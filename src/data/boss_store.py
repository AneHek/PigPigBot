from datetime import datetime

from src.data.models import _redis_client

KEY_BOSS_DMG = "qqbot:boss:{boss_id}:{date}:dmg"
KEY_BOSS_HP = "qqbot:boss:{boss_id}:{date}:hp"
KEY_BOSS_CLAIMED = "qqbot:boss:{boss_id}:{date}:claimed"
KEY_BOSS_LAST_KILL = "qqbot:boss:{boss_id}:{date}:last_kill"
KEY_BOSS_KILL_COUNT = "qqbot:boss:{boss_id}:{date}:kill_count:{user_id}"


class BossMixin:

    def _boss_dmg_key(self, boss_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_BOSS_DMG.format(boss_id=boss_id, date=date)

    def _boss_hp_key(self, boss_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_BOSS_HP.format(boss_id=boss_id, date=date)

    def _boss_claimed_key(self, boss_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_BOSS_CLAIMED.format(boss_id=boss_id, date=date)

    def _boss_last_kill_key(self, boss_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_BOSS_LAST_KILL.format(boss_id=boss_id, date=date)

    def add_boss_damage(self, boss_id: str, user_id: str, damage: float) -> None:
        key = self._boss_dmg_key(boss_id)
        _redis_client.zincrby(key, damage, user_id)
        _redis_client.expire(key, 86400)

    def get_boss_damage(self, boss_id: str, user_id: str) -> float:
        key = self._boss_dmg_key(boss_id)
        val = _redis_client.zscore(key, user_id)
        return float(val) if val else 0.0

    def get_boss_rank(self, boss_id: str, top_n: int = 10) -> list[tuple[str, float]]:
        key = self._boss_dmg_key(boss_id)
        return _redis_client.zrevrange(key, 0, top_n - 1, withscores=True)

    def get_boss_rank_count(self, boss_id: str) -> int:
        key = self._boss_dmg_key(boss_id)
        return _redis_client.zcard(key)

    def get_boss_hp(self, boss_id: str) -> int:
        key = self._boss_hp_key(boss_id)
        val = _redis_client.get(key)
        return int(val) if val else 0

    def set_boss_hp(self, boss_id: str, hp: int) -> None:
        key = self._boss_hp_key(boss_id)
        _redis_client.set(key, hp)
        _redis_client.expire(key, 1800)

    def decr_boss_hp(self, boss_id: str, damage: float) -> int:
        key = self._boss_hp_key(boss_id)
        current = self.get_boss_hp(boss_id)
        new_hp = max(0, current - int(damage))
        _redis_client.set(key, new_hp)
        _redis_client.expire(key, 1800)
        return new_hp

    def is_boss_claimed(self, boss_id: str, user_id: str) -> bool:
        key = self._boss_claimed_key(boss_id)
        return _redis_client.sismember(key, user_id)

    def mark_boss_claimed(self, boss_id: str, user_id: str) -> None:
        key = self._boss_claimed_key(boss_id)
        _redis_client.sadd(key, user_id)
        _redis_client.expire(key, 86400)

    def set_boss_last_kill(self, boss_id: str, user_id: str) -> None:
        key = self._boss_last_kill_key(boss_id)
        _redis_client.set(key, user_id)
        _redis_client.expire(key, 86400)

    def get_boss_last_kill(self, boss_id: str) -> str | None:
        key = self._boss_last_kill_key(boss_id)
        return _redis_client.get(key)
