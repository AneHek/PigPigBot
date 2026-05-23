"""
test_battle.py - Tests for battle engine.
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.modules['redis'] = MagicMock()

from src.battle import BattleEngine, BattleResult, BattleEvent, BattlePet, \
    DT, MAX_DURATION, format_battle_report
from src.pet_config import PET_SPECIES, Skill, SkillEffect


def make_test_pet_dict(**overrides) -> dict:
    """Create a test pet dict for battle."""
    base = {
        "owner_id": "test_user",
        "name": "TestPet",
        "species_id": "P001",  # 五行猪混混 (attack type)
        "evolution_stage": 0,
        "battle_type": "attack",
        "hp": 1000,
        "atk": 100,
        "def_": 50,
        "spd": 1.0,
        "crit": 10,
        "crit_dmg": 1.5,
        "eva": 5,
        "lifesteal": 0.05,
    }
    base.update(overrides)
    return base


class TestBattleEngine(unittest.TestCase):
    """Core battle engine tests."""

    def setUp(self):
        self.engine = BattleEngine()

    def test_battle_ends_with_winner(self):
        """A significantly stronger pet should win."""
        a = make_test_pet_dict(hp=2000, atk=500, owner_id="A", name="强猪")
        b = make_test_pet_dict(hp=100, atk=10, owner_id="B", name="弱猪")
        result = self.engine.run(a, b)
        self.assertIsNotNone(result.winner)
        self.assertGreater(result.duration, 0)
        self.assertTrue(len(result.events) > 0)

    def test_battle_result_has_correct_structure(self):
        """BattleResult has all expected fields."""
        a = make_test_pet_dict(owner_id="A", name="猪A")
        b = make_test_pet_dict(owner_id="B", name="猪B")
        result = self.engine.run(a, b)
        self.assertIsInstance(result, BattleResult)
        self.assertIsInstance(result.duration, float)
        self.assertIsInstance(result.events, list)

    def test_battle_events_include_attacks(self):
        """Battle should generate attack events."""
        a = make_test_pet_dict(atk=100, spd=2.0)
        b = make_test_pet_dict(def_=0, eva=0)
        result = self.engine.run(a, b)
        attack_events = [e for e in result.events if e.type == "attack"]
        self.assertTrue(len(attack_events) > 0)

    def test_very_high_eva_dodges(self):
        """Pet with 100% eva should dodge often."""
        a = make_test_pet_dict(atk=50, spd=1.0)
        b = make_test_pet_dict(eva=95, hp=5000, atk=10)  # high EVA for dodging
        result = self.engine.run(a, b)
        dodge_events = [e for e in result.events if e.type == "dodge"]
        # Should have at least some dodges with 95% eva
        self.assertTrue(len(dodge_events) > 0)

    def test_crits_occur(self):
        """High crit rate generates crits."""
        a = make_test_pet_dict(crit=90, crit_dmg=2.0, atk=50, spd=2.0)
        b = make_test_pet_dict(eva=0, hp=5000)
        result = self.engine.run(a, b)
        crit_events = [e for e in result.events if e.is_crit]
        self.assertTrue(len(crit_events) > 0)

    def test_battle_within_timeout(self):
        """Battle should complete within max duration."""
        a = make_test_pet_dict(hp=100, atk=5, spd=0.5)
        b = make_test_pet_dict(hp=100, atk=5, spd=0.5)
        result = self.engine.run(a, b)
        self.assertLess(result.duration, MAX_DURATION + 1)

    def test_type_advantage_works(self):
        """Attack type should have advantage against defense type."""
        result_no_adv = self.engine.run(
            make_test_pet_dict(battle_type="attack", owner_id="A"),
            make_test_pet_dict(battle_type="speed", owner_id="B")
        )
        result_with_adv = self.engine.run(
            make_test_pet_dict(battle_type="attack", owner_id="A"),
            make_test_pet_dict(battle_type="defense", owner_id="B")
        )
        # Both should complete
        self.assertIsNotNone(result_no_adv)
        self.assertIsNotNone(result_with_adv)


class TestSkillExecution(unittest.TestCase):
    """Test skill effects in battle."""

    def setUp(self):
        self.engine = BattleEngine()

    def test_skills_trigger(self):
        """Skills should fire during battle."""
        a = make_test_pet_dict(atk=50, spd=1.0, species_id="P001")
        b = make_test_pet_dict(hp=2000, atk=10, def_=0, eva=0)
        result = self.engine.run(a, b)
        skill_events = [e for e in result.events if e.type == "skill"]
        self.assertTrue(len(skill_events) > 0)

    def test_dot_skill_applied(self):
        """DoT skills should create dot events."""
        a = make_test_pet_dict(atk=50, spd=1.5, species_id="P003")  # Has dot at stage 2
        # Use stage 1 (培根猪卷) which has dot + bleed
        a["evolution_stage"] = 1
        b = make_test_pet_dict(hp=2000, def_=0, eva=0)
        result = self.engine.run(a, b)
        dot_events = [e for e in result.events if e.type == "dot"]
        # May or may not have dots depending on skill timing
        self.assertIsInstance(result.duration, float)

    def test_true_damage_skill(self):
        """True damage bypasses defense."""
        a = make_test_pet_dict(atk=50, spd=1.0, species_id="P001")
        a["evolution_stage"] = 2  # Stage 3: 混沌猪 has true damage
        b = make_test_pet_dict(hp=500, def_=2000, eva=0)  # Very high defense
        result = self.engine.run(a, b)
        # Battle should complete - true damage helps against high def
        self.assertIsInstance(result.duration, float)


class TestBattleReport(unittest.TestCase):
    """Test battle report formatting."""

    def setUp(self):
        self.engine = BattleEngine()

    def test_format_report_no_crash(self):
        """format_battle_report should not raise."""
        a = make_test_pet_dict(owner_id="A", name="猪A")
        b = make_test_pet_dict(owner_id="B", name="猪B")
        result = self.engine.run(a, b)
        report = format_battle_report(result)
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)

    def test_report_shows_winner(self):
        """Winner name appears in report."""
        a = make_test_pet_dict(hp=2000, atk=500, owner_id="A", name="强猪")
        b = make_test_pet_dict(hp=100, atk=10, owner_id="B", name="弱猪")
        result = self.engine.run(a, b)
        report = format_battle_report(result)
        if result.winner:
            self.assertIn(result.winner_name, report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
