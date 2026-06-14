from src.data.models import _redis_client, KEY_GROUP_MEMBERS, KEY_GAME_UID_COUNTER, KEY_GAME_UID_MAP, KEY_USER_GAME_UID


class GroupMixin:

    def add_group_member(self, group_id: str, user_id: str) -> None:
        _redis_client.sadd(KEY_GROUP_MEMBERS.format(group_id=group_id), user_id)

    def get_user_game_uid(self, user_id: str) -> int:
        val = _redis_client.get(KEY_USER_GAME_UID.format(user_id=user_id))
        return int(val) if val else 0

    def assign_game_uid(self, user_id: str) -> int:
        existing = self.get_user_game_uid(user_id)
        if existing > 0:
            return existing
        game_uid = _redis_client.incr(KEY_GAME_UID_COUNTER)
        _redis_client.set(KEY_USER_GAME_UID.format(user_id=user_id), game_uid)
        _redis_client.set(KEY_GAME_UID_MAP.format(game_uid=game_uid), user_id)
        return game_uid

    def get_user_by_game_uid(self, game_uid: int) -> str | None:
        return _redis_client.get(KEY_GAME_UID_MAP.format(game_uid=game_uid))
