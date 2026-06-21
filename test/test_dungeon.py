"""
test_dungeon.py — 副本系统测试。

覆盖：菜单、章节查看、战斗入口、被动注入、奖励结算、首通标记、章节奖励、重置。
"""
import sys
import unittest
from unittest.mock import MagicMock, patch, call

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis, make_test_pet
from src.battle.models import BattleResult, BattlePet, BattleEvent


class DungeonTestBase(unittest.TestCase):

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
             "crit": pet.crit, "crit_dmg": pet.crit_dmg, "eva": pet.eva, "lifesteal": pet.lifesteal}
        )
        return pet

    def _make_win_result(self, winner_id="u1"):
        return BattleResult(
            winner=winner_id,
            winner_name="测试猪" if winner_id == "u1" else "怪物",
            loser_name="怪物" if winner_id == "u1" else "测试猪",
            events=[],
            duration=5.0,
            pets=[],
        )


class TestDungeonMenu(DungeonTestBase):

    def test_menu_no_pet(self):
        result = self.game.dungeon("u1")
        self.assertIn("还没有宠物", result)

    def test_menu_shows_chapters(self):
        self._setup_pet()
        result = self.game.dungeon("u1")
        self.assertIn("副本总览", result)
        self.assertIn("萌新猪舍", result)

    def test_menu_chapter_1_unlocked(self):
        self._setup_pet()
        result = self.game.dungeon("u1")
        self.assertNotIn("未解锁", result.split("\n")[2])

    def test_menu_chapter_2_locked(self):
        self._setup_pet()
        result = self.game.dungeon("u1")
        self.assertIn("未解锁", result)


class TestDungeonChapter(DungeonTestBase):

    def test_chapter_invalid(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="99")
        self.assertIn("不存在", result)

    def test_chapter_shows_stages(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="1")
        self.assertIn("杂兵关", result)
        self.assertIn("BOSS关", result)

    def test_chapter_locked(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="2")
        self.assertIn("尚未解锁", result)


class TestDungeonFightValidation(DungeonTestBase):

    def test_fight_invalid_stage(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="1 99")
        self.assertIn("关卡不存在", result)

    def test_fight_daily_limit(self):
        self._setup_pet()
        for _ in range(3):
            self.game.dm.incr_dungeon_count("u1", 1, "1")
        result = self.game.dungeon("u1", arg="1 1")
        self.assertIn("次数已用完", result)

    def test_fight_energy_insufficient(self):
        self._setup_pet()
        self.game.dm.use_energy("u1", 96)
        result = self.game.dungeon("u1", arg="1 1")
        self.assertIn("行动力不足", result)

    def test_fight_training(self):
        self._setup_pet()
        self.game.dm.start_training("u1")
        result = self.game.dungeon("u1", arg="1 1")
        self.assertIn("训练中无法挑战", result)

    def test_fight_locked_chapter(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="2 1")
        self.assertIn("尚未解锁", result)

    def test_fight_hide_not_ch7(self):
        self._setup_pet()
        result = self.game.dungeon("u1", arg="1 hide")
        self.assertIn("隐藏关卡仅在第 7 章", result)


