"""
pet_stats.py — IV generation, attribute calculation, formulas.

Based on levelandAtt.md design document.
"""
import random

from src.pet_config import PET_GROWTH, EVOLUTION_COEFFICIENTS, FIXED_STATS, STAT_CAPS


def generate_ivs() -> dict[str, int]:
    """Generate 6 IVs using normal distribution μ=15 σ=7, clamped [0,31].

    Returns dict with keys: iv_hp, iv_atk, iv_def, iv_spd, iv_crit, iv_eva
    """
    ivs = {}
    for key in ["iv_hp", "iv_atk", "iv_def", "iv_spd", "iv_crit", "iv_eva"]:
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
    """Map total IV sum to quality rating.

    E: 0-30, D: 31-60, C: 61-90, B: 91-120, A: 121-150, S: 151-186
    """
    s = sum(ivs.values())
    if s >= 151: return "S"
    if s >= 121: return "A"
    if s >= 91:  return "B"
    if s >= 61:  return "C"
    if s >= 31:  return "D"
    return "E"


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
        f"🐷 【{pet.species_name}】 {pet.name}\n"
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
