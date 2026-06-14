import time
from datetime import datetime

from src.data.models import _redis_client

KEY_ENERGY = "qqbot:energy:{user_id}"
ENERGY_MAX = 100
ENERGY_REGEN_INTERVAL = 180


class EnergyMixin:

    def _energy_key(self, user_id: str) -> str:
        return KEY_ENERGY.format(user_id=user_id)

    def get_energy(self, user_id: str) -> dict:
        key = self._energy_key(user_id)
        data = _redis_client.hgetall(key)
        if not data:
            now = time.time()
            _redis_client.hset(key, mapping={"value": str(ENERGY_MAX), "last_update": str(now)})
            return {"value": ENERGY_MAX, "last_update": now}

        value = int(data.get("value", ENERGY_MAX))
        last_update = float(data.get("last_update", time.time()))

        now = time.time()
        elapsed = now - last_update
        regen = int(elapsed // ENERGY_REGEN_INTERVAL)
        if regen > 0 and value < ENERGY_MAX:
            value = min(ENERGY_MAX, value + regen)
            _redis_client.hset(key, mapping={"value": str(value), "last_update": str(now)})

        return {"value": value, "last_update": last_update}

    def use_energy(self, user_id: str, amount: int) -> bool:
        energy = self.get_energy(user_id)
        if energy["value"] < amount:
            return False
        key = self._energy_key(user_id)
        new_value = energy["value"] - amount
        _redis_client.hset(key, mapping={"value": str(new_value), "last_update": str(time.time())})
        return True

    def add_energy(self, user_id: str, amount: int) -> int:
        energy = self.get_energy(user_id)
        key = self._energy_key(user_id)
        new_value = energy["value"] + amount
        _redis_client.hset(key, mapping={"value": str(new_value), "last_update": str(time.time())})
        return new_value
