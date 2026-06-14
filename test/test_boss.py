"""
test_boss.py — 世界 Boss 系统测试。
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet


class BossTestBase(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", level=30):
        pet = make_test_pet(user_id=user_id, level=level)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )


class TestBossStatus(BossTestBase):

    def test_status_no_active_boss(self):
        result = self.game.boss("u1", arg="")
        self.assertIn("没有活跃的", result)
        self.assertIn("时间表", result)

    @patch("src.game.boss.get_active_boss")
    def test_status_with_active_boss(self, mock_active):
        mock_active.return_value = ("time_demon", {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 30,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        })
        result = self.game.boss("u1", arg="")
        self.assertIn("时间魔王猪", result)


class TestBossRank(BossTestBase):

    @patch("src.game.boss.get_active_boss")
    def test_rank_no_active(self, mock_active):
        mock_active.return_value = None
        result = self.game.boss("u1", arg="排行")
        self.assertIn("没有活跃", result)

    @patch("src.game.boss.get_active_boss")
    def test_rank_empty(self, mock_active):
        mock_active.return_value = ("time_demon", {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 30,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        })
        result = self.game.boss("u1", arg="排行")
        self.assertIn("暂无参与者", result)


class TestBossClaim(BossTestBase):

    def test_claim_no_pet(self):
        result = self.game.boss("u1", arg="奖励")
        self.assertIn("还没有宠物", result)

    @patch("src.game.boss.get_active_boss")
    def test_claim_no_active(self, mock_active):
        mock_active.return_value = None
        self._setup_pet()
        result = self.game.boss("u1", arg="奖励")
        self.assertIn("没有活跃", result)

    @patch("src.game.boss.get_active_boss")
    def test_claim_not_participated(self, mock_active):
        mock_active.return_value = ("time_demon", {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 30,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        })
        self._setup_pet()
        result = self.game.boss("u1", arg="奖励")
        self.assertIn("未参与", result)


class TestBossAttack(BossTestBase):

    def test_attack_no_pet(self):
        result = self.game.boss("u1", arg="攻击")
        self.assertIn("还没有宠物", result)

    @patch("src.game.boss.get_active_boss")
    def test_attack_no_active(self, mock_active):
        mock_active.return_value = None
        self._setup_pet()
        result = self.game.boss("u1", arg="攻击")
        self.assertIn("没有活跃", result)

    @patch("src.game.boss.get_active_boss")
    def test_attack_energy_insufficient(self, mock_active):
        mock_active.return_value = ("time_demon", {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 30,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        })
        self._setup_pet()
        self.game.dm.use_energy("u1", 90)
        result = self.game.boss("u1", arg="攻击")
        self.assertIn("行动力不足", result)


if __name__ == "__main__":
    unittest.main()
