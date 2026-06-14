from src.data.models import _redis_client

KEY_INTIMACY = "qqbot:intimacy:{user_id}"
KEY_CONTRIBUTION = "qqbot:contribution:{user_id}"
KEY_TITLE = "qqbot:title:{user_id}"
KEY_TITLE_EQUIPPED = "qqbot:title:{user_id}:equipped"
KEY_TITLE_EXPIRE = "qqbot:title:{user_id}:expire:{title}"
CONTRIBUTION_SOFT_CAP = 100000


class SocialMixin:

    def _intimacy_key(self, user_id: str) -> str:
        return KEY_INTIMACY.format(user_id=user_id)

    def _contribution_key(self, user_id: str) -> str:
        return KEY_CONTRIBUTION.format(user_id=user_id)

    def _title_key(self, user_id: str) -> str:
        return KEY_TITLE.format(user_id=user_id)

    def _title_equipped_key(self, user_id: str) -> str:
        return KEY_TITLE_EQUIPPED.format(user_id=user_id)

    def _title_expire_key(self, user_id: str, title: str) -> str:
        return KEY_TITLE_EXPIRE.format(user_id=user_id, title=title)

    def get_intimacy(self, user_id: str, target_id: str) -> int:
        key = self._intimacy_key(user_id)
        val = _redis_client.hget(key, target_id)
        return int(val) if val else 0

    def add_intimacy(self, user_id: str, target_id: str, amount: int = 1) -> int:
        key = self._intimacy_key(user_id)
        _redis_client.hincrby(key, target_id, amount)
        target_key = self._intimacy_key(target_id)
        _redis_client.hincrby(target_key, user_id, amount)
        return self.get_intimacy(user_id, target_id)

    def get_all_intimacy(self, user_id: str) -> dict[str, int]:
        key = self._intimacy_key(user_id)
        data = _redis_client.hgetall(key)
        return {k: int(v) for k, v in data.items()}

    def get_contribution(self, user_id: str) -> int:
        val = _redis_client.get(self._contribution_key(user_id))
        return int(val) if val else 0

    def add_contribution(self, user_id: str, amount: int) -> int:
        key = self._contribution_key(user_id)
        current = self.get_contribution(user_id)
        if current >= CONTRIBUTION_SOFT_CAP:
            return current
        new_val = min(CONTRIBUTION_SOFT_CAP, current + amount)
        _redis_client.set(key, new_val)
        return new_val

    def use_contribution(self, user_id: str, amount: int) -> bool:
        current = self.get_contribution(user_id)
        if current < amount:
            return False
        key = self._contribution_key(user_id)
        _redis_client.decrby(key, amount)
        return True

    def add_title(self, user_id: str, title: str) -> None:
        key = self._title_key(user_id)
        _redis_client.sadd(key, title)

    def remove_title(self, user_id: str, title: str) -> None:
        key = self._title_key(user_id)
        _redis_client.srem(key, title)

    def get_titles(self, user_id: str) -> set:
        key = self._title_key(user_id)
        return _redis_client.smembers(key)

    def has_title(self, user_id: str, title: str) -> bool:
        key = self._title_key(user_id)
        return _redis_client.sismember(key, title)

    def equip_title(self, user_id: str, title: str) -> bool:
        if not self.has_title(user_id, title):
            return False
        key = self._title_equipped_key(user_id)
        _redis_client.set(key, title)
        return True

    def unequip_title(self, user_id: str) -> None:
        key = self._title_equipped_key(user_id)
        _redis_client.delete(key)

    def get_equipped_title(self, user_id: str) -> str:
        key = self._title_equipped_key(user_id)
        val = _redis_client.get(key)
        return val if val else ""

    def set_title_expire(self, user_id: str, title: str, expire_ts: float) -> None:
        key = self._title_expire_key(user_id, title)
        _redis_client.set(key, str(expire_ts))

    def get_title_expire(self, user_id: str, title: str) -> float:
        key = self._title_expire_key(user_id, title)
        val = _redis_client.get(key)
        return float(val) if val else 0.0
