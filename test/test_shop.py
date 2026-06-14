"""
test_shop.py — 商店、购买、使用、背包命令测试。
"""
import sys
import unittest
from unittest.mock import MagicMock

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet


class ShopTestBase(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", level=10):
        pet = make_test_pet(user_id=user_id, level=level)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )


class TestShopMenu(ShopTestBase):

    def test_shop_no_pet(self):
        result = self.game.shop_menu("u1")
        self.assertIn("还没有宠物", result)

    def test_shop_shows_items(self):
        self._setup_pet()
        result = self.game.shop_menu("u1")
        self.assertIn("金币商店", result)
        self.assertIn("钻石商店", result)
        self.assertIn("经验药水", result)


class TestShopBuy(ShopTestBase):

    def test_buy_no_arg(self):
        self._setup_pet()
        result = self.game.shop_buy("u1", arg="")
        self.assertIn("指定商品", result)

    def test_buy_invalid_item(self):
        self._setup_pet()
        result = self.game.shop_buy("u1", arg="不存在的商品")
        self.assertIn("不存在", result)

    def test_buy_gold_success(self):
        self._setup_pet()
        self.game.dm.add_gold("u1", 10000)
        result = self.game.shop_buy("u1", arg="经验药水小 2")
        self.assertIn("购买成功", result)
        self.assertEqual(self.game.dm.get_item("u1", "potion_s"), 2)

    def test_buy_gold_insufficient(self):
        self._setup_pet()
        result = self.game.shop_buy("u1", arg="经验药水小 1")
        self.assertIn("金币不足", result)

    def test_buy_daily_limit(self):
        self._setup_pet()
        self.game.dm.add_gold("u1", 100000)
        self.game.dm.incr_shop_buy("u1", "potion_l", 1)
        result = self.game.shop_buy("u1", arg="经验药水大 1")
        self.assertIn("限购", result)


class TestUseItem(ShopTestBase):

    def test_use_no_arg(self):
        self._setup_pet()
        result = self.game.use_item_cmd("u1", arg="")
        self.assertIn("指定物品", result)

    def test_use_no_item(self):
        self._setup_pet()
        result = self.game.use_item_cmd("u1", arg="经验药水小")
        self.assertIn("没有该物品", result)

    def test_use_exp_potion(self):
        self._setup_pet()
        self.game.dm.add_item("u1", "potion_s", 5)
        result = self.game.use_item_cmd("u1", arg="经验药水小 2")
        self.assertIn("使用", result)
        self.assertIn("经验", result)
        self.assertEqual(self.game.dm.get_item("u1", "potion_s"), 3)

    def test_use_energy_potion(self):
        self._setup_pet()
        self.game.dm.add_item("u1", "energy_potion", 3)
        self.game.dm.use_energy("u1", 50)
        result = self.game.use_item_cmd("u1", arg="行动力药水 1")
        self.assertIn("行动力", result)

    def test_use_daily_limit(self):
        self._setup_pet()
        self.game.dm.add_item("u1", "potion_l", 10)
        self.game.dm.incr_use_item("u1", "potion_l", 5)
        result = self.game.use_item_cmd("u1", arg="经验药水大 1")
        self.assertIn("使用次数已达上限", result)


class TestBag(ShopTestBase):

    def test_bag_no_pet(self):
        result = self.game.bag_list("u1")
        self.assertIn("还没有宠物", result)

    def test_bag_empty(self):
        self._setup_pet()
        result = self.game.bag_list("u1")
        self.assertIn("空空如也", result)

    def test_bag_shows_items(self):
        self._setup_pet()
        self.game.dm.add_item("u1", "potion_s", 5)
        self.game.dm.add_item("u1", "potion_m", 2)
        result = self.game.bag_list("u1")
        self.assertIn("经验药水(小)", result)
        self.assertIn("×5", result)
        self.assertIn("经验药水(中)", result)
        self.assertIn("×2", result)


if __name__ == "__main__":
    unittest.main()
