"""
bot.py - QQ 机器人 Webhook 模式 (HTTPS)
基于 QQ 开放平台官方 API，仅处理群聊 @ 消息和私聊消息
"""
import json
import ssl
import time
import asyncio
import logging
import datetime
from pathlib import Path

import aiohttp
from aiohttp import web
import nacl.signing

from src.config import config
from src.handler import handle_message
from src.token_manager import token_manager
from src.data_manager import data_manager

logger = logging.getLogger("QQBot")

# Playwright lazy import（避免未安装时崩溃）
_playwright_available = True
try:
    from playwright.async_api import async_playwright
except ImportError:
    _playwright_available = False
    logger.warning("Playwright 未安装，HTML截图功能不可用。请执行: pip install playwright && playwright install chromium 或 playwright install msedge")

# API 基础 URL
SANDBOX = config["bot"]["sandbox"]
API_BASE = "https://sandbox.api.sgroup.qq.com" if SANDBOX else "https://api.sgroup.qq.com"


def _generate_self_signed_cert(cert_path: Path, key_path: Path, hostname: str = "localhost"):
    """自动生成自签名 SSL 证书（开发/测试用）

    Args:
        hostname: 证书绑定的主机名或 IP（如 "1.2.3.4" 或 "bot.example.com"）
    """
    import ipaddress

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        logger.error("生成自签名证书需要 cryptography 库，请执行: pip install cryptography")
        return False

    # 判断是 IP 还是域名
    try:
        ipaddress.ip_address(hostname)
        san = [x509.IPAddress(ipaddress.IPv4Address(hostname))]
        is_ip = True
    except ValueError:
        san = [x509.DNSName(hostname)]
        is_ip = False

    # 生成私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # 构建证书，CN 使用给定的 hostname
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Guangdong"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Shenzhen"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QQBot"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # 写入文件
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    mode = "IP" if is_ip else "域名"
    logger.info(f"🔐 已生成自签名证书 (CN={hostname}, {mode}): {cert_path}")
    return True


