"""
pet_stats.py — IV generation, attribute calculation, formulas.

Based on levelandAtt.md design document.
"""
import random

from src.pet_config import PET_GROWTH, EVOLUTION_COEFFICIENTS, FIXED_STATS, STAT_CAPS


# ══════════════════════════════════════════════════════════════════════
# 品质档位常量
# ══════════════════════════════════════════════════════════════════════

# 品质档位索引 → IV总和范围（含边界）
QUALITY_RANGES: dict[int, tuple[int, int]] = {
    0: (0, 30),     # E
    1: (31, 60),    # D
    2: (61, 90),    # C
    3: (91, 120),   # B
    4: (121, 150),  # A
    5: (151, 186),  # S
}

# 品质档位索引 → 标签字母
QUALITY_INDEX_TO_LABEL: dict[int, str] = {0: "E", 1: "D", 2: "C", 3: "B", 4: "A", 5: "S"}


def generate_quality(n: int = 5, p: float = 0.5) -> int:
    """使用二项分布生成品质档位索引 0~5。

    二项分布 Binomial(n, p) 的概率质量函数：
      P(k) = C(n,k) * p^k * (1-p)^(n-k)

    Args:
        n: 试验次数（默认5，对应6个档位）
        p: 成功概率（默认0.5，对称钟形分布）

    Returns:
        品质档位索引 0=E, 1=D, 2=C, 3=B, 4=A, 5=S
    """
    successes = sum(1 for _ in range(n) if random.random() < p)
    return successes  # 0~n，恰好映射到 0~5 六个品质档位


def generate_ivs(quality_index: int | None = None) -> dict[str, int]:
    """生成6项IV。

    若指定 quality_index，IV总和约束在 QUALITY_RANGES[quality_index] 范围内；
    否则沿用量品质评分逻辑（兼容旧调用）。

    算法：在档位范围随机取 target_sum → 6个随机权重按比例分配
    → 钳位到[0,31] → 超出/不足二次分配至未钳位维度 → 最多3轮迭代

    Args:
        quality_index: 品质档位索引 0~5，None 时对每项独立正态分布

    Returns:
        dict: {"iv_hp": int, ..., "iv_eva": int}，每项 0~31
    """
    iv_keys = ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]

    if quality_index is not None:
        lo, hi = QUALITY_RANGES[quality_index]
        target_sum = random.randint(lo, hi)

        iv_keys = ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]
        iv_values = {k: 0 for k in iv_keys}

        # 生成6个随机权重，按比例分配 target_sum
        weights = [random.random() for _ in range(6)]
        total_weight = sum(weights)
        for k, w in zip(iv_keys, weights):
            iv_values[k] = int(round((w / total_weight) * target_sum))

        # clamp to [0, 31]
        for k in iv_keys:
            iv_values[k] = max(0, min(31, iv_values[k]))

        # iterative redistribution to converge on target_sum
        for _ in range(10):
            cur_sum = sum(iv_values.values())
            delta = target_sum - cur_sum
            if delta == 0:
                break
            # select adjustable keys: not at boundary on the side we need to adjust
            if delta > 0:
                adjustable = [k for k in iv_keys if iv_values[k] < 31]
            else:
                adjustable = [k for k in iv_keys if iv_values[k] > 0]
            if not adjustable:
                break
            # distribute delta evenly
            per_key = delta // len(adjustable)
            remainder = delta % len(adjustable)
            for i, k in enumerate(adjustable):
                add = per_key + (1 if i < abs(remainder) else 0)
                iv_values[k] = max(0, min(31, iv_values[k] + add))

        # 最终钳位确保边界
        for k in iv_keys:
            iv_values[k] = max(0, min(31, iv_values[k]))

        return iv_values

    # 兼容旧行为：对每项独立正态分布
    ivs = {}
    for key in iv_keys:
        raw = random.gauss(15, 7)
        ivs[key] = max(0, min(31, int(round(raw))))
    return ivs


def iv_coefficient(iv: int) -> float:
    """IV修正系数 f = 0.75 + (IV/31) × 0.5"""
    return 0.75 + (iv / 31) * 0.5


def calc_stats(species_id: str, evolution_stage: int,
               level: int, ivs: dict[str, int]) -> dict[str, float]:
    """Calculate all computed battle stats for a pet.

    Args:
        species_id: "P001" ~ "P025"
        evolution_stage: 0/1/2
        level: 1-100
        ivs: dict with keys iv_hp, iv_atk, iv_def, iv_spd, iv_crit, iv_eva

    Returns dict with keys matching Pet dataclass: hp, atk, def_, spd, crit, crit_dmg, eva, lifesteal
    """
    from src.pet_config import PET_SPECIES
    battle_type = PET_SPECIES[species_id]["battle_type"]
    growth = PET_GROWTH[battle_type]
    E = EVOLUTION_COEFFICIENTS[evolution_stage]

    # IV mapping: stat_key → iv_key
    iv_map = {
        "hp": "iv_hp", "atk": "iv_atk", "def": "iv_def",
        "spd": "iv_spd", "crit": "iv_crit", "eva": "iv_eva",
    }

    stats = {}
    for stat_key in ["hp", "atk", "def", "spd", "crit", "eva"]:
        base_init, per_level = growth[stat_key]
        iv_val = ivs[iv_map[stat_key]]
        f = iv_coefficient(iv_val)

        # Formula: base_init * f + per_level * f * E * (level - 1)
        value = base_init * f + per_level * f * E * (level - 1)
        # Map "def" → "def_" for Pet dataclass compatibility
        out_key = "def_" if stat_key == "def" else stat_key
        stats[out_key] = round(value, 1)

    # Fixed stats (only depend on evolution stage)
    fixed = FIXED_STATS[evolution_stage]
    stats["crit_dmg"] = fixed["crit_dmg"]
    stats["lifesteal"] = fixed["lifesteal"]

    # Apply caps
    caps = {
        "spd": STAT_CAPS["spd"],
        "crit": STAT_CAPS["crit"],
        "eva": STAT_CAPS["eva"],
        "lifesteal": STAT_CAPS["lifesteal"] / 100.0,  # store as ratio
        "crit_dmg": STAT_CAPS["crit_dmg"] / 100.0,
    }
    for key, cap in caps.items():
        if key in stats:
            stats[key] = min(stats[key], cap)

    return stats


