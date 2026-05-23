"""
test_data_manager.py - DataManager tests for new Battle Pet system.
"""
import json
import time
import unittest
import sys
from unittest.mock import patch

# ── In-Memory Redis Mock ──

class InMemoryRedis:
    _store: dict[str, str] = {}
    _hashes: dict[str, dict[str, str]] = {}
    _zsets: dict[str, dict[str, float]] = {}

    @classmethod
    def reset(cls):
        cls._store = {}
        cls._hashes = {}
        cls._zsets = {}

    def __init__(self, *args, **kwargs):
        pass

    def ping(self):
        return True

    def set(self, key: str, value: str, *args, **kwargs):
        self._store[key] = value

    def get(self, key: str):
        return self._store.get(key)

    def exists(self, key: str):
        return 1 if key in self._store else 0

    def delete(self, *keys: str):
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
            if k in self._hashes:
                del self._hashes[k]
                count += 1
            if k in self._zsets:
                del self._zsets[k]
                count += 1
        return count

    def hget(self, name: str, key: str):
        return self._hashes.get(name, {}).get(key)

    def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        if name not in self._hashes:
            self._hashes[name] = {}
        if mapping:
            self._hashes[name].update(mapping)
        elif key is not None:
            self._hashes[name][key] = value
        return 1

    def zadd(self, name: str, mapping: dict):
        if name not in self._zsets:
            self._zsets[name] = {}
        self._zsets[name].update(mapping)
        return len(mapping)

    def zrevrange(self, name: str, start: int, end: int):
        if name not in self._zsets:
            return []
        sorted_items = sorted(self._zsets[name].items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_items[start:end + 1]]

    def zrem(self, name: str, *values: str):
        if name not in self._zsets:
            return 0
        count = 0
        for v in values:
            if v in self._zsets[name]:
                del self._zsets[name][v]
                count += 1
        return count

    def scan_iter(self, match: str = None):
        prefix = match.replace("*", "") if match else ""
        for key in self._store:
            if key.startswith(prefix):
                yield key


# ── Mock config ──

MOCK_CONFIG = {
    "redis": {"host": "localhost", "port": 6379, "password": "", "db": 0},
    "image": {"dir": "data/images"},
    "game": {
        "battle": {"tick_interval": 0.1, "max_duration": 60},
        "training": {"min_lock_minutes": 10, "exp_per_level_per_minute": 50},
    },
}

# ── Patch redis and config ──

_redis_patch = patch("redis.Redis", InMemoryRedis)
_redis_patch.start()

import src.data_manager as dm_module
dm_module.config = MOCK_CONFIG
dm_module._redis_client = InMemoryRedis()

from src.data_manager import DataManager, Pet, data_manager, KEY_LEADERBOARD
from src.pet_stats import generate_ivs, calc_stats


def make_test_pet(user_id="user001", user_name="测试", species_id="P001",
                  level=1, exp=0, stage=0, battle_type="attack"):
    """Create a test Pet object directly."""
    ivs = generate_ivs()
    # Use fixed IVs for deterministic tests
    fixed_ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
    stats = calc_stats(species_id, stage, level, fixed_ivs)
    return Pet(
        owner_id=user_id, owner_name=user_name, name="测试猪",
        level=level, exp=exp,
        species_id=species_id, evolution_stage=stage, battle_type=battle_type,
        **fixed_ivs, **stats,
    )


class TestDataManagerBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dm = DataManager()

    def setUp(self):
        InMemoryRedis.reset()


