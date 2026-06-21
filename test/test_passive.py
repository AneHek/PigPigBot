"""
test_passive.py — 被动技能系统测试。
"""
import sys
import unittest
from unittest.mock import MagicMock

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, MOCK_CONFIG, make_test_pet


class TestPassiveStore(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.data import DataManager
        self.dm = DataManager()

    def test_slot_crud(self):
        self.dm.set_passive_slot("u1", 1, "PS_A01")
        slots = self.dm.get_passive_slots("u1")
        self.assertEqual(slots["1"], "PS_A01")

    def test_clear_slot(self):
        self.dm.set_passive_slot("u1", 1, "PS_A01")
        self.dm.clear_passive_slot("u1", 1)
        slots = self.dm.get_passive_slots("u1")
        self.assertNotIn("1", slots)

    def test_level_crud(self):
        self.assertEqual(self.dm.get_passive_level("u1", "PS_A01"), 0)
        self.dm.set_passive_level("u1", "PS_A01", 3)
        self.assertEqual(self.dm.get_passive_level("u1", "PS_A01"), 3)

    def test_bag_crud(self):
        self.assertEqual(self.dm.get_passive_bag("u1", "PS_A01"), 0)
        self.dm.add_passive_bag("u1", "PS_A01", 5)
        self.assertEqual(self.dm.get_passive_bag("u1", "PS_A01"), 5)
        self.assertTrue(self.dm.use_passive_bag("u1", "PS_A01", 3))
        self.assertEqual(self.dm.get_passive_bag("u1", "PS_A01"), 2)
        self.assertFalse(self.dm.use_passive_bag("u1", "PS_A01", 5))

    def test_reset_tracking(self):
        self.assertFalse(self.dm.is_passive_reset_today("u1", 1))
        self.dm.mark_passive_reset("u1", 1)
        self.assertTrue(self.dm.is_passive_reset_today("u1", 1))


class TestPassiveCommand(unittest.IsolatedAsyncioTestCase):

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

    def test_passive_no_pet(self):
        result = self.game.passive_cmd("u1")
        self.assertIn("还没有宠物", result)

    def test_passive_list_empty(self):
        self._setup_pet()
        result = self.game.passive_cmd("u1")
        self.assertIn("被动", result)
        self.assertIn("空", result)

    def test_passive_bag_empty(self):
        self._setup_pet()
        result = self.game.passive_cmd("u1", arg="背包")
        self.assertIn("空空如也", result)

    def test_passive_equip_from_bag(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 3)
        result = self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        self.assertIn("已装备", result)
        slots = self.game.dm.get_passive_slots("u1")
        self.assertEqual(slots["1"], "PS_A01")
        self.assertEqual(self.game.dm.get_passive_level("u1", "PS_A01"), 1)

    def test_passive_equip_duplicate_slot(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.dm.add_passive_bag("u1", "PS_D01", 1)
        self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        result = self.game.passive_cmd("u1", arg="装备 坚韧体魄 1")
        self.assertIn("已装备", result)

    def test_passive_upgrade(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 5)
        self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        result = self.game.passive_cmd("u1", arg="升级 蛮力印记")
        self.assertIn("升级成功", result)
        self.assertEqual(self.game.dm.get_passive_level("u1", "PS_A01"), 2)

    def test_passive_upgrade_insufficient(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        result = self.game.passive_cmd("u1", arg="升级 蛮力印记")
        self.assertIn("需要", result)

    def test_passive_reset(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        self.game.dm.add_diamond("u1", 10)
        result = self.game.passive_cmd("u1", arg="重置 1")
        self.assertIn("已重置", result)
        slots = self.game.dm.get_passive_slots("u1")
        self.assertNotIn("1", slots)
        self.assertEqual(self.game.dm.get_passive_bag("u1", "PS_A01"), 1)

    def test_passive_reset_no_diamond(self):
        self._setup_pet()
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.passive_cmd("u1", arg="装备 蛮力印记 1")
        result = self.game.passive_cmd("u1", arg="重置 1")
        self.assertIn("钻石不足", result)

    def test_passive_help(self):
        self._setup_pet()
        result = self.game.passive_cmd("u1", arg="xxx")
        self.assertIn("被动指令", result)


class TestPassiveBattleEffect(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.battle import battle_engine
        self.engine = battle_engine

    def _make_pet_dict(self, atk=100, hp=500, modifiers=None):
        d = {
            "owner_id": "test",
            "name": "测试猪",
            "species_id": "P001",
            "evolution_stage": 0,
            "battle_type": "attack",
            "hp": hp, "atk": atk, "def_": 20, "spd": 1.0,
            "crit": 5, "crit_dmg": 1.5, "eva": 5, "lifesteal": 0.05,
        }
        if modifiers:
            d["modifiers"] = modifiers
        return d

    def test_passive_atk_bonus(self):
        pet_a = self._make_pet_dict(
            modifiers=[{"stat": "atk", "value": 7.8, "type": "pct"}],
        )
        bp_a = self.engine._create_battle_pet(pet_a)
        mods = self.engine._collect_battle_modifiers(pet_a)
        self.engine._apply_modifiers(bp_a, mods)
        self.assertAlmostEqual(bp_a.atk, 100 * 1.078, delta=1)

    def test_passive_hp_bonus(self):
        pet_a = self._make_pet_dict(
            modifiers=[{"stat": "hp", "value": 5, "type": "pct"}],
        )
        bp_a = self.engine._create_battle_pet(pet_a)
        mods = self.engine._collect_battle_modifiers(pet_a)
        self.engine._apply_modifiers(bp_a, mods)
        self.assertAlmostEqual(bp_a.max_hp, 500 * 1.05, delta=1)

    def test_no_passive(self):
        pet_a = self._make_pet_dict()
        bp_a = self.engine._create_battle_pet(pet_a)
        mods = self.engine._collect_battle_modifiers(pet_a)
        self.engine._apply_modifiers(bp_a, mods)
        self.assertEqual(bp_a.atk, 100)
        self.assertEqual(bp_a.max_hp, 500)


class TestApplyModifiers(unittest.TestCase):

    def setUp(self):
        from src.battle import battle_engine
        self.engine = battle_engine

    def _make_bp(self, atk=100, hp=500, def_=20, spd=1.0,
                 crit=5, crit_dmg=1.5, eva=5, lifesteal=0.05):
        d = {
            "owner_id": "test", "name": "t", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": hp, "atk": atk, "def_": def_, "spd": spd,
            "crit": crit, "crit_dmg": crit_dmg, "eva": eva, "lifesteal": lifesteal,
        }
        return self.engine._create_battle_pet(d)

    def test_pct_atk(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "atk", "value": 10, "type": "pct"}])
        self.assertAlmostEqual(bp.atk, 110)

    def test_flat_atk(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "atk", "value": 20, "type": "flat"}])
        self.assertAlmostEqual(bp.atk, 120)

    def test_pct_hp(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "hp", "value": 10, "type": "pct"}])
        self.assertAlmostEqual(bp.max_hp, 550)
        self.assertAlmostEqual(bp.hp, 550)

    def test_flat_hp(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "hp", "value": 100, "type": "flat"}])
        self.assertAlmostEqual(bp.max_hp, 600)
        self.assertAlmostEqual(bp.hp, 600)

    def test_flat_crit(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "crit", "value": 5, "type": "flat"}])
        self.assertAlmostEqual(bp.crit, 10)

    def test_flat_crit_dmg(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "crit_dmg", "value": 0.1, "type": "flat"}])
        self.assertAlmostEqual(bp.crit_dmg, 1.6)

    def test_flat_lifesteal(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [{"stat": "lifesteal", "value": 0.02, "type": "flat"}])
        self.assertAlmostEqual(bp.lifesteal, 0.07)

    def test_multiple_modifiers(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [
            {"stat": "atk", "value": 10, "type": "pct"},
            {"stat": "atk", "value": 5, "type": "pct"},
            {"stat": "crit", "value": 3, "type": "flat"},
        ])
        self.assertAlmostEqual(bp.atk, 100 * 1.10 * 1.05, delta=0.1)
        self.assertAlmostEqual(bp.crit, 8)

    def test_empty_modifiers(self):
        bp = self._make_bp()
        self.engine._apply_modifiers(bp, [])
        self.assertAlmostEqual(bp.atk, 100)
        self.assertAlmostEqual(bp.max_hp, 500)


class TestBuildBattleDict(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def test_build_battle_dict_no_passives(self):
        pet = make_test_pet(user_id="u1")
        self.game.dm.create_pet(
            "u1", "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )
        stored_pet = self.game.dm.get_pet("u1")
        d = self.game._build_battle_dict("u1", stored_pet)
        self.assertNotIn("modifiers", d)
        self.assertEqual(d["owner_id"], "u1")

    def test_build_battle_dict_with_passives(self):
        pet = make_test_pet(user_id="u1")
        self.game.dm.create_pet(
            "u1", "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.dm.set_passive_slot("u1", 1, "PS_A01")
        self.game.dm.set_passive_level("u1", "PS_A01", 3)

        stored_pet = self.game.dm.get_pet("u1")
        d = self.game._build_battle_dict("u1", stored_pet)
        self.assertIn("modifiers", d)
        self.assertTrue(len(d["modifiers"]) > 0)
        atk_mod = next(m for m in d["modifiers"] if m["stat"] == "atk")
        self.assertEqual(atk_mod["type"], "pct")
        self.assertGreater(atk_mod["value"], 0)


if __name__ == "__main__":
    unittest.main()
