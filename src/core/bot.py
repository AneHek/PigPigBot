import json
import ssl
import time
import asyncio
import logging
from pathlib import Path

from aiohttp import web
import nacl.signing

from src.config import config
from src.handler import handle_message
from src.core.token_manager import token_manager
from src.core.api import ApiClient, SANDBOX
from src.core.ssl_utils import generate_self_signed_cert
from src.data import data_manager

logger = logging.getLogger("QQBot")

_playwright_available = True
try:
    from playwright.async_api import async_playwright
except ImportError:
    _playwright_available = False
    logger.warning("Playwright 未安装，HTML截图功能不可用。请执行: pip install playwright && playwright install chromium 或 playwright install msedge")


class QQBot(ApiClient):

    def __init__(self):
        super().__init__()
        self.app_id = str(config["bot"]["app_id"])
        self.secret = config["bot"]["secret"]
        self._playwright_browser = None
        self._playwright = None

        _concurrency = config.get("image", {}).get("screenshot_concurrency", 2)
        self._screenshot_semaphore = asyncio.Semaphore(_concurrency)
        self._page_pool: list = []

        self._processed_msg_ids: dict[str, float] = {}
        self._last_user_request: dict[str, float] = {}
        self._MSG_ID_TTL = 10.0
        self._USER_DEBOUNCE = 2.0
        self._cleanup_task: asyncio.Task | None = None
        self._daily_screenshot_cleanup_task: asyncio.Task | None = None

    def _verify_signature(self, event_ts: str, plain_token: str) -> str:
        seed = self.secret
        while len(seed) < 32:
            seed = seed * 2
        seed_bytes = seed[:32].encode("utf-8")

        signing_key = nacl.signing.SigningKey(seed_bytes)

        message = (event_ts + plain_token).encode("utf-8")
        signed = signing_key.sign(message)

        return signed.signature.hex()

    async def handle_group_at(self, data: dict):
        content = data.get("content", "").strip()
        author = data.get("author", {})
        user_id = author.get("member_openid", author.get("id", ""))
        user_name = author.get("username", "未知")
        group_openid = data.get("group_openid", data.get("group_id", ""))
        msg_id = data.get("id", "")

        if not user_id or not group_openid:
            logger.warning(f"群聊事件缺少关键字段: user={user_id}, group={group_openid}")
            return

        logger.info(f"群聊 @ 消息 | 用户: {user_name}({user_id}) | 群: {group_openid} | 内容: {content[:50]}")

        data_manager.add_group_member(group_openid, user_id)

        reply = await handle_message(user_id, user_name, content, group_id=group_openid)
        if reply:
            if isinstance(reply, list):
                for seq, msg in enumerate(reply, start=1):
                    if seq > 1:
                        await asyncio.sleep(1)
                    await self.send_group_reply(group_openid, msg_id, msg, msg_seq=seq)
            else:
                await self.send_group_reply(group_openid, msg_id, reply)

    async def handle_c2c(self, data: dict):
        content = data.get("content", "").strip()
        author = data.get("author", {})
        user_id = author.get("user_openid", author.get("id", ""))
        user_name = author.get("username", "未知")
        msg_id = data.get("id", "")

        if not user_id:
            logger.warning("私聊事件缺少用户 ID")
            return

        logger.info(f"私聊消息 | 用户: {user_name}({user_id}) | 内容: {content[:50]}")

        reply = await handle_message(user_id, user_name, content)
        if reply:
            if isinstance(reply, list):
                for seq, msg in enumerate(reply, start=1):
                    if seq > 1:
                        await asyncio.sleep(1)
                    await self.send_c2c_reply(user_id, msg_id, msg, msg_seq=seq)
            else:
                await self.send_c2c_reply(user_id, msg_id, reply)

    def _cleanup_expired(self) -> None:
        now = time.time()
        msg_cutoff = now - self._MSG_ID_TTL
        user_cutoff = now - self._USER_DEBOUNCE
        self._processed_msg_ids = {
            k: v for k, v in self._processed_msg_ids.items() if v > msg_cutoff
        }
        self._last_user_request = {
            k: v for k, v in self._last_user_request.items() if v > user_cutoff
        }

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            self._cleanup_expired()

    async def webhook_handler(self, request: web.Request) -> web.Response:
        raw_body = await request.text()
        logger.debug(
            f"Webhook 请求 | 来源: {request.remote} | "
            f"Headers: {dict(request.headers)} | Body: {raw_body[:500]}"
        )

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.warning(f"Webhook 请求体 JSON 解析失败: {e} | 原始内容: {raw_body[:200]}")
            return web.Response(
                text='{"code": 400, "message": "invalid json"}',
                content_type="application/json",
            )

        op = body.get("op")
        d = body.get("d", {})

        if op == 13:
            plain_token = d.get("plain_token", "")
            event_ts = d.get("event_ts", "")
            if not plain_token or not event_ts:
                logger.warning("URL 验证请求缺少 plain_token 或 event_ts")
                return web.json_response({
                    "plain_token": plain_token,
                    "signature": "",
                })

            signature = self._verify_signature(event_ts, plain_token)
            logger.info(
                f"Webhook URL 验证 | event_ts={event_ts} "
                f"plain_token={plain_token[:20]}... "
                f"signature={signature[:20]}..."
            )
            return web.json_response({
                "plain_token": plain_token,
                "signature": signature,
            })

        if op == 0:
            event_type = body.get("t", "")
            event_data = d

            msg_id = event_data.get("id", "")
            author = event_data.get("author", {})
            user_id = author.get("member_openid") or author.get("user_openid") or author.get("id", "")

            now = time.time()

            if msg_id and msg_id in self._processed_msg_ids:
                if now - self._processed_msg_ids[msg_id] < self._MSG_ID_TTL:
                    logger.debug(f"忽略重复消息 msg_id={msg_id}")
                    return web.Response(text='{"code": 0}', content_type="application/json")

            if user_id and user_id in self._last_user_request:
                elapsed = now - self._last_user_request[user_id]
                if elapsed < self._USER_DEBOUNCE:
                    logger.debug(f"忽略高频请求 user_id={user_id} elapsed={elapsed:.2f}s")
                    return web.Response(text='{"code": 0}', content_type="application/json")

            if msg_id:
                self._processed_msg_ids[msg_id] = now
            if user_id:
                self._last_user_request[user_id] = now

            if event_type == "GROUP_AT_MESSAGE_CREATE":
                await self.handle_group_at(event_data)
            elif event_type == "C2C_MESSAGE_CREATE":
                await self.handle_c2c(event_data)
            else:
                logger.debug(f"忽略未处理的事件类型: {event_type}")

        return web.Response(text='{"code": 0}', content_type="application/json")

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        webhook_cfg = config["webhook"]

        if not webhook_cfg.get("force_https", False):
            return None

        cert_file = webhook_cfg.get("ssl_cert", "")
        key_file = webhook_cfg.get("ssl_key", "")

        if cert_file and key_file:
            cert_path = Path(cert_file)
            key_path = Path(key_file)
            if not cert_path.is_absolute():
                cert_path = Path(__file__).parent.parent.parent / cert_path
            if not key_path.is_absolute():
                key_path = Path(__file__).parent.parent.parent / key_path
        else:
            cert_path = Path(__file__).parent.parent.parent / "certs" / "cert.pem"
            key_path = Path(__file__).parent.parent.parent / "certs" / "key.pem"

        hostname = webhook_cfg.get("cert_hostname", "localhost")
        need_regenerate = not cert_path.exists() or not key_path.exists()
        if need_regenerate:
            logger.info(f"未找到 SSL 证书，正在为 {hostname} 生成自签名证书...")
            if not generate_self_signed_cert(cert_path, key_path, hostname):
                logger.error("无法生成 SSL 证书，回退到 HTTP 模式")
                return None

        try:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(str(cert_path), str(key_path))
            logger.info(f"✅ SSL 证书加载成功: {cert_path}")
            return ssl_ctx
        except Exception as e:
            logger.error(f"SSL 证书加载失败: {e}")
            return None

    async def start(self):
        await token_manager.start()

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        webhook_cfg = config["webhook"]
        host = webhook_cfg["host"]
        port = webhook_cfg["port"]
        path = webhook_cfg["path"]
        image_cfg = config["image"]

        app = web.Application()
        app.router.add_post(path, self.webhook_handler)
        app.router.add_get(path, self.webhook_handler)

        image_dir = image_cfg["dir"]
        image_route = image_cfg["route"]
        abs_image_dir = Path(image_dir)
        if not abs_image_dir.is_absolute():
            abs_image_dir = Path(__file__).parent.parent.parent / abs_image_dir
        abs_image_dir.mkdir(parents=True, exist_ok=True)
        app.router.add_static(image_route, str(abs_image_dir), show_index=True)

        from src.screenshot.lifecycle import cleanup_orphan_files, daily_cleanup_loop
        screenshots_dir = Path(image_cfg.get("screenshots_dir", "data/images/screenshots"))
        if not screenshots_dir.is_absolute():
            screenshots_dir = Path(__file__).parent.parent.parent / screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        cleanup_orphan_files(screenshots_dir)

        self._daily_screenshot_cleanup_task = asyncio.create_task(
            daily_cleanup_loop(screenshots_dir)
        )

        if _playwright_available:
            try:
                self._playwright = await async_playwright().start()
                try:
                    self._playwright_browser = await self._playwright.chromium.launch(headless=True)
                    logger.info("🎭 Playwright browser 已启动 (chromium)")
                except Exception:
                    logger.info("Chromium 不可用，尝试使用 Microsoft Edge...")
                    self._playwright_browser = await self._playwright.chromium.launch(
                        channel="msedge", headless=True
                    )
                    logger.info("🎭 Playwright browser 已启动 (msedge)")
            except Exception as e:
                logger.warning(f"Playwright browser 启动失败: {e}，截图功能不可用")

        if self._playwright_browser:
            _pool_size = config.get("image", {}).get("screenshot_concurrency", 2)
            for i in range(_pool_size):
                try:
                    page = await self._playwright_browser.new_page(
                        viewport={"width": 380, "height": 800})
                    self._page_pool.append(page)
                except Exception as e:
                    logger.warning(f"预热页面 {i} 失败: {e}")
            if self._page_pool:
                logger.info(f"📄 页面预热池就绪: {len(self._page_pool)} 个页面")

        ssl_context = self._build_ssl_context()
        protocol = "https" if ssl_context else "http"
        force_https = config["webhook"].get("force_https", False)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port, ssl_context=ssl_context)

        logger.info("=" * 50)
        logger.info("🐾 QQ 宠物养成机器人 启动中...")
        logger.info(f"📡 模式：Webhook ({protocol.upper()})")
        logger.info(f"🔗 服务地址：{protocol}://{host}:{port}{path}")
        logger.info(f"🖼️  图片地址：{protocol}://{host}:{port}{image_route}/{{文件名}}")
        logger.info(f"📋 处理事件：群聊@消息 + 私聊消息")
        logger.info(f"🔧 沙箱模式：{SANDBOX}")
        if not ssl_context:
            if force_https:
                logger.warning("⚠️  force_https 已开启但 SSL 证书加载失败，请检查 certs/ 目录")
            else:
                logger.info("ℹ️  本地 HTTP 模式，请通过 ngrok/frp/nginx 等反向代理提供 HTTPS")
                logger.info("💡 提示：QQ 开放平台回调地址需填写代理提供的 HTTPS 地址")
        logger.info("=" * 50)

        await site.start()
        logger.info(f"Webhook 服务已启动，等待事件推送...")

        while True:
            await asyncio.sleep(3600)

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._daily_screenshot_cleanup_task:
            self._daily_screenshot_cleanup_task.cancel()
            try:
                await self._daily_screenshot_cleanup_task
            except asyncio.CancelledError:
                pass

        await token_manager.shutdown()
        await self.close()
        for page in self._page_pool:
            try:
                await page.close()
            except Exception:
                pass
        self._page_pool.clear()
        if self._playwright_browser:
            await self._playwright_browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("机器人已关闭")
