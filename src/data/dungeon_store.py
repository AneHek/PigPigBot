from datetime import datetime

from src.data.models import _redis_client

KEY_DUNGEON_COUNT = "qqbot:dungeon:{user_id}:{ch}:{stage}:{date}"
KEY_DUNGEON_FIRST = "qqbot:dungeon:first:{user_id}"
KEY_DUNGEON_RESET = "qqbot:dungeon_reset:{user_id}:{ch}:{date}"


class DungeonMixin:

    def _dungeon_count_key(self, user_id: str, ch: int, stage: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_DUNGEON_COUNT.format(user_id=user_id, ch=ch, stage=stage, date=date)

    def _dungeon_first_key(self, user_id: str) -> str:
        return KEY_DUNGEON_FIRST.format(user_id=user_id)

    def _dungeon_reset_key(self, user_id: str, ch: int) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_DUNGEON_RESET.format(user_id=user_id, ch=ch, date=date)

    def get_dungeon_count(self, user_id: str, ch: int, stage: str) -> int:
        val = _redis_client.get(self._dungeon_count_key(user_id, ch, stage))
        return int(val) if val else 0

    def incr_dungeon_count(self, user_id: str, ch: int, stage: str) -> int:
        key = self._dungeon_count_key(user_id, ch, stage)
        result = _redis_client.incr(key)
        _redis_client.expire(key, 86400)
        return result

    def is_dungeon_first(self, user_id: str, ch: int, stage: str) -> bool:
        key = self._dungeon_first_key(user_id)
        return _redis_client.sismember(key, f"{ch}-{stage}")

    def mark_dungeon_first(self, user_id: str, ch: int, stage: str) -> bool:
        key = self._dungeon_first_key(user_id)
        return _redis_client.sadd(key, f"{ch}-{stage}") > 0

    def get_dungeon_first_set(self, user_id: str) -> set:
        key = self._dungeon_first_key(user_id)
        return _redis_client.smembers(key)

    def is_dungeon_reset_today(self, user_id: str, ch: int) -> bool:
        key = self._dungeon_reset_key(user_id, ch)
        return _redis_client.exists(key) > 0

    def mark_dungeon_reset(self, user_id: str, ch: int) -> None:
        key = self._dungeon_reset_key(user_id, ch)
        _redis_client.set(key, "1")
        _redis_client.expire(key, 86400)

    def reset_dungeon_counts(self, user_id: str, ch: int) -> None:
        pattern = f"qqbot:dungeon:{user_id}:{ch}:*:{datetime.now().strftime('%Y%m%d')}"
        for key in _redis_client.scan_iter(match=pattern):
            _redis_client.delete(key)
