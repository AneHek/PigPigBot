"""
test_pet_stats.py - Tests for pet_stats module.
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

# Need to mock redis before importing any project module
sys.modules['redis'] = MagicMock()

from src.pet_stats import (
    generate_ivs, generate_quality, QUALITY_RANGES, QUALITY_INDEX_TO_LABEL,
    iv_coefficient, calc_stats, calc_max_exp,
    calc_training_exp, quality_rating, quality_label,
)


class TestGenerateQuality(unittest.TestCase):
    """Test binomial quality generation."""

    def test_generate_quality_returns_valid_index(self):
        """品质索引应在 0~5 范围内"""
        for _ in range(200):
            idx = generate_quality(5, 0.5)
            self.assertGreaterEqual(idx, 0)
            self.assertLessEqual(idx, 5)

    def test_generate_quality_distribution(self):
        """二项分布分布近似校验：各档位应有合理的出现概率"""
        counts = {i: 0 for i in range(6)}
        samples = 5000
        for _ in range(samples):
            counts[generate_quality(5, 0.5)] += 1
        # 每个档位至少出现 1%（考虑二项分布 0 和 5 概率均为 1/32≈3%）
        for i in range(6):
            ratio = counts[i] / samples
            self.assertGreater(ratio, 0.005, f"档位 {i} 概率异常低: {ratio:.4f}")


class TestIVGeneration(unittest.TestCase):
    """Test IV generation with quality constraint."""

    def test_generate_ivs_no_quality_returns_six_values(self):
        """无品质约束时仍返回6项IV"""
        ivs = generate_ivs()
        self.assertEqual(len(ivs), 6)
        for key in ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]:
            self.assertIn(key, ivs)

    def test_ivs_in_range(self):
        """每项IV在 [0, 31]"""
        for _ in range(100):
            ivs = generate_ivs()
            for v in ivs.values():
                self.assertGreaterEqual(v, 0)
                self.assertLessEqual(v, 31)

    def test_ivs_with_quality_constraint(self):
        """指定品质档位后，IV总和应在档位范围内"""
        for qi in range(6):
            lo, hi = QUALITY_RANGES[qi]
            for _ in range(50):
                ivs = generate_ivs(qi)
                s = sum(ivs.values())
                # 允许 ±5 的容差（钳位可能导致微小偏移）
                self.assertGreaterEqual(s, lo - 5,
                    f"QI={qi}: sum={s} < lo={lo}")
                self.assertLessEqual(s, hi + 5,
                    f"QI={qi}: sum={s} > hi={hi}")

    def test_quality_ranges_match_rating(self):
        """QUALITY_RANGES 和 quality_rating() 边界一致"""
        test_sums = [0, 30, 31, 60, 61, 90, 91, 120, 121, 150, 151, 186]
        for s in test_sums:
            # 构造假IV字典
            fake_ivs = {
                "iv_hp": s // 6,
                "iv_atk": s // 6,
                "iv_def": s // 6,
                "iv_spd": s // 6,
                "iv_crit": s // 6,
                "iv_eva": s - 5 * (s // 6),
            }
            rating = quality_rating(fake_ivs)
            # 验证：档位范围内找对应标签
            found = False
            for qi, (lo, hi) in QUALITY_RANGES.items():
                if lo <= s <= hi and QUALITY_INDEX_TO_LABEL[qi] == rating:
                    found = True
                    break
            self.assertTrue(found,
                f"sum={s} rating={rating} not matching QUALITY_RANGES")


class TestIVCoefficient(unittest.TestCase):
    """Test IV coefficient formula."""

    def test_iv_0_gives_075(self):
        self.assertEqual(iv_coefficient(0), 0.75)

    def test_iv_31_gives_125(self):
        self.assertEqual(iv_coefficient(31), 1.25)

    def test_iv_15_approximately_1(self):
        self.assertAlmostEqual(iv_coefficient(15), 0.99, places=1)

    def test_iv_coefficient_monotonic(self):
        prev = 0
        for iv in range(32):
            c = iv_coefficient(iv)
            self.assertGreaterEqual(c, prev)
            prev = c


class TestStatCalculation(unittest.TestCase):
    """Test attribute calculations."""

    def _make_ivs(self, values):
        keys = ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]
        return dict(zip(keys, values))

    def test_calc_stats_attack_lv1(self):
        """Attack type level 1 with IV=15 gives expected baseline."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        stats = calc_stats("P001", 0, 1, ivs)

        # Attack type base: atk=65*f + 8.3*f*1.0*0
        # f = 0.75 + 15/31*0.5 ≈ 0.99
        self.assertAlmostEqual(stats["atk"], 64.4, delta=2)
        self.assertAlmostEqual(stats["hp"], 515, delta=10)
        self.assertAlmostEqual(stats["def_"], 17.8, delta=1)
        self.assertEqual(stats["crit_dmg"], 1.5)
        self.assertEqual(stats["lifesteal"], 0.05)

    def test_calc_stats_defense_lv1(self):
        """Defense type level 1."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        stats = calc_stats("P005", 0, 1, ivs)

        self.assertAlmostEqual(stats["hp"], 644, delta=10)
        self.assertAlmostEqual(stats["atk"], 39.6, delta=2)
        self.assertAlmostEqual(stats["def_"], 29.7, delta=1)

    def test_calc_stats_speed_lv1(self):
        """Speed type level 1."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        stats = calc_stats("P002", 0, 1, ivs)

        self.assertAlmostEqual(stats["hp"], 426, delta=10)
        self.assertAlmostEqual(stats["spd"], 0.64, delta=0.05)
        self.assertAlmostEqual(stats["eva"], 5.9, delta=1)

    def test_calc_stats_with_level(self):
        """Stats increase with level."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        stats_lv1 = calc_stats("P001", 0, 1, ivs)
        stats_lv30 = calc_stats("P001", 0, 30, ivs)

        self.assertGreater(stats_lv30["hp"], stats_lv1["hp"])
        self.assertGreater(stats_lv30["atk"], stats_lv1["atk"])
        self.assertGreater(stats_lv30["def_"], stats_lv1["def_"])
        self.assertGreater(stats_lv30["spd"], stats_lv1["spd"])
        self.assertGreater(stats_lv30["crit"], stats_lv1["crit"])

    def test_calc_stats_evolution_coefficient(self):
        """Evolution increases stats via coefficient."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        stats_s0_lv30 = calc_stats("P001", 0, 30, ivs)
        stats_s1_lv30 = calc_stats("P001", 1, 30, ivs)
        stats_s2_lv30 = calc_stats("P001", 2, 30, ivs)

        self.assertGreater(stats_s1_lv30["atk"], stats_s0_lv30["atk"])
        self.assertGreater(stats_s2_lv30["atk"], stats_s1_lv30["atk"])

    def test_fixed_stats_by_stage(self):
        """CRIT_DMG and LIFESTEAL only change with evolution."""
        ivs = self._make_ivs([15, 15, 15, 15, 15, 15])
        self.assertEqual(calc_stats("P001", 0, 1, ivs)["crit_dmg"], 1.5)
        self.assertEqual(calc_stats("P001", 0, 1, ivs)["lifesteal"], 0.05)
        self.assertEqual(calc_stats("P001", 1, 1, ivs)["crit_dmg"], 1.6)
        self.assertEqual(calc_stats("P001", 1, 1, ivs)["lifesteal"], 0.08)
        self.assertEqual(calc_stats("P001", 2, 1, ivs)["crit_dmg"], 1.7)
        self.assertEqual(calc_stats("P001", 2, 1, ivs)["lifesteal"], 0.11)

    def test_high_iv_gives_higher_stats(self):
        """Higher IV yields higher stats."""
        ivs_low = self._make_ivs([0, 0, 0, 0, 0, 0])
        ivs_high = self._make_ivs([31, 31, 31, 31, 31, 31])
        stats_low = calc_stats("P001", 0, 10, ivs_low)
        stats_high = calc_stats("P001", 0, 10, ivs_high)

        for key in ["hp", "atk", "def_", "spd", "crit", "eva"]:
            self.assertGreater(stats_high[key], stats_low[key],
                              f"IV=31 should give higher {key} than IV=0")