class TestDungeonFightRealPath(DungeonTestBase):

    @patch("src.game.dungeon.battle_engine")
    def test_fight_returns_list_on_win(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)
        result = self.game.dungeon("u1", arg="1 1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    @patch("src.game.dungeon.battle_engine")
    def test_fight_returns_list_on_lose(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("monster")
        self._setup_pet(level=20)
        result = self.game.dungeon("u1", arg="1 1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIn("战败", result[1])

    @patch("src.game.dungeon.battle_engine")
    def test_fight_deducts_energy(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)
        energy_before = self.game.dm.get_energy("u1")["value"]
        self.game.dungeon("u1", arg="1 1")
        energy_after = self.game.dm.get_energy("u1")["value"]
        self.assertEqual(energy_before - energy_after, 5)

    @patch("src.game.dungeon.battle_engine")
    def test_fight_increments_daily_count(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)
        self.assertEqual(self.game.dm.get_dungeon_count("u1", 1, "1"), 0)
        self.game.dungeon("u1", arg="1 1")
        self.assertEqual(self.game.dm.get_dungeon_count("u1", 1, "1"), 1)

    @patch("src.game.dungeon.battle_engine")
    def test_fight_no_count_on_lose(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("monster")
        self._setup_pet(level=20)
        self.game.dungeon("u1", arg="1 1")
        self.assertEqual(self.game.dm.get_dungeon_count("u1", 1, "1"), 0)


class TestDungeonRewards(DungeonTestBase):

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_win_grants_exp_and_gold(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 1.0
        self._setup_pet(level=20)

        pet_before = self.game.dm.get_pet("u1")
        gold_before = self.game.dm.get_gold("u1")

        self.game.dungeon("u1", arg="1 1")

        pet_after = self.game.dm.get_pet("u1")
        gold_after = self.game.dm.get_gold("u1")

        self.assertGreater(pet_after.exp + pet_after.level * 100, pet_before.exp)
        self.assertGreater(gold_after, gold_before)

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_win_grants_materials(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 2
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 1.0
        self._setup_pet(level=20)

        self.game.dungeon("u1", arg="1 2")

        stone = self.game.dm.get_item("u1", "stone")
        self.assertGreaterEqual(stone, 1)

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_first_clear_marks(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 1.0
        self._setup_pet(level=20)

        first_set = self.game.dm.get_dungeon_first_set("u1")
        self.assertNotIn("1-1", first_set)

        self.game.dungeon("u1", arg="1 1")

        first_set = self.game.dm.get_dungeon_first_set("u1")
        self.assertIn("1-1", first_set)

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_first_clear_exp_bonus(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 1.0
        self._setup_pet(level=20)

        result_first = self.game.dungeon("u1", arg="1 1")
        self.assertIn("首通加成", result_first[1])

        mock_engine.run.return_value = self._make_win_result("u1")
        result_second = self.game.dungeon("u1", arg="1 1")
        self.assertNotIn("首通加成", result_second[1])


class TestDungeonEnemyPassives(DungeonTestBase):

    @patch("src.game.dungeon.battle_engine")
    def test_ch1_enemy_no_passives(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=10)
        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertNotIn("passive_slots", monster_dict)
        self.assertNotIn("passive_levels", monster_dict)

    @patch("src.game.dungeon.battle_engine")
    def test_ch2_enemy_has_passives(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)

        for s in ["1", "2", "3", "boss"]:
            self.game.dm.mark_dungeon_first("u1", 1, s)

        self.game.dungeon("u1", arg="2 1")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertIn("passive_slots", monster_dict)
        self.assertIn("passive_levels", monster_dict)
        self.assertIn("PS_D01", monster_dict["passive_slots"].values())

    @patch("src.game.dungeon.battle_engine")
    def test_ch2_boss_has_more_passives(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)

        for s in ["1", "2", "3", "boss"]:
            self.game.dm.mark_dungeon_first("u1", 1, s)

        self.game.dungeon("u1", arg="2 boss")

        call_args = mock_engine.run.call_args
        monster_dict = call_args[0][1]
        self.assertIn("passive_slots", monster_dict)
        self.assertEqual(len(monster_dict["passive_slots"]), 2)


class TestDungeonPlayerPassives(DungeonTestBase):

    @patch("src.game.dungeon.battle_engine")
    def test_player_passives_injected(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)

        self.game.dm.set_passive_slot("u1", 1, "PS_A01")
        self.game.dm.set_passive_level("u1", "PS_A01", 3)

        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        pet_dict = call_args[0][0]
        self.assertIn("modifiers", pet_dict)
        atk_mod = next(m for m in pet_dict["modifiers"] if m["stat"] == "atk")
        self.assertEqual(atk_mod["type"], "pct")
        self.assertGreater(atk_mod["value"], 0)

    @patch("src.game.dungeon.battle_engine")
    def test_player_no_passives_no_key(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)

        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        pet_dict = call_args[0][0]
        self.assertNotIn("modifiers", pet_dict)

    @patch("src.game.dungeon.battle_engine")
    def test_player_multiple_passives(self, mock_engine):
        mock_engine.run.return_value = self._make_win_result("u1")
        self._setup_pet(level=20)

        self.game.dm.set_passive_slot("u1", 1, "PS_A01")
        self.game.dm.set_passive_level("u1", "PS_A01", 5)
        self.game.dm.set_passive_slot("u1", 2, "PS_D01")
        self.game.dm.set_passive_level("u1", "PS_D01", 3)

        self.game.dungeon("u1", arg="1 1")

        call_args = mock_engine.run.call_args
        pet_dict = call_args[0][0]
        self.assertIn("modifiers", pet_dict)
        self.assertEqual(len(pet_dict["modifiers"]), 2)
        stats = {m["stat"] for m in pet_dict["modifiers"]}
        self.assertIn("atk", stats)
        self.assertIn("hp", stats)


class TestDungeonPassiveDrops(DungeonTestBase):

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_passive_book_drops(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.side_effect = [1, "PS_A01", "PS_D01"]
        mock_rand.random.return_value = 0.01
        self._setup_pet(level=20)

        self.game.dungeon("u1", arg="1 1")

        bag_a01 = self.game.dm.get_passive_bag("u1", "PS_A01")
        bag_d01 = self.game.dm.get_passive_bag("u1", "PS_D01")
        self.assertGreaterEqual(bag_a01 + bag_d01, 1)

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_no_drop_on_high_roll(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 0.99
        self._setup_pet(level=20)

        self.game.dungeon("u1", arg="1 1")

        all_bags = self.game.dm.get_all_passive_bags("u1")
        self.assertEqual(len(all_bags), 0)


class TestDungeonChapterCompletion(DungeonTestBase):

    @patch("src.game.dungeon.random")
    @patch("src.game.dungeon.battle_engine")
    def test_chapter_first_clear_reward(self, mock_engine, mock_rand):
        mock_engine.run.return_value = self._make_win_result("u1")
        mock_rand.randint.return_value = 10
        mock_rand.choice.return_value = 1
        mock_rand.random.return_value = 1.0
        self._setup_pet(level=20)

        for s in ["1", "2", "3"]:
            self.game.dm.mark_dungeon_first("u1", 1, s)

        gold_before = self.game.dm.get_gold("u1")
        result = self.game.dungeon("u1", arg="1 boss")

        gold_after = self.game.dm.get_gold("u1")

        self.assertIn("首通奖励", result[1])
        self.assertGreater(gold_after - gold_before, 1000)


class TestDungeonReset(DungeonTestBase):

    def test_reset_no_arg(self):
        self._setup_pet()
        result = self.game.dungeon_reset("u1", arg="")
        self.assertIn("指定章节号", result)

    def test_reset_invalid_chapter(self):
        self._setup_pet()
        result = self.game.dungeon_reset("u1", arg="99")
        self.assertIn("不存在", result)

    def test_reset_diamond_insufficient(self):
        self._setup_pet()
        result = self.game.dungeon_reset("u1", arg="1")
        self.assertIn("钻石不足", result)

    def test_reset_success(self):
        self._setup_pet()
        self.game.dm.add_diamond("u1", 20)
        result = self.game.dungeon_reset("u1", arg="1")
        self.assertIn("已重置", result)

    def test_reset_twice(self):
        self._setup_pet()
        self.game.dm.add_diamond("u1", 50)
        self.game.dungeon_reset("u1", arg="1")
        result = self.game.dungeon_reset("u1", arg="1")
        self.assertIn("已重置过", result)

    def test_reset_clears_counts(self):
        self._setup_pet()
        self.game.dm.incr_dungeon_count("u1", 1, "1")
        self.game.dm.incr_dungeon_count("u1", 1, "1")
        self.assertEqual(self.game.dm.get_dungeon_count("u1", 1, "1"), 2)

        self.game.dm.add_diamond("u1", 20)
        self.game.dungeon_reset("u1", arg="1")
        self.assertEqual(self.game.dm.get_dungeon_count("u1", 1, "1"), 0)


class TestEnemyPassiveConfig(unittest.TestCase):

    def test_ch1_no_passives(self):
        from src.game.dungeon_config import get_enemy_passives
        self.assertEqual(get_enemy_passives(1, "1"), {})
        self.assertEqual(get_enemy_passives(1, "boss"), {})

    def test_ch2_has_passives(self):
        from src.game.dungeon_config import get_enemy_passives
        p = get_enemy_passives(2, "1")
        self.assertIn("passive_slots", p)
        self.assertIn("passive_levels", p)

    def test_ch7_hide_has_passives(self):
        from src.game.dungeon_config import get_enemy_passives
        p = get_enemy_passives(7, "hide")
        self.assertIn("passive_slots", p)
        self.assertEqual(len(p["passive_slots"]), 4)

    def test_all_passive_ids_valid(self):
        from src.game.dungeon_config import ENEMY_PASSIVES
        from src.game.passive_config import PASSIVE_SKILLS
        for ch, stages in ENEMY_PASSIVES.items():
            for stage_id, cfg in stages.items():
                for slot, sid in cfg["passive_slots"].items():
                    self.assertIn(sid, PASSIVE_SKILLS,
                                  f"Ch{ch}-{stage_id} slot {slot}: {sid} not in PASSIVE_SKILLS")
                for sid, lvl in cfg["passive_levels"].items():
                    self.assertIn(sid, PASSIVE_SKILLS,
                                  f"Ch{ch}-{stage_id} level key {sid} not in PASSIVE_SKILLS")
                    self.assertGreater(lvl, 0)
                    self.assertLessEqual(lvl, 10)

    def test_passive_slots_match_levels(self):
        from src.game.dungeon_config import ENEMY_PASSIVES
        for ch, stages in ENEMY_PASSIVES.items():
            for stage_id, cfg in stages.items():
                slot_ids = set(cfg["passive_slots"].values())
                level_ids = set(cfg["passive_levels"].keys())
                self.assertEqual(slot_ids, level_ids,
                                 f"Ch{ch}-{stage_id}: slots {slot_ids} != levels {level_ids}")

    def test_boss_has_more_or_equal_passives(self):
        from src.game.dungeon_config import ENEMY_PASSIVES
        for ch, stages in ENEMY_PASSIVES.items():
            if "boss" not in stages:
                continue
            boss_count = len(stages["boss"]["passive_slots"])
            for stage_id in ["1", "2", "3"]:
                if stage_id in stages:
                    normal_count = len(stages[stage_id]["passive_slots"])
                    self.assertGreaterEqual(boss_count, normal_count,
                                            f"Ch{ch}: boss ({boss_count}) < {stage_id} ({normal_count})")


if __name__ == "__main__":
    unittest.main()