def calc_max_exp(level: int) -> int:
    """EXP required to reach (level + 1)."""
    return 100 * level * (level + 5)


def calc_training_exp(level: int, minutes: int) -> int:
    """EXP gained from training for `minutes` minutes.

    Formula: 50 * level * minutes
    """
    return 50 * level * minutes


def quality_rating(ivs: dict[str, int]) -> str:
    """根据IV总和返回品质标签（基于 QUALITY_RANGES 和 QUALITY_INDEX_TO_LABEL）。

    E: 0-30, D: 31-60, C: 61-90, B: 91-120, A: 121-150, S: 151-186
    """
    s = sum(ivs.values())
    for idx, (lo, hi) in QUALITY_RANGES.items():
        if lo <= s <= hi:
            return QUALITY_INDEX_TO_LABEL[idx]
    return "E"  # fallback


def calc_cp(pet) -> int:
    """计算综合战斗力 CP（Combat Power）。

    Formula: CP = HP×0.05 + ATK×2 + DEF×1.5 + SPD×800 + CRIT%×15 + EVA%×12
    参见 gameplay.md §一.1 注脚。

    Args:
        pet: Pet 数据对象

    Returns:
        四舍五入的整数 CP
    """
    cp = (pet.hp * 0.05 + pet.atk * 2 + getattr(pet, 'def_', 0) * 1.5 +
          pet.spd * 800 + pet.crit * 15 + pet.eva * 12)
    return int(round(cp))


def quality_label(quality: str) -> str:
    """Chinese label for quality."""
    labels = {"S": "传说", "A": "卓越", "B": "优秀", "C": "不错", "D": "一般", "E": "普通"}
    return labels.get(quality, quality)


def format_battle_stats(pet) -> str:
    """Format battle stats as display text."""
    stage_names = ["一阶", "二阶", "三阶"]
    stage = stage_names[pet.evolution_stage] if pet.evolution_stage < 3 else "三阶"
    type_names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
    btype = type_names.get(pet.battle_type, pet.battle_type)

    # Progress bar for EXP
    ratio = pet.exp / pet.max_exp if pet.max_exp > 0 else 0
    bar_len = 10
    filled = int(ratio * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    # Training status
    import time
    training_info = ""
    if pet.training:
        elapsed = int((time.time() - pet.training_start) / 60)
        training_info = f"\n⏳ 训练中 (已训练 {elapsed} 分钟)"

    q = pet.quality
    q_label = quality_label(q)

    return (
        f"🐷 【{pet.species_name}】 ({pet.game_uid})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⭐ 品质：{q_label}({q})  |  {stage}  |  {btype}\n"
        f"📊 Lv.{pet.level}  |  EXP: {bar} {pet.exp}/{pet.max_exp}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❤️ HP: {pet.hp:.0f}     ⚔️ ATK: {pet.atk:.0f}\n"
        f"🛡️ DEF: {pet.def_:.0f}     ⚡ SPD: {pet.spd:.2f}\n"
        f"💥 CRIT: {pet.crit:.1f}%   🔪 CRIT_DMG: {pet.crit_dmg*100:.0f}%\n"
        f"👻 EVA: {pet.eva:.1f}%    🩸 吸血: {pet.lifesteal*100:.0f}%"
        f"{training_info}"
    )


def format_iv_detail(pet) -> str:
    """Format detailed IV display."""
    stars = lambda v: "★" * (v // 6) + "☆" * (5 - v // 6)
    return (
        f"📊 IV 详情：\n"
        f"  HP:  {pet.iv_hp:2d}/31 {stars(pet.iv_hp)}\n"
        f"  ATK: {pet.iv_atk:2d}/31 {stars(pet.iv_atk)}\n"
        f"  DEF: {pet.iv_def:2d}/31 {stars(pet.iv_def)}\n"
        f"  SPD: {pet.iv_spd:2d}/31 {stars(pet.iv_spd)}\n"
        f"  CRIT:{pet.iv_crit:2d}/31 {stars(pet.iv_crit)}\n"
        f"  EVA: {pet.iv_eva:2d}/31 {stars(pet.iv_eva)}\n"
        f"  总和: {pet.iv_sum}/186  —  品质: {pet.quality}({quality_label(pet.quality)})"
    )
