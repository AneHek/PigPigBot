from datetime import datetime

from src.data.models import _redis_client

KEY_GOLD = "qqbot:gold:{user_id}"
KEY_DIAMOND = "qqbot:diamond:{user_id}"
KEY_ITEM = "qqbot:item:{user_id}:{item_id}"
KEY_SHOP_BUY = "qqbot:shop_buy:{user_id}:{item}:{date}"
KEY_USE_ITEM = "qqbot:use_item:{user_id}:{item}:{date}"


class EconomyMixin:

    def _gold_key(self, user_id: str) -> str:
        return KEY_GOLD.format(user_id=user_id)

    def _diamond_key(self, user_id: str) -> str:
        return KEY_DIAMOND.format(user_id=user_id)

    def _item_key(self, user_id: str, item_id: str) -> str:
        return KEY_ITEM.format(user_id=user_id, item_id=item_id)

    def get_gold(self, user_id: str) -> int:
        val = _redis_client.get(self._gold_key(user_id))
        return int(val) if val else 0

    def add_gold(self, user_id: str, amount: int) -> int:
        key = self._gold_key(user_id)
        return _redis_client.incrby(key, amount)

    def use_gold(self, user_id: str, amount: int) -> bool:
        current = self.get_gold(user_id)
        if current < amount:
            return False
        key = self._gold_key(user_id)
        _redis_client.decrby(key, amount)
        return True

    def get_diamond(self, user_id: str) -> int:
        val = _redis_client.get(self._diamond_key(user_id))
        return int(val) if val else 0

    def add_diamond(self, user_id: str, amount: int) -> int:
        key = self._diamond_key(user_id)
        return _redis_client.incrby(key, amount)

    def use_diamond(self, user_id: str, amount: int) -> bool:
        current = self.get_diamond(user_id)
        if current < amount:
            return False
        key = self._diamond_key(user_id)
        _redis_client.decrby(key, amount)
        return True

    def add_item(self, user_id: str, item_id: str, amount: int = 1) -> int:
        key = self._item_key(user_id, item_id)
        return _redis_client.incrby(key, amount)

    def get_item(self, user_id: str, item_id: str) -> int:
        val = _redis_client.get(self._item_key(user_id, item_id))
        return int(val) if val else 0

    def use_item(self, user_id: str, item_id: str, amount: int = 1) -> bool:
        current = self.get_item(user_id, item_id)
        if current < amount:
            return False
        key = self._item_key(user_id, item_id)
        _redis_client.decrby(key, amount)
        return True

    def get_all_items(self, user_id: str) -> dict[str, int]:
        pattern = f"qqbot:item:{user_id}:*"
        items = {}
        for key in _redis_client.scan_iter(match=pattern):
            val = _redis_client.get(key)
            if val and int(val) > 0:
                item_id = key.split(":")[-1]
                items[item_id] = int(val)
        return items

    def _shop_buy_key(self, user_id: str, item_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_SHOP_BUY.format(user_id=user_id, item=item_id, date=date)

    def _use_item_key(self, user_id: str, item_id: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        return KEY_USE_ITEM.format(user_id=user_id, item=item_id, date=date)

    def get_shop_buy_count(self, user_id: str, item_id: str) -> int:
        val = _redis_client.get(self._shop_buy_key(user_id, item_id))
        return int(val) if val else 0

    def incr_shop_buy(self, user_id: str, item_id: str, amount: int = 1) -> int:
        key = self._shop_buy_key(user_id, item_id)
        result = _redis_client.incrby(key, amount)
        _redis_client.expire(key, 86400)
        return result

    def get_use_item_count(self, user_id: str, item_id: str) -> int:
        val = _redis_client.get(self._use_item_key(user_id, item_id))
        return int(val) if val else 0

    def incr_use_item(self, user_id: str, item_id: str, amount: int = 1) -> int:
        key = self._use_item_key(user_id, item_id)
        result = _redis_client.incrby(key, amount)
        _redis_client.expire(key, 86400)
        return result