class QQBot:
    """QQ 开放平台机器人 (Webhook 模式, HTTPS)

    仅处理两种事件：
    - GROUP_AT_MESSAGE_CREATE : 群聊中 @ 机器人的消息
    - C2C_MESSAGE_CREATE      : 用户私聊机器人的消息
    """

    def __init__(self):
        self.app_id = str(config["bot"]["app_id"])
        self.secret = config["bot"]["secret"]
        self._sessions: dict[str, aiohttp.ClientSession] = {}
        self._playwright_browser = None
        self._playwright = None

        # ── 截图并发控制与页面预热池 ──
        _concurrency = config.get("image", {}).get("screenshot_concurrency", 2)
        self._screenshot_semaphore = asyncio.Semaphore(_concurrency)
        self._page_pool: list = []

        # ── 去重与防抖 ──
        self._processed_msg_ids: dict[str, float] = {}   # msg_id → 处理时间戳
        self._last_user_request: dict[str, float] = {}    # user_id → 最近请求时间戳
        self._MSG_ID_TTL = 10.0       # 同一 msg_id 10s 内重复则忽略
        self._USER_DEBOUNCE = 2.0     # 同一用户请求间隔至少 2s
        self._cleanup_task: asyncio.Task | None = None              # 去重记录清理
        self._daily_screenshot_cleanup_task: asyncio.Task | None = None  # 截图每日兜底清理

    # ──────────────────────────────────────────────
    # 签名与验证
    # ──────────────────────────────────────────────

    def _verify_signature(self, event_ts: str, plain_token: str) -> str:
        """计算 Webhook 验证签名 (Ed25519)

        QQ 开放平台 URL 验证流程（op=13）：
        1. 平台向 webhook 地址发送 POST，body 包含 op=13, d.plain_token, d.event_ts
        2. 用 robot_secret 派生 Ed25519 密钥种子，对 event_ts + plain_token 做 Ed25519 签名
        3. 返回 {"plain_token": "...", "signature": "..."}
        """
        # 1. 派生 32 字节种子：重复 secret 直到 >= 32，取前 32 字节
        seed = self.secret
        while len(seed) < 32:
            seed = seed * 2
        seed_bytes = seed[:32].encode("utf-8")

        # 2. 从种子生成 Ed25519 签名密钥
        signing_key = nacl.signing.SigningKey(seed_bytes)

        # 3. 对 event_ts + plain_token 签名
        message = (event_ts + plain_token).encode("utf-8")
        signed = signing_key.sign(message)

        # 4. 返回十六进制签名
        return signed.signature.hex()

    # ──────────────────────────────────────────────
    # HTTP Client
    # ──────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP Session"""
        task_id = id(asyncio.current_task())
        if task_id not in self._sessions:
            self._sessions[task_id] = aiohttp.ClientSession()
        return self._sessions[task_id]

    async def _api_headers(self) -> dict:
        """构建 API 请求头，从 Redis 获取 token"""
        token = await token_manager.get_token()
        if not token:
            logger.error("无法从 Redis 获取 access_token，API 调用将失败")
            token = ""
        return {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        }

    async def _post_api(self, url: str, payload: dict) -> bool:
        """统一的 API POST 调用"""
        session = await self._get_session()
        try:
            async with session.post(url, json=payload,
                                    headers=await self._api_headers()) as resp:
                if resp.status in (200, 202):
                    logger.debug(f"API 成功: {url}")
                    return True
                body = await resp.text()
                logger.error(f"API 失败 [{resp.status}] {url}: {body}")
                return False
        except Exception as e:
            logger.error(f"API 异常 {url}: {e}")
            return False

    # ──────────────────────────────────────────────
    # 消息发送
    # ──────────────────────────────────────────────

    def _build_msg_payload(self, reply, msg_id: str, msg_seq: int = 0) -> dict:
        """根据回复内容类型构建消息载荷"""
        if isinstance(reply, str):
            payload = {
                "content": reply,
                "msg_type": 0,
                "msg_id": msg_id,
            }
            if msg_seq > 0:
                payload["msg_seq"] = msg_seq
            return payload

        if isinstance(reply, dict):
            payload = {"msg_id": msg_id}
            if msg_seq > 0:
                payload["msg_seq"] = msg_seq
            if "msg_type" in reply:
                payload.update(reply)
            else:
                payload["content"] = reply.get("content", "")
                payload["msg_type"] = reply.get("msg_type", 0)
                if "keyboard" in reply:
                    payload["keyboard"] = reply["keyboard"]
            return payload

        payload = {
            "content": str(reply),
            "msg_type": 0,
            "msg_id": msg_id,
        }
        if msg_seq > 0:
            payload["msg_seq"] = msg_seq
        return payload

    async def send_group_reply(self, group_openid: str, msg_id: str,
                                reply, msg_seq: int = 0) -> bool:
        """回复群聊消息（支持文本和模板消息）"""
        url = f"{API_BASE}/v2/groups/{group_openid}/messages"
        payload = self._build_msg_payload(reply, msg_id, msg_seq)
        return await self._post_api(url, payload)

    async def send_c2c_reply(self, user_openid: str, msg_id: str,
                              reply, msg_seq: int = 0) -> bool:
        """回复私聊消息（支持文本和模板消息）"""
        url = f"{API_BASE}/v2/users/{user_openid}/messages"
        payload = self._build_msg_payload(reply, msg_id, msg_seq)
        return await self._post_api(url, payload)

    # ──────────────────────────────────────────────
    # 事件处理
    # ──────────────────────────────────────────────

    async def handle_group_at(self, data: dict):
        """处理群聊 @ 消息"""
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
        """处理私聊消息"""
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

    # ──────────────────────────────────────────────
    # 去重 / 防抖工具
    # ──────────────────────────────────────────────

    def _cleanup_expired(self) -> None:
        """清理过期的去重和防抖记录，防止内存泄漏"""
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
        """后台协程：每 30 秒清理一次过期记录"""
        while True:
            await asyncio.sleep(30)
            self._cleanup_expired()

    # ──────────────────────────────────────────────
    # Webhook HTTP 路由处理
    # ──────────────────────────────────────────────

    async def webhook_handler(self, request: web.Request) -> web.Response:
        """Webhook 统一入口

        1. URL 验证（op=13）→ 返回签名后的 token
        2. 事件分发（op=0）→ 路由到对应处理器
        """
        # 获取原始请求体文本（用于调试）
        raw_body = await request.text()
        logger.debug(
            f"Webhook 请求 | 来源: {request.remote} | "
            f"Headers: {dict(request.headers)} | Body: {raw_body[:500]}"
        )

        # 解析 JSON
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

        # ── URL 验证（op=13）──
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

        # ── 事件分发（op=0）──
        if op == 0:
            event_type = body.get("t", "")
            event_data = d

            # 提取 msg_id 和 user_id（群聊/私聊字段统一提取）
            msg_id = event_data.get("id", "")
            author = event_data.get("author", {})
            user_id = author.get("member_openid") or author.get("user_openid") or author.get("id", "")

            now = time.time()

            # ── msg_id 去重：10s 内同一 msg_id 视为重放，直接忽略 ──
            if msg_id and msg_id in self._processed_msg_ids:
                if now - self._processed_msg_ids[msg_id] < self._MSG_ID_TTL:
                    logger.debug(f"忽略重复消息 msg_id={msg_id}")
                    return web.Response(text='{"code": 0}', content_type="application/json")

            # ── user_id 防抖：同一用户 2s 内多次请求只处理第一次 ──
            if user_id and user_id in self._last_user_request:
                elapsed = now - self._last_user_request[user_id]
                if elapsed < self._USER_DEBOUNCE:
                    logger.debug(f"忽略高频请求 user_id={user_id} elapsed={elapsed:.2f}s")
                    return web.Response(text='{"code": 0}', content_type="application/json")

            # 记录本次请求
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

    # ──────────────────────────────────────────────
    # 启动 & 清理
    # ──────────────────────────────────────────────

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        """根据配置构建 SSL 上下文

        仅在 force_https = true 时启用 HTTPS：
        - 自动检测用户配置或默认路径的证书
        - 若无证书则自动生成自签名证书
        - force_https = false 时直接返回 None（HTTP 模式，配合 ngrok/frp 使用）
        """
        webhook_cfg = config["webhook"]

        # 不强制 HTTPS → HTTP 模式（适合 ngrok/frp 等反向代理）
        if not webhook_cfg.get("force_https", False):
            return None

        # 以下为 HTTPS 模式
        cert_file = webhook_cfg.get("ssl_cert", "")
        key_file = webhook_cfg.get("ssl_key", "")

        if cert_file and key_file:
            cert_path = Path(cert_file)
            key_path = Path(key_file)
            if not cert_path.is_absolute():
                cert_path = Path(__file__).parent.parent / cert_path
            if not key_path.is_absolute():
                key_path = Path(__file__).parent.parent / key_path
        else:
            cert_path = Path(__file__).parent.parent / "certs" / "cert.pem"
            key_path = Path(__file__).parent.parent / "certs" / "key.pem"

        # 证书不存在，或 hostname 变更 → 重新生成
        hostname = webhook_cfg.get("cert_hostname", "localhost")
        need_regenerate = not cert_path.exists() or not key_path.exists()
        if need_regenerate:
            logger.info(f"未找到 SSL 证书，正在为 {hostname} 生成自签名证书...")
            if not _generate_self_signed_cert(cert_path, key_path, hostname):
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
        """启动 Webhook HTTPS 服务"""
        # ── 启动 Token 管理器（后台获取 & 定时刷新）──
        await token_manager.start()

        # ── 启动后台清理协程（去重/防抖记录过期清理）──
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        webhook_cfg = config["webhook"]
        host = webhook_cfg["host"]
        port = webhook_cfg["port"]
        path = webhook_cfg["path"]
        image_cfg = config["image"]

        app = web.Application()
        app.router.add_post(path, self.webhook_handler)
        app.router.add_get(path, self.webhook_handler)

        # ── 图片服务路由 ──
        image_dir = image_cfg["dir"]
        image_route = image_cfg["route"]
        abs_image_dir = Path(image_dir)
        if not abs_image_dir.is_absolute():
            abs_image_dir = Path(__file__).parent.parent / abs_image_dir
        abs_image_dir.mkdir(parents=True, exist_ok=True)
        app.router.add_static(image_route, str(abs_image_dir), show_index=True)

        # ── 清理截图孤儿文件 + 确保目录存在 ──
        from src.image_lifecycle import cleanup_orphan_files, daily_cleanup_loop
        screenshots_dir = Path(image_cfg.get("screenshots_dir", "data/images/screenshots"))
        if not screenshots_dir.is_absolute():
            screenshots_dir = Path(__file__).parent.parent / screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        cleanup_orphan_files(screenshots_dir)

        # ── 启动截图每日 0 点兜底清理协程 ──
        self._daily_screenshot_cleanup_task = asyncio.create_task(
            daily_cleanup_loop(screenshots_dir)
        )

        # ── 启动 Playwright browser（优先 chromium，失败则尝试 msedge）──
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

        # ── 预热页面池（减少首次截图延迟）──
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

        # ── SSL 配置 ──
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

        # 保持运行
        while True:
            await asyncio.sleep(3600)

    async def shutdown(self):
        """清理资源"""
        # 取消后台清理协程
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 取消截图每日清理协程
        if self._daily_screenshot_cleanup_task:
            self._daily_screenshot_cleanup_task.cancel()
            try:
                await self._daily_screenshot_cleanup_task
            except asyncio.CancelledError:
                pass

        await token_manager.shutdown()
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()
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
