"""
test_title.py — 称号系统测试。
"""
import sys
import unittest
from unittest.mock import MagicMock

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet


class TitleTestBase(unittest.TestCase):

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


class TestTitleList(TitleTestBase):

    def test_list_no_pet(self):
        result = self.game.title_cmd("u1")
        self.assertIn("还没有宠物", result)

    def test_list_empty(self):
        self._setup_pet()
        result = self.game.title_cmd("u1")
        self.assertIn("暂无称号", result)

    def test_list_shows_titles(self):
        self._setup_pet()
        self.game.dm.add_title("u1", "副本征服者·1")
        result = self.game.title_cmd("u1")
        self.assertIn("副本征服者·1", result)


class TestTitleEquip(TitleTestBase):

    def test_equip_success(self):
        self._setup_pet()
        self.game.dm.add_title("u1", "进化大师")
        result = self.game.title_cmd("u1", arg="装备 进化大师")
        self.assertIn("已装备", result)

    def test_equip_not_owned(self):
        self._setup_pet()
        result = self.game.title_cmd("u1", arg="装备 不存在的称号")
        self.assertIn("不存在", result)


class TestTitleUnequip(TitleTestBase):

    def test_unequip_success(self):
        self._setup_pet()
        self.game.dm.add_title("u1", "进化大师")
        self.game.dm.equip_title("u1", "进化大师")
        result = self.game.title_cmd("u1", arg="卸下")
        self.assertIn("已卸下", result)

    def test_unequip_none(self):
        self._setup_pet()
        result = self.game.title_cmd("u1", arg="卸下")
        self.assertIn("没有装备", result)


class TestTitleBuy(TitleTestBase):

    def test_buy_success(self):
        self._setup_pet()
        self.game.dm.add_contribution("u1", 1000)
        result = self.game.title_cmd("u1", arg="购买 群聊之星")
        self.assertIn("购买称号", result)
        self.assertIn("成功", result)

    def test_buy_insufficient(self):
        self._setup_pet()
        result = self.game.title_cmd("u1", arg="购买 群聊之星")
        self.assertIn("贡献点不足", result)

    def test_buy_already_owned(self):
        self._setup_pet()
        self.game.dm.add_title("u1", "群聊之星")
        result = self.game.title_cmd("u1", arg="购买 群聊之星")
        self.assertIn("已经拥有", result)


if __name__ == "__main__":
    unittest.main()
