"""
token_manager.py - QQ 机器人 AccessToken 管理器

通过 QQ 开放平台 API 获取 access_token，存入 Redis，
并启动后台线程定期校验和刷新 token。
"""
import time
import asyncio
import logging
import threading

import aiohttp
import redis.asyncio as aioredis

from src.config import config

logger = logging.getLogger("TokenManager")

# ── API 地址 ──
TOKEN_API_URL = "https://bots.qq.com/app/getAppAccessToken"

# Redis key
REDIS_TOKEN_KEY = "qqbot:access_token"
REDIS_TOKEN_EXPIRES_KEY = "qqbot:access_token_expires_at"

class TokenManager:
    """QQ 机器人 AccessToken 管理器（基于 Redis + 后台线程）"""

    def __init__(self):
        self._app_id = str(config["bot"]["app_id"])
        self._client_secret = config["bot"]["secret"]
        self._redis: aioredis.Redis | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._refresh_task: asyncio.Task | None = None
        self._stop_event = threading.Event()

    # ─── Redis 连接 ──────────────────────────────────

    async def _get_redis(self) -> aioredis.Redis:
        """获取或创建 Redis 连接"""
        if self._redis is None:
            redis_cfg = config.get("redis", {})
            self._redis = aioredis.Redis(
                host=redis_cfg.get("host", "localhost"),
                port=redis_cfg.get("port", 6379),
                password=redis_cfg.get("password", "") or None,
                db=redis_cfg.get("db", 0),
                decode_responses=True,
            )
            # 测试连接
            await self._redis.ping()
            logger.info("✅ Redis 连接成功")
        return self._redis

    # ─── Token 获取 ──────────────────────────────────

    async def fetch_and_store_token(self) -> str | None:
        """从 QQ 开放平台获取 access_token 并存入 Redis

        Returns:
            成功返回 token 字符串，失败返回 None
        """
        payload = {
            "appId": self._app_id,
            "clientSecret": self._client_secret,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(TOKEN_API_URL, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"获取 access_token 失败 [{resp.status}]: {body}")
                        return None

                    data = await resp.json()

        except aiohttp.ClientError as e:
            logger.error(f"请求 access_token 网络异常: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}")
            return None

        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 7200))

        if not access_token:
            logger.error(f"access_token 为空，响应: {data}")
            return None

        # 存入 Redis，设置过期时间（加一些缓冲，避免 Redis key 比实际 token 先过期）
        try:
            r = await self._get_redis()
            pipe = r.pipeline()
            pipe.set(REDIS_TOKEN_KEY, access_token)
            pipe.set(REDIS_TOKEN_EXPIRES_KEY, str(time.time() + expires_in))
            # Redis key 过期时间略长于 token 有效期，防止刚好卡点
            pipe.expire(REDIS_TOKEN_KEY, expires_in + 60)
            pipe.expire(REDIS_TOKEN_EXPIRES_KEY, expires_in + 60)
            await pipe.execute()

            logger.info(
                f"✅ access_token 已获取并存入 Redis，"
                f"有效期 {expires_in}s ({expires_in / 3600:.1f}h)，"
                f"前20位: {access_token[:20]}..."
            )
            return access_token

        except Exception as e:
            logger.error(f"存储 access_token 到 Redis 失败: {e}")
            return None

    # ─── Token 读取 ──────────────────────────────────

    async def get_token(self) -> str | None:
        """从 Redis 读取当前有效的 access_token

        Returns:
            有效 token 字符串，不存在或读取失败返回 None
        """
        try:
            r = await self._get_redis()
            token = await r.get(REDIS_TOKEN_KEY)
            if token:
                return token
            logger.warning("Redis 中未找到 access_token")
            return None
        except Exception as e:
            logger.error(f"从 Redis 读取 token 失败: {e}")
            return None

    # ─── 后台刷新 ────────────────────────────────────

    async def _refresh_loop(self):
        """后台循环：定期检查并刷新 token"""
        logger.info("🔄 Token 后台刷新线程已启动")

        # 首次获取
        if not await self._token_exists():
            logger.info("首次启动，获取 access_token...")
            await self.fetch_and_store_token()

        while not self._stop_event.is_set():
            try:
                should_refresh = await self._need_refresh()

                if should_refresh:
                    # 记录刷新前的过期时间，用于检测 token 是否真的更新了
                    old_expires = await self._get_expires_at()
                    logger.info("token 即将过期，刷新中...")
                    result = await self.fetch_and_store_token()

                    if result is None:
                        logger.warning("token 刷新失败，5s 后重试")
                        await self._sleep_with_stop(5)
                    else:
                        # 检查 token 是否真的更新了（QQ 平台只在过期前 60s 返回新 token）
                        new_expires = await self._get_expires_at()
                        if new_expires and old_expires and abs(new_expires - old_expires) < 1:
                            # 令牌未实际刷新（还在 QQ 刷新窗口外），等待进入窗口
                            remaining = old_expires - time.time()
                            wait = max(remaining - 50, 5)  # 等到只剩 50s
                            logger.info(f"token 未实际更新（QQ 刷新窗口外），{wait:.0f}s 后重试")
                            await self._sleep_with_stop(int(wait))
                        else:
                            logger.info("token 刷新成功")
                            await self._sleep_with_stop(5)
                else:
                    # 计算下次检查时间
                    sleep_seconds = await self._get_sleep_seconds()
                    logger.debug(f"token 状态正常，{sleep_seconds}s 后再次检查")
                    await self._sleep_with_stop(sleep_seconds)

            except Exception as e:
                logger.error(f"token 刷新循环异常: {e}")
                # 出错后等待 60 秒再重试
                await self._sleep_with_stop(60)

        logger.info("Token 刷新循环已停止")

    async def _get_expires_at(self) -> float | None:
        """从 Redis 读取 token 过期时间戳，失败返回 None"""
        try:
            r = await self._get_redis()
            expires_str = await r.get(REDIS_TOKEN_EXPIRES_KEY)
            if expires_str:
                return float(expires_str)
            return None
        except Exception:
            return None

    async def _token_exists(self) -> bool:
        """检查 Redis 中是否存在有效 token"""
        try:
            r = await self._get_redis()
            return await r.exists(REDIS_TOKEN_KEY) > 0
        except Exception:
            return False

    async def _need_refresh(self) -> bool:
        """判断是否需要刷新 token

        QQ 平台限制：只在过期前 60s 内才能拿到新 token，
        提前请求只会返回旧 token。因此阈值设在 55s，
        留 5s 缓冲确保进入刷新窗口。
        """
        try:
            r = await self._get_redis()
            expires_str = await r.get(REDIS_TOKEN_EXPIRES_KEY)
            if not expires_str:
                return True

            expires_at = float(expires_str)
            remaining = expires_at - time.time()

            # QQ 平台只在过期前 60s 内允许刷新
            threshold = 55

            if remaining <= threshold:
                logger.info(f"token 剩余有效期 {remaining:.0f}s <= {threshold}s，需要刷新")
                return True

            return False
        except Exception as e:
            logger.error(f"检查 token 有效期失败: {e}")
            return True  # 出错时也尝试刷新

    async def _sleep_with_stop(self, seconds: int):
        """带停止信号的 sleep，收到 stop 事件时提前退出"""
        for _ in range(int(seconds)):
            if self._stop_event.is_set():
                break
            await asyncio.sleep(1)

    async def _get_sleep_seconds(self) -> int:
        """计算下次检查的等待秒数（等到剩余 threshold 时再检查）"""
        try:
            r = await self._get_redis()
            expires_str = await r.get(REDIS_TOKEN_EXPIRES_KEY)
            if not expires_str:
                return 60

            expires_at = float(expires_str)
            remaining = expires_at - time.time()
            threshold = 55  # 与 _need_refresh 保持一致

            # 等到剩余 threshold 时再检查，至少等 10s 避免忙等
            sleep_seconds = max(int(remaining - threshold), 10)
            return min(sleep_seconds, 3600)

        except Exception:
            return 60

    # ─── 启动 & 停止 ──────────────────────────────────

    async def start(self):
        """启动 Token 管理器（在 event loop 中调用）"""
        self._loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("TokenManager 已启动")

    async def shutdown(self):
        """关闭 Token 管理器"""
        logger.info("正在关闭 TokenManager...")
        self._stop_event.set()

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self._redis:
            await self._redis.close()
            self._redis = None

        logger.info("TokenManager 已关闭")


# ─── 全局单例 ──────────────────────────────────────────
token_manager = TokenManager()
