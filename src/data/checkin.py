from datetime import datetime

from src.data.models import _redis_client

KEY_CHECKIN = "qqbot:checkin:{user_id}:{date}"
KEY_CHECKIN_STREAK = "qqbot:checkin:{user_id}:streak"
KEY_CHECKIN_LAST = "qqbot:checkin:{user_id}:last_date"


class CheckinMixin:

    def _checkin_key(self, user_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_CHECKIN.format(user_id=user_id, date=date)

    def _streak_key(self, user_id: str) -> str:
        return KEY_CHECKIN_STREAK.format(user_id=user_id)

    def _last_date_key(self, user_id: str) -> str:
        return KEY_CHECKIN_LAST.format(user_id=user_id)

    def is_checked_in_today(self, user_id: str) -> bool:
        key = self._checkin_key(user_id)
        return _redis_client.exists(key) > 0

    def do_checkin(self, user_id: str) -> int:
        if self.is_checked_in_today(user_id):
            return -1

        today = datetime.now().strftime("%Y%m%d")
        last_date_val = _redis_client.get(self._last_date_key(user_id))

        streak_key = self._streak_key(user_id)
        if last_date_val:
            last_date = datetime.strptime(last_date_val, "%Y%m%d")
            today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            diff = (today_date - last_date).days
            if diff == 1:
                _redis_client.incr(streak_key)
            elif diff > 1:
                _redis_client.set(streak_key, 1)
        else:
            _redis_client.set(streak_key, 1)

        checkin_key = self._checkin_key(user_id)
        _redis_client.set(checkin_key, "1")
        _redis_client.expire(checkin_key, 86400)

        _redis_client.set(self._last_date_key(user_id), today)

        streak = int(_redis_client.get(streak_key) or 1)
        return streak

    def get_streak(self, user_id: str) -> int:
        val = _redis_client.get(self._streak_key(user_id))
        return int(val) if val else 0