class TestStatCaps(unittest.TestCase):
    """Test attribute cap enforcement."""

    def _make_ivs(self, values):
        keys = ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]
        return dict(zip(keys, values))

    def test_spd_capped_at_2(self):
        """SPD cannot exceed 2.0."""
        ivs = self._make_ivs([15, 15, 15, 31, 15, 15])
        stats = calc_stats("P002", 2, 100, ivs)  # Speed type stage 3 level 100
        self.assertLessEqual(stats["spd"], 2.0)

    def test_crit_capped_at_75(self):
        """CRIT cannot exceed 75%."""
        ivs = self._make_ivs([15, 15, 15, 15, 31, 15])
        stats = calc_stats("P001", 2, 100, ivs)
        self.assertLessEqual(stats["crit"], 75.0)


class TestExpFormulas(unittest.TestCase):
    """Test EXP formulas."""

    def test_max_exp_lv1(self):
        """Lv1 needs 600 exp."""
        self.assertEqual(calc_max_exp(1), 600)

    def test_max_exp_lv10(self):
        """Lv10 needs 15000 exp."""
        self.assertEqual(calc_max_exp(10), 15000)

    def test_max_exp_lv30(self):
        """Lv30 needs 105000 exp."""
        exp = 100 * 30 * (30 + 5)
        self.assertEqual(calc_max_exp(30), exp)

    def test_max_exp_lv100(self):
        """Lv100 needs 1050000 exp."""
        exp = 100 * 100 * (100 + 5)
        self.assertEqual(calc_max_exp(100), exp)

    def test_max_exp_monotonically_increasing(self):
        """Each level requires more exp than the last."""
        prev = 0
        for lv in range(1, 101):
            m = calc_max_exp(lv)
            self.assertGreater(m, prev, f"Lv{lv} exp should be > Lv{lv-1}")
            prev = m


