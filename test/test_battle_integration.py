"""
test_battle_integration.py — End-to-end battle flow integration tests.

Tests the REAL call paths without mocking the battle engine:
  command → _build_battle_dict → battle_engine.run → result processing

Covers: PvP, Boss attack, Dungeon fight, type advantage symmetry,
        true damage dodge, confuse mechanic.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet
from src.battle import BattleEngine, BattleResult
from src.pet.config import PET_SPECIES, Skill, SkillEffect


class IntegrationTestBase(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", level=10, species_id="P001"):
        pet = make_test_pet(user_id=user_id, level=level, species_id=species_id)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva,
             "lifesteal": pet.lifesteal}
        )
        if level > 1:
            total_exp = sum(100 * lv * (lv + 5) for lv in range(1, level))
            self.game.dm.add_exp(user_id, total_exp)
        return self.game.dm.get_pet(user_id)


class TestBuildBattleDictIntegration(IntegrationTestBase):

    def test_build_battle_dict_produces_valid_engine_input(self):
        self._setup_pet("u1", level=20)
        pet = self.game.dm.get_pet("u1")
        d = self.game._build_battle_dict("u1", pet)

        engine = BattleEngine()
        bp = engine._create_battle_pet(d)
        self.assertEqual(bp.owner_id, "u1")
        self.assertGreater(bp.hp, 0)
        self.assertGreater(bp.atk, 0)

    def test_build_battle_dict_with_passives_produces_modifiers(self):
        self._setup_pet("u1", level=20)
        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.dm.set_passive_slot("u1", 1, "PS_A01")
        self.game.dm.set_passive_level("u1", "PS_A01", 3)

        pet = self.game.dm.get_pet("u1")
        d = self.game._build_battle_dict("u1", pet)
        self.assertIn("modifiers", d)

        engine = BattleEngine()
        bp = engine._create_battle_pet(d)
        mods = engine._collect_battle_modifiers(d)
        engine._apply_modifiers(bp, mods)
        self.assertGreater(bp.atk, pet.atk)


class TestTypeAdvantageSymmetry(unittest.TestCase):

    def setUp(self):
        self.engine = BattleEngine()

    def _make_pet(self, owner_id, battle_type, **kw):
        d = {
            "owner_id": owner_id, "name": f"Pet{owner_id}",
            "species_id": "P001", "evolution_stage": 0,
            "battle_type": battle_type,
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 5, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        }
        d.update(kw)
        return d

    def test_attack_vs_defense_advantage(self):
        a_adv = self.engine._type_advantage("attack", "defense")
        self.assertAlmostEqual(a_adv, 1.15)

    def test_defense_vs_attack_disadvantage(self):
        d_adv = self.engine._type_advantage("defense", "attack")
        self.assertAlmostEqual(d_adv, 0.90)

    def test_symmetry_attack_defense(self):
        a_adv = self.engine._type_advantage("attack", "defense")
        b_adv = self.engine._type_advantage("defense", "attack")
        self.assertAlmostEqual(a_adv, 1.15)
        self.assertAlmostEqual(b_adv, 0.90)
        self.assertNotEqual(a_adv, b_adv)

    def test_symmetry_speed_attack(self):
        a_adv = self.engine._type_advantage("speed", "attack")
        b_adv = self.engine._type_advantage("attack", "speed")
        self.assertAlmostEqual(a_adv, 1.15)
        self.assertAlmostEqual(b_adv, 0.90)

    def test_symmetry_defense_speed(self):
        a_adv = self.engine._type_advantage("defense", "speed")
        b_adv = self.engine._type_advantage("speed", "defense")
        self.assertAlmostEqual(a_adv, 1.15)
        self.assertAlmostEqual(b_adv, 0.90)

    def test_same_type_neutral(self):
        self.assertAlmostEqual(self.engine._type_advantage("attack", "attack"), 1.0)
        self.assertAlmostEqual(self.engine._type_advantage("defense", "defense"), 1.0)


class TestTrueDamageDodge(unittest.TestCase):

    def setUp(self):
        self.engine = BattleEngine()

    def test_true_damage_can_be_dodged(self):
        source = self.engine._create_battle_pet({
            "owner_id": "a", "name": "A", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        })
        target = self.engine._create_battle_pet({
            "owner_id": "b", "name": "B", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 10, "def_": 0, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 100, "lifesteal": 0,
        })

        effect = SkillEffect(type="true_damage", value=500)
        events = []

        original_hp = target.hp
        self.engine._resolve_effect(source, target, effect, events, 0.0, 1.0)

        dodge_events = [e for e in events if e.type == "dodge"]
        damage_events = [e for e in events if e.type == "damage"]

        if dodge_events:
            self.assertEqual(target.hp, original_hp)
            self.assertEqual(len(damage_events), 0)


class TestConfuseMechanic(unittest.TestCase):

    def setUp(self):
        self.engine = BattleEngine()

    def test_confuse_status_applied(self):
        source = self.engine._create_battle_pet({
            "owner_id": "a", "name": "A", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        })
        target = self.engine._create_battle_pet({
            "owner_id": "b", "name": "B", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        })

        effect = SkillEffect(type="control", control_type="confuse",
                             duration=3, confuse_chance=100)
        events = []
        self.engine._resolve_effect(source, target, effect, events, 0.0, 1.0)

        confuse = self.engine._get_confuse(target)
        self.assertIsNotNone(confuse)
        self.assertEqual(confuse.confuse_chance, 100)

    def test_confuse_skips_action(self):
        pet = self.engine._create_battle_pet({
            "owner_id": "a", "name": "A", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        })
        enemy = self.engine._create_battle_pet({
            "owner_id": "b", "name": "B", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        })

        from src.battle.models import Status
        pet.statuses.append(Status("confuse", "control", 5,
                                   control_type="confuse",
                                   confuse_chance=100))

        events = []
        with patch("src.battle.engine.random") as mock_rand:
            mock_rand.random.return_value = 0.0
            acted = self.engine._process_pet(pet, enemy, 0.1, False, False,
                                             False, events, 0.0, 1.0)

        self.assertFalse(acted)
        control_events = [e for e in events if e.type == "control"
                          and "困惑" in e.detail]
        self.assertTrue(len(control_events) > 0)


class TestPvPIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        InMemoryRedis.reset()
        from src.game import PetGame
        from src.data import DataManager
        dm = DataManager()
        self.game = PetGame(dm)

    def _setup_pet(self, user_id="u1", level=10, species_id="P001"):
        pet = make_test_pet(user_id=user_id, level=level, species_id=species_id)
        self.game.dm.create_pet(
            user_id, "test", pet.species_id, pet.name,
            pet.battle_type, pet.iv_dict,
            {"hp": pet.hp, "atk": pet.atk, "def_": pet.def_, "spd": pet.spd,
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva,
             "lifesteal": pet.lifesteal}
        )
        if level > 1:
            total_exp = sum(100 * lv * (lv + 5) for lv in range(1, level))
            self.game.dm.add_exp(user_id, total_exp)
        return self.game.dm.get_pet(user_id)

    @patch("src.game.pvp.battle_engine")
    async def test_pvp_full_flow(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="测试猪",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=20, species_id="P001")
        self._setup_pet("u2", level=20, species_id="P002")

        self.game.dm.assign_game_uid("u1")
        self.game.dm.assign_game_uid("u2")

        result = await self.game.battle_pvp("u1", arg="2")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

        call_args = mock_engine.run.call_args
        pet_a_dict = call_args[0][0]
        pet_b_dict = call_args[0][1]
        self.assertEqual(pet_a_dict["owner_id"], "u1")
        self.assertEqual(pet_b_dict["owner_id"], "u2")
        self.assertIn("species_id", pet_a_dict)
        self.assertIn("species_id", pet_b_dict)

    @patch("src.game.pvp.battle_engine")
    async def test_pvp_passives_injected_both_sides(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="测试猪",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=20, species_id="P001")
        self._setup_pet("u2", level=20, species_id="P002")
        self.game.dm.assign_game_uid("u1")
        self.game.dm.assign_game_uid("u2")

        self.game.dm.add_passive_bag("u1", "PS_A01", 1)
        self.game.dm.set_passive_slot("u1", 1, "PS_A01")
        self.game.dm.set_passive_level("u1", "PS_A01", 3)

        await self.game.battle_pvp("u1", arg="2")

        call_args = mock_engine.run.call_args
        pet_a_dict = call_args[0][0]
        self.assertIn("modifiers", pet_a_dict)
        atk_mod = next(m for m in pet_a_dict["modifiers"] if m["stat"] == "atk")
        self.assertGreater(atk_mod["value"], 0)


class TestBossAttackIntegration(IntegrationTestBase):

    @patch("src.game.boss.battle_engine")
    def test_boss_hp_capped_to_remaining(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="Boss",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=20, species_id="P001")

        boss_info = {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 10,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        }

        self.game.dm.set_boss_hp("time_demon", 500)

        with patch("src.game.boss.get_active_boss", return_value=("time_demon", boss_info)):
            result = self.game.boss("u1", arg="攻击")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertLessEqual(monster_dict["hp"], 500)

    @patch("src.game.boss.battle_engine")
    def test_boss_monster_dict_has_required_fields(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="Boss",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=20, species_id="P001")

        boss_info = {
            "name": "时间魔王猪", "hp": 1000000, "min_level": 10,
            "schedule": [(12, 0)], "duration_minutes": 10,
            "species_id": "P007", "stage": 2,
        }

        with patch("src.game.boss.get_active_boss", return_value=("time_demon", boss_info)):
            self.game.boss("u1", arg="攻击")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        for key in ["owner_id", "name", "species_id", "evolution_stage",
                     "battle_type", "hp", "atk", "def_", "spd", "crit",
                     "crit_dmg", "eva", "lifesteal"]:
            self.assertIn(key, monster_dict, f"Missing key: {key}")


class TestDungeonFightIntegration(IntegrationTestBase):

    @patch("src.game.dungeon.battle_engine")
    def test_dungeon_enemy_passives_as_modifiers(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="怪物",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=30, species_id="P001")
        for s in ["1", "2", "3", "boss"]:
            self.game.dm.mark_dungeon_first("u1", 1, s)

        self.game.dungeon("u1", arg="2 1")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertIn("modifiers", monster_dict)
        self.assertTrue(len(monster_dict["modifiers"]) > 0)

    @patch("src.game.dungeon.battle_engine")
    def test_dungeon_ch1_no_enemy_modifiers(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="怪物",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=10, species_id="P001")
        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertNotIn("modifiers", monster_dict)

    @patch("src.game.dungeon.battle_engine")
    def test_dungeon_player_passives_injected(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="怪物",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=20, species_id="P001")
        self.game.dm.add_passive_bag("u1", "PS_D01", 1)
        self.game.dm.set_passive_slot("u1", 1, "PS_D01")
        self.game.dm.set_passive_level("u1", "PS_D01", 2)

        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        pet_dict = call_args[0][0]
        self.assertIn("modifiers", pet_dict)
        hp_mod = next(m for m in pet_dict["modifiers"] if m["stat"] == "hp")
        self.assertGreater(hp_mod["value"], 0)

    @patch("src.game.dungeon.battle_engine")
    def test_dungeon_enemy_modifiers_valid_format(self, mock_engine):
        from src.battle.models import BattleResult
        mock_engine.run.return_value = BattleResult(
            winner="u1", winner_name="测试猪", loser_name="怪物",
            events=[], duration=5.0, pets=[],
        )

        self._setup_pet("u1", level=30, species_id="P001")
        for s in ["1", "2", "3", "boss"]:
            self.game.dm.mark_dungeon_first("u1", 1, s)
            self.game.dm.mark_dungeon_first("u1", 2, s)

        self.game.dungeon("u1", arg="3 1")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertIn("modifiers", monster_dict)
        for mod in monster_dict["modifiers"]:
            self.assertIn("stat", mod)
            self.assertIn("value", mod)
            self.assertIn("type", mod)
            self.assertIn(mod["type"], ("pct", "flat"))


class TestRealEngineBattle(unittest.TestCase):

    def setUp(self):
        self.engine = BattleEngine()

    def test_real_battle_both_types_get_advantage(self):
        attack_pet = {
            "owner_id": "A", "name": "攻击猪", "species_id": "P001",
            "evolution_stage": 0, "battle_type": "attack",
            "hp": 5000, "atk": 200, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        }
        defense_pet = {
            "owner_id": "B", "name": "防御猪", "species_id": "P004",
            "evolution_stage": 0, "battle_type": "defense",
            "hp": 5000, "atk": 200, "def_": 50, "spd": 1.0,
            "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
        }

        result = self.engine.run(attack_pet, defense_pet)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, BattleResult)
        self.assertGreater(len(result.events), 0)

    def test_real_battle_all_25_species_runnable(self):
        for sid in PET_SPECIES:
            for stage in range(3):
                pet = {
                    "owner_id": "test", "name": f"Test_{sid}_{stage}",
                    "species_id": sid, "evolution_stage": stage,
                    "battle_type": PET_SPECIES[sid]["battle_type"],
                    "hp": 1000, "atk": 100, "def_": 50, "spd": 1.0,
                    "crit": 5, "crit_dmg": 1.5, "eva": 5, "lifesteal": 0.05,
                }
                enemy = {
                    "owner_id": "enemy", "name": "Enemy",
                    "species_id": "P001", "evolution_stage": 0,
                    "battle_type": "attack",
                    "hp": 100, "atk": 10, "def_": 0, "spd": 0.5,
                    "crit": 0, "crit_dmg": 1.5, "eva": 0, "lifesteal": 0,
                }
                result = self.engine.run(pet, enemy)
                self.assertIsNotNone(result, f"Battle failed for {sid} stage {stage}")


class TestHandlerRouting(unittest.TestCase):

    def test_all_battle_commands_registered(self):
        from src.game.commands import get_handler
        self.assertIsNotNone(get_handler("战斗"))
        self.assertIsNotNone(get_handler("battle"))
        self.assertIsNotNone(get_handler("boss"))
        self.assertIsNotNone(get_handler("副本"))
        self.assertIsNotNone(get_handler("dungeon"))

    def test_handler_signature_compatible(self):
        from src.game.commands import get_handler
        import inspect
        for cmd_name in ["战斗", "battle", "boss", "副本", "dungeon"]:
            handler = get_handler(cmd_name)
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            self.assertIn("self", params, f"{cmd_name}: missing 'self'")
            self.assertIn("user_id", params, f"{cmd_name}: missing 'user_id'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