class TestPetModel(unittest.TestCase):
    """Test new Pet dataclass."""

    def test_max_exp_new_formula(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t")
        self.assertEqual(pet.max_exp, 600)  # 100*1*(1+5)
        pet.level = 10
        self.assertEqual(pet.max_exp, 15000)  # 100*10*15
        pet.level = 100
        self.assertEqual(pet.max_exp, 1050000)  # 100*100*105

    def test_iv_dict_property(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t",
                  iv_hp=20, iv_atk=15, iv_def=10, iv_spd=25, iv_crit=5, iv_eva=31)
        self.assertEqual(pet.iv_dict["iv_hp"], 20)
        self.assertEqual(pet.iv_dict["iv_eva"], 31)

    def test_quality(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t",
                  iv_hp=25, iv_atk=25, iv_def=25, iv_spd=25, iv_crit=25, iv_eva=25)
        self.assertEqual(pet.iv_sum, 150)
        self.assertEqual(pet.quality, "A")

    def test_to_dict_from_dict_roundtrip(self):
        pet = Pet(owner_id="user001", owner_name="张三", name="小猪",
                  species_id="P001", battle_type="attack", level=5, exp=120,
                  iv_hp=20, iv_atk=15, hp=800, atk=100, def_=50)
        d = pet.to_dict()
        pet2 = Pet.from_dict(d)
        self.assertEqual(pet2.owner_id, "user001")
        self.assertEqual(pet2.name, "小猪")
        self.assertEqual(pet2.species_id, "P001")
        self.assertEqual(pet2.battle_type, "attack")
        self.assertEqual(pet2.level, 5)
        self.assertEqual(pet2.exp, 120)
        self.assertEqual(pet2.iv_hp, 20)
        self.assertEqual(pet2.hp, 800)

    def test_from_dict_filters_unknown_keys(self):
        """Old pet data with removed fields should not crash from_dict."""
        old_data = {
            "owner_id": "u1", "owner_name": "n", "name": "t",
            "species_id": "P001", "level": 10, "exp": 500,
            "satiety": 70, "mood": 80, "health": 90, "energy": 60,  # deprecated
            "coins": 100, "emoji": "🐱", "pet_type": "cat",  # deprecated
        }
        pet = Pet.from_dict(old_data)
        self.assertEqual(pet.owner_id, "u1")
        self.assertEqual(pet.level, 10)
        self.assertEqual(pet.exp, 500)
        # Deprecated fields ignored silently
        self.assertFalse(hasattr(pet, 'satiety'))


class TestPetCreation(TestDataManagerBase):
    def test_create_pet_and_retrieve(self):
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        pet = self.dm.create_pet("user001", "张三", "P001", "小混沌",
                                 "attack", ivs, stats)

        self.assertEqual(pet.owner_id, "user001")
        self.assertEqual(pet.name, "小混沌")
        self.assertEqual(pet.species_id, "P001")
        self.assertEqual(pet.battle_type, "attack")
        self.assertEqual(pet.evolution_stage, 0)
        self.assertEqual(pet.level, 1)
        self.assertEqual(pet.exp, 0)

        retrieved = self.dm.get_pet("user001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "小混沌")

    def test_has_pet(self):
        self.assertFalse(self.dm.has_pet("user001"))
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)
        self.assertTrue(self.dm.has_pet("user001"))

    def test_delete_pet(self):
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        pet = self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)
        self.dm.update_leaderboard(pet)
        self.assertTrue(self.dm.delete_pet("user001"))
        self.assertFalse(self.dm.has_pet("user001"))


class TestExpAndLevelUp(TestDataManagerBase):
    def setUp(self):
        super().setUp()
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)

    def test_add_exp_persists(self):
        self.dm.add_exp("user001", 500)
        pet = self.dm.get_pet("user001")
        self.assertEqual(pet.exp, 500)

    def test_no_level_up_insufficient(self):
        pet = self.dm.add_exp("user001", 500)
        self.assertEqual(pet.level, 1)
        self.assertEqual(pet.exp, 500)

    def test_exact_level_up(self):
        pet = self.dm.add_exp("user001", 600)  # Lv1 max_exp = 600
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.exp, 0)

    def test_overflow_exp(self):
        pet = self.dm.add_exp("user001", 650)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.exp, 50)

    def test_chain_level_up(self):
        # Lv1→600, Lv2: 100*2*7=1400, Lv3: 100*3*8=2400
        # Total to Lv4: 600+1400+2400 = 4400
        pet = self.dm.add_exp("user001", 4400)
        self.assertEqual(pet.level, 4)
        self.assertEqual(pet.exp, 0)

    def test_evolution_gate_stage0(self):
        """At stage 0, level caps at 29 regardless of exp."""
        pet = self.dm.add_exp("user001", 999999)
        self.assertEqual(pet.evolution_stage, 0)
        self.assertEqual(pet.level, 29)
        self.assertLess(pet.exp, pet.max_exp)

    def test_level_up_recalculates_stats(self):
        """After level up, stats should increase."""
        pet_before = self.dm.get_pet("user001")
        old_atk = pet_before.atk
        pet_after = self.dm.add_exp("user001", 4400)
        self.assertGreater(pet_after.atk, old_atk)


