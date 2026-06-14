"""
test_data_economy.py — EconomyMixin 单元测试。
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis

from src.data.economy import EconomyMixin


class Economy(EconomyMixin):
    pass


class TestGold(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        self.eco = Economy()

    def test_get_gold_default_zero(self):
        self.assertEqual(self.eco.get_gold("u1"), 0)

    def test_add_gold(self):
        self.eco.add_gold("u1", 100)
        self.assertEqual(self.eco.get_gold("u1"), 100)

    def test_use_gold_success(self):
        self.eco.add_gold("u1", 100)
        self.assertTrue(self.eco.use_gold("u1", 50))
        self.assertEqual(self.eco.get_gold("u1"), 50)

    def test_use_gold_insufficient(self):
        self.eco.add_gold("u1", 30)
        self.assertFalse(self.eco.use_gold("u1", 50))
        self.assertEqual(self.eco.get_gold("u1"), 30)


class TestDiamond(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        self.eco = Economy()

    def test_get_diamond_default_zero(self):
        self.assertEqual(self.eco.get_diamond("u1"), 0)

    def test_add_diamond(self):
        self.eco.add_diamond("u1", 10)
        self.assertEqual(self.eco.get_diamond("u1"), 10)

    def test_use_diamond_success(self):
        self.eco.add_diamond("u1", 10)
        self.assertTrue(self.eco.use_diamond("u1", 5))
        self.assertEqual(self.eco.get_diamond("u1"), 5)

    def test_use_diamond_insufficient(self):
        self.eco.add_diamond("u1", 3)
        self.assertFalse(self.eco.use_diamond("u1", 5))


class TestItems(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        self.eco = Economy()

    def test_get_item_default_zero(self):
        self.assertEqual(self.eco.get_item("u1", "potion_s"), 0)

    def test_add_item(self):
        self.eco.add_item("u1", "potion_s", 5)
        self.assertEqual(self.eco.get_item("u1", "potion_s"), 5)

    def test_use_item_success(self):
        self.eco.add_item("u1", "potion_s", 5)
        self.assertTrue(self.eco.use_item("u1", "potion_s", 2))
        self.assertEqual(self.eco.get_item("u1", "potion_s"), 3)

    def test_use_item_insufficient(self):
        self.eco.add_item("u1", "potion_s", 1)
        self.assertFalse(self.eco.use_item("u1", "potion_s", 2))

    def test_get_all_items(self):
        self.eco.add_item("u1", "potion_s", 5)
        self.eco.add_item("u1", "potion_m", 2)
        items = self.eco.get_all_items("u1")
        self.assertEqual(items["potion_s"], 5)
        self.assertEqual(items["potion_m"], 2)

    def test_add_item_accumulates(self):
        self.eco.add_item("u1", "stone", 3)
        self.eco.add_item("u1", "stone", 2)
        self.assertEqual(self.eco.get_item("u1", "stone"), 5)


if __name__ == "__main__":
    unittest.main()
