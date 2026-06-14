"""
test_checkin.py — 签到和行动力命令测试。
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, MOCK_CONFIG, make_test_pet


class TestCheckin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", level=10):
        pet = make_test_pet(user_id=user_id, level=level)
        created = self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )
        if level > 1:
            self.game.dm.update_pet(user_id, level=level)

    def test_checkin_no_pet(self):
        result = self.game.checkin("u1")
        self.assertIn("还没有宠物", result)

    def test_checkin_success(self):
        self._setup_pet()
        result = self.game.checkin("u1")
        self.assertIn("签到成功", result)
        self.assertIn("金币", result)
        self.assertIn("钻石", result)

    def test_checkin_duplicate(self):
        self._setup_pet()
        self.game.checkin("u1")
        result = self.game.checkin("u1")
        self.assertIn("已签到", result)

    def test_checkin_gives_gold(self):
        self._setup_pet(level=20)
        self.game.checkin("u1")
        gold = self.game.dm.get_gold("u1")
        self.assertEqual(gold, 1000)

    def test_checkin_gives_diamond(self):
        self._setup_pet(level=20)
        self.game.checkin("u1")
        diamond = self.game.dm.get_diamond("u1")
        self.assertEqual(diamond, 5)

    def test_checkin_streak_increments(self):
        self._setup_pet()
        result1 = self.game.checkin("u1")
        self.assertIn("第 1 天", result1)


class TestEnergyStatus(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1"):
        pet = make_test_pet(user_id=user_id)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )

    def test_energy_no_pet(self):
        result = self.game.energy_status("u1")
        self.assertIn("还没有宠物", result)

    def test_energy_shows_current(self):
        self._setup_pet()
        result = self.game.energy_status("u1")
        self.assertIn("行动力", result)
        self.assertIn("100", result)

    def test_energy_after_use(self):
        self._setup_pet()
        self.game.dm.use_energy("u1", 30)
        result = self.game.energy_status("u1")
        self.assertIn("70", result)


if __name__ == "__main__":
    unittest.main()