class TestEvolution(TestDataManagerBase):
    def setUp(self):
        super().setUp()
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)

    def test_evolve_not_at_gate(self):
        """Cannot evolve if not at gate level."""
        result = self.dm.evolve_pet("user001")
        self.assertIsNone(result)

    def test_evolve_at_gate(self):
        """Evolve from stage 0 to stage 1 at Lv29."""
        # Push to Lv29 gate
        self.dm.add_exp("user001", 999999)
        pet = self.dm.get_pet("user001")
        self.assertEqual(pet.level, 29)

        result = self.dm.evolve_pet("user001")
        self.assertIsNotNone(result)
        self.assertEqual(result.evolution_stage, 1)
        self.assertEqual(result.level, 30)  # +1 from gate

    def test_evolve_increases_fixed_stats(self):
        """Evolution boosts crit_dmg and lifesteal."""
        self.dm.add_exp("user001", 999999)
        old_pet = self.dm.get_pet("user001")
        old_crit_dmg = old_pet.crit_dmg
        old_lifesteal = old_pet.lifesteal

        result = self.dm.evolve_pet("user001")
        self.assertEqual(result.crit_dmg, 1.6)  # 150% → 160%
        self.assertEqual(result.lifesteal, 0.08)  # 5% → 8%


class TestTraining(TestDataManagerBase):
    def setUp(self):
        super().setUp()
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)

    def test_start_training(self):
        pet = self.dm.start_training("user001")
        self.assertIsNotNone(pet)
        self.assertTrue(pet.training)
        self.assertGreater(pet.training_start, 0)

    def test_cannot_start_twice(self):
        self.dm.start_training("user001")
        result = self.dm.start_training("user001")
        self.assertIsNone(result)

    def test_end_training_too_early(self):
        self.dm.start_training("user001")
        result, exp = self.dm.end_training("user001")
        self.assertIsNone(result)
        self.assertEqual(exp, -1)  # -1 = too early

    def test_end_training_grants_exp(self):
        self.dm.start_training("user001")
        # Manually set training_start to 11 minutes ago
        pet = self.dm.get_pet("user001")
        pet.training_start = time.time() - 660  # 11 minutes
        import src.data_manager as dm_mod
        dm_mod._redis_client.set(
            self.dm._pet_key("user001"),
            json.dumps(pet.to_dict(), ensure_ascii=False),
        )

        result, exp_gained = self.dm.end_training("user001")
        self.assertIsNotNone(result)
        self.assertFalse(result.training)
        self.assertGreater(exp_gained, 0)
        self.assertGreater(result.exp, 0)


class TestLeaderboard(TestDataManagerBase):
    def test_leaderboard_has_species(self):
        ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        stats = calc_stats("P001", 0, 1, ivs)
        pet = self.dm.create_pet("user001", "张三", "P001", "猪", "attack", ivs, stats)
        self.dm.update_leaderboard(pet)

        board = self.dm.get_leaderboard(10)
        self.assertEqual(len(board), 1)
        self.assertIn("species_name", board[0])
        self.assertIn("evolution_stage", board[0])
        self.assertIn("quality", board[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
