"""
passive_store.py — PassiveMixin: 被动技能数据持久化。

Redis keys:
  qqbot:passive:{user_id}:slots     hash  field=1~4, value=skill_id
  qqbot:passive:{user_id}:level:{skill_id}  str   技能等级
  qqbot:passive:{user_id}:bag:{skill_id}    str   背包中技能书数量
  qqbot:passive_reset:{user_id}:{slot}:{date}  str  当日是否已重置
"""
import time
from src.data.models import _redis_client


def _slot_key(user_id: str) -> str:
    return f"qqbot:passive:{user_id}:slots"


def _level_key(user_id: str, skill_id: str) -> str:
    return f"qqbot:passive:{user_id}:level:{skill_id}"


def _bag_key(user_id: str, skill_id: str) -> str:
    return f"qqbot:passive:{user_id}:bag:{skill_id}"


def _reset_key(user_id: str, slot: int) -> str:
    date = time.strftime("%Y-%m-%d")
    return f"qqbot:passive_reset:{user_id}:{slot}:{date}"


class PassiveMixin:

    def get_passive_slots(self, user_id: str) -> dict[str, str]:
        result = _redis_client.hgetall(_slot_key(user_id))
        if isinstance(result, dict):
            return {k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in result.items()}
        return {}

    def get_passive_level(self, user_id: str, skill_id: str) -> int:
        val = _redis_client.get(_level_key(user_id, skill_id))
        if val is None:
            return 0
        return int(val)

    def get_passive_bag(self, user_id: str, skill_id: str) -> int:
        val = _redis_client.get(_bag_key(user_id, skill_id))
        if val is None:
            return 0
        return int(val)

    def get_all_passive_bags(self, user_id: str) -> dict[str, int]:
        pattern = f"qqbot:passive:{user_id}:bag:*"
        keys = _redis_client.keys(pattern)
        result = {}
        for k in keys:
            key_str = k.decode() if isinstance(k, bytes) else k
            skill_id = key_str.split(":bag:")[-1]
            val = _redis_client.get(key_str)
            if val:
                result[skill_id] = int(val)
        return result

    def set_passive_slot(self, user_id: str, slot: int, skill_id: str):
        _redis_client.hset(_slot_key(user_id), str(slot), skill_id)

    def clear_passive_slot(self, user_id: str, slot: int):
        _redis_client.hdel(_slot_key(user_id), str(slot))

    def set_passive_level(self, user_id: str, skill_id: str, level: int):
        _redis_client.set(_level_key(user_id, skill_id), str(level))

    def add_passive_bag(self, user_id: str, skill_id: str, qty: int = 1):
        key = _bag_key(user_id, skill_id)
        _redis_client.incrby(key, qty)

    def use_passive_bag(self, user_id: str, skill_id: str, qty: int = 1) -> bool:
        current = self.get_passive_bag(user_id, skill_id)
        if current < qty:
            return False
        key = _bag_key(user_id, skill_id)
        _redis_client.decrby(key, qty)
        return True

    def is_passive_reset_today(self, user_id: str, slot: int) -> bool:
        val = _redis_client.get(_reset_key(user_id, slot))
        return val is not None

    def mark_passive_reset(self, user_id: str, slot: int):
        key = _reset_key(user_id, slot)
        _redis_client.set(key, "1")
        _redis_client.expire(key, 86400)