class TestTrainingExp(unittest.TestCase):
    """Test training EXP formula."""

    def test_training_exp_basic(self):
        """exp = 50 * level * minutes."""
        self.assertEqual(calc_training_exp(1, 10), 500)
        self.assertEqual(calc_training_exp(10, 10), 5000)
        self.assertEqual(calc_training_exp(30, 10), 15000)
        self.assertEqual(calc_training_exp(50, 60), 150000)


class TestQualityRating(unittest.TestCase):
    """Test quality rating system."""

    def test_quality_boundaries(self):
        self.assertEqual(quality_rating({"a": 0}), "E")
        self.assertEqual(quality_rating({chr(97+i): v for i, v in enumerate([5]*6)}), "E")
        # Sum = 31
        ivs = {"iv_hp": 6, "iv_atk": 5, "iv_def": 5, "iv_spd": 5, "iv_crit": 5, "iv_eva": 5}
        self.assertEqual(quality_rating(ivs), "D")
        # Sum = 61
        ivs = {"iv_hp": 11, "iv_atk": 10, "iv_def": 10, "iv_spd": 10, "iv_crit": 10, "iv_eva": 10}
        self.assertEqual(quality_rating(ivs), "C")
        # Sum = 91
        ivs = {"iv_hp": 16, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        self.assertEqual(quality_rating(ivs), "B")
        # Sum = 121
        ivs = {"iv_hp": 21, "iv_atk": 20, "iv_def": 20, "iv_spd": 20, "iv_crit": 20, "iv_eva": 20}
        self.assertEqual(quality_rating(ivs), "A")
        # Sum = 151
        ivs = {"iv_hp": 26, "iv_atk": 25, "iv_def": 25, "iv_spd": 25, "iv_crit": 25, "iv_eva": 25}
        self.assertEqual(quality_rating(ivs), "S")

    def test_quality_label(self):
        self.assertEqual(quality_label("S"), "传说")
        self.assertEqual(quality_label("A"), "卓越")
        self.assertEqual(quality_label("B"), "优秀")
        self.assertEqual(quality_label("C"), "不错")
        self.assertEqual(quality_label("D"), "一般")
        self.assertEqual(quality_label("E"), "普通")


class TestCalcCP(unittest.TestCase):
    """Test Combat Power calculation."""

    def _make_mock_pet(self, hp=520, atk=65, def_=18, spd=0.58, crit=8, eva=4):
        """Create a mock object with pet-like attributes."""
        from types import SimpleNamespace
        return SimpleNamespace(hp=hp, atk=atk, def_=def_, spd=spd, crit=crit, eva=eva)

    def test_calc_cp_baseline(self):
        """P001 attack type Lv1: baseline CP."""
        from src.pet_stats import calc_cp
        pet = self._make_mock_pet(hp=520, atk=65, def_=18, spd=0.58, crit=8, eva=4)
        cp = calc_cp(pet)
        # CP = 520*0.05 + 65*2 + 18*1.5 + 0.58*800 + 8*15 + 4*12
        #   = 26 + 130 + 27 + 464 + 120 + 48 = 815
        self.assertEqual(cp, 815)

    def test_calc_cp_higher_stats_gives_higher_cp(self):
        """Higher stats yield higher CP."""
        from src.pet_stats import calc_cp
        pet_low = self._make_mock_pet(hp=300, atk=30, def_=10, spd=0.2, crit=2, eva=1)
        pet_high = self._make_mock_pet(hp=1000, atk=200, def_=100, spd=1.5, crit=50, eva=30)
        self.assertGreater(calc_cp(pet_high), calc_cp(pet_low))

    def test_calc_cp_is_int(self):
        """CP should be an integer."""
        from src.pet_stats import calc_cp
        pet = self._make_mock_pet()
        self.assertIsInstance(calc_cp(pet), int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
