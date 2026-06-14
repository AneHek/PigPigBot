import logging

import aiohttp

from src.config import config
from src.core.token_manager import token_manager

logger = logging.getLogger("QQBot")

SANDBOX = config["bot"]["sandbox"]
API_BASE = "https://sandbox.api.sgroup.qq.com" if SANDBOX else "https://api.sgroup.qq.com"


class ApiClient:

    def __init__(self):
        self._sessions: dict[str, aiohttp.ClientSession] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        import asyncio
        task_id = id(asyncio.current_task())
        if task_id not in self._sessions:
            self._sessions[task_id] = aiohttp.ClientSession()
        return self._sessions[task_id]

    async def _api_headers(self) -> dict:
        token = await token_manager.get_token()
        if not token:
            logger.error("无法从 Redis 获取 access_token，API 调用将失败")
            token = ""
        return {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        }

    async def _post_api(self, url: str, payload: dict) -> bool:
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

    def _build_msg_payload(self, reply, msg_id: str, msg_seq: int = 0) -> dict:
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
        url = f"{API_BASE}/v2/groups/{group_openid}/messages"
        payload = self._build_msg_payload(reply, msg_id, msg_seq)
        return await self._post_api(url, payload)

    async def send_c2c_reply(self, user_openid: str, msg_id: str,
                              reply, msg_seq: int = 0) -> bool:
        url = f"{API_BASE}/v2/users/{user_openid}/messages"
        payload = self._build_msg_payload(reply, msg_id, msg_seq)
        return await self._post_api(url, payload)

    async def close(self):
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()
