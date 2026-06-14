"""
test_interaction.py — 互动系统测试。
"""
import sys
import unittest
from unittest.mock import MagicMock

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet


class InteractTestBase(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", game_uid=1):
        pet = make_test_pet(user_id=user_id, level=10)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )
        self.game.dm.assign_game_uid(user_id)

    def _setup_two_pets(self):
        self._setup_pet("u1")
        self._setup_pet("u2")


class TestFeed(InteractTestBase):

    def test_feed_no_pet(self):
        result = self.game.feed("u1", arg="1")
        self.assertIn("还没有宠物", result)

    def test_feed_no_target(self):
        self._setup_pet("u1")
        result = self.game.feed("u1", arg="")
        self.assertIn("正确的游戏用户 ID", result)

    def test_feed_self(self):
        self._setup_pet("u1")
        result = self.game.feed("u1", arg="1")
        self.assertIn("不能对自己", result)

    def test_feed_success(self):
        self._setup_two_pets()
        result = self.game.feed("u1", arg="2")
        self.assertIn("喂食成功", result)
        self.assertIn("经验", result)

    def test_feed_cooldown(self):
        self._setup_two_pets()
        self.game.feed("u1", arg="2")
        result = self.game.feed("u1", arg="2")
        self.assertIn("冷却中", result)


class TestIntimacy(InteractTestBase):

    def test_intimacy_increases(self):
        self._setup_two_pets()
        self.game.feed("u1", arg="2")
        intimacy = self.game.dm.get_intimacy("u1", "u2")
        self.assertEqual(intimacy, 1)

    def test_intimacy_bidirectional(self):
        self._setup_two_pets()
        self.game.feed("u1", arg="2")
        intimacy_u2 = self.game.dm.get_intimacy("u2", "u1")
        self.assertEqual(intimacy_u2, 1)

    def test_intimacy_list_empty(self):
        self._setup_pet("u1")
        result = self.game.intimacy_list("u1")
        self.assertIn("还没有亲密度记录", result)

    def test_intimacy_list_shows(self):
        self._setup_two_pets()
        self.game.feed("u1", arg="2")
        result = self.game.intimacy_list("u1")
        self.assertIn("亲密度列表", result)


class TestGroupTrain(InteractTestBase):

    def test_group_train_no_group(self):
        self._setup_pet("u1")
        result = self.game.group_train("u1", group_id="")
        self.assertIn("群聊中使用", result)

    def test_group_train_success(self):
        self._setup_pet("u1")
        result = self.game.group_train("u1", group_id="g1")
        self.assertIn("群训练完成", result)

    def test_group_train_cooldown(self):
        self._setup_pet("u1")
        self.game.group_train("u1", group_id="g1")
        result = self.game.group_train("u1", group_id="g1")
        self.assertIn("冷却中", result)


if __name__ == "__main__":
    unittest.main()
