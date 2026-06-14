"""
pet_config.py — Pet species, skills, and growth data.

All 25 evolution lines from pig.md with skills.
Growth rates match levelandAtt.md tables exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Skill / SkillEffect dataclasses ──


@dataclass
class SkillEffect:
    """A single effect within a skill. All fields optional, resolved by BattleEngine."""
    type: str = ""                    # damage, dot, debuff, control, buff, heal, hot,
                                      # shield, reflect, true_damage, purify,
                                      # crit_guaranteed, interrupt, confuse, reset_skills
    # Damage/heal values
    value: float = 0                  # flat damage or heal amount
    min_val: float = 0                # min damage for random-range skills
    max_val: float = 0                # max damage for random-range skills
    # Percentage-based scaling (resolved at battle time)
    atk_pct: float = 0               # damage = attacker.atk * atk_pct / 100
    hp_pct: float = 0                # heal = source.max_hp * hp_pct / 100
    dot_atk_pct: float = 0           # dot_per_tick = attacker.atk * dot_atk_pct / 100
    # Dot/HoT
    damage_per_tick: float = 0
    tick_interval: float = 1.0
    # Debuff/buff
    stat: str = ""                    # atk, def, spd, crit, eva, lifesteal, hit_rate, magic_resist
    stat_pct: float = 0               # percentage change (e.g. 20 = 20%)
    # Control
    control_type: str = ""            # stun, freeze, silence, disarm, imprison, fear, taunt, confuse, float
    # Common
    duration: float = 0               # seconds
    target: str = "enemy"             # enemy or self
    # Multi-hit
    hit_count: int = 1                # number of hits
    # Crit guarantee
    crit_dmg_pct: float = 0           # override crit_dmg for this hit
    # Reflect/shield
    value_pct: float = 0              # percentage-based (e.g. 30% shield or reflect)
    # Confuse
    confuse_chance: float = 0         # 0-100, chance to self-attack
    # Purge self-buff purge flag
    purge_buffs: bool = False         # True = remove all negative effects
    # Interrupt
    interrupt_target: bool = False    # True = interrupt current skill
    # Auto-skill mechanic (P010 stage3)
    auto_interval: float = 0          # if > 0, auto-trigger this skill every N seconds


@dataclass
class Skill:
    """A pet's active skill."""
    name: str
    cd: float                         # cooldown in seconds
    description: str = ""
    effects: list[SkillEffect] = field(default_factory=list)

    def to_effects(self) -> list[dict[str, Any]]:
        """Convert to dict list for JSON serialization."""
        return [{
            "type": e.type, "value": e.value, "min_val": e.min_val, "max_val": e.max_val,
            "atk_pct": e.atk_pct, "hp_pct": e.hp_pct, "dot_atk_pct": e.dot_atk_pct,
            "damage_per_tick": e.damage_per_tick, "tick_interval": e.tick_interval,
            "stat": e.stat, "stat_pct": e.stat_pct,
            "control_type": e.control_type, "duration": e.duration, "target": e.target,
            "hit_count": e.hit_count, "crit_dmg_pct": e.crit_dmg_pct,
            "value_pct": e.value_pct, "confuse_chance": e.confuse_chance,
            "purge_buffs": e.purge_buffs, "interrupt_target": e.interrupt_target,
            "auto_interval": e.auto_interval,
        } for e in self.effects]

    @classmethod
    def from_effects(cls, name: str, cd: float, description: str,
                     *effects: SkillEffect) -> Skill:
        return cls(name=name, cd=cd, description=description, effects=list(effects))


# ── Helper constructors ──

def dmg(value: float) -> SkillEffect:
    return SkillEffect(type="damage", value=value)

def dmg_range(min_val: float, max_val: float) -> SkillEffect:
    return SkillEffect(type="damage", min_val=min_val, max_val=max_val)

def multi_hit(count: int, per_hit: float) -> SkillEffect:
    return SkillEffect(type="damage", value=per_hit, hit_count=count)

def true_dmg(value: float) -> SkillEffect:
    return SkillEffect(type="true_damage", value=value)

def heal(value: float) -> SkillEffect:
    return SkillEffect(type="heal", value=value, target="self")

def dot(dmg_per_tick: float, duration: float, interval: float = 1.0) -> SkillEffect:
    return SkillEffect(type="dot", damage_per_tick=dmg_per_tick, duration=duration,
                       tick_interval=interval)

def hot(value: float, duration: float) -> SkillEffect:
    return SkillEffect(type="hot", damage_per_tick=value, duration=duration, target="self")

def debuff(stat: str, pct: float, duration: float) -> SkillEffect:
    """Reduce a stat by pct% for duration seconds."""
    return SkillEffect(type="debuff", stat=stat, stat_pct=pct, duration=duration)

def buff(stat: str, pct: float, duration: float) -> SkillEffect:
    return SkillEffect(type="buff", stat=stat, stat_pct=pct, duration=duration, target="self")

def control(ctype: str, duration: float) -> SkillEffect:
    return SkillEffect(type="control", control_type=ctype, duration=duration)

def confuse(duration: float, chance: float = 50) -> SkillEffect:
    return SkillEffect(type="control", control_type="confuse", duration=duration,
                       confuse_chance=chance)

def shield(pct: float, duration: float) -> SkillEffect:
    return SkillEffect(type="shield", value_pct=pct, duration=duration, target="self")

def reflect_dmg(pct: float, duration: float) -> SkillEffect:
    return SkillEffect(type="reflect", value_pct=pct, duration=duration, target="self")

def crit_next(crit_dmg_pct: float = 0) -> SkillEffect:
    return SkillEffect(type="crit_guaranteed", crit_dmg_pct=crit_dmg_pct, target="self")

def purify() -> SkillEffect:
    return SkillEffect(type="purify", purge_buffs=True, target="self")

def interrupt() -> SkillEffect:
    return SkillEffect(type="interrupt", interrupt_target=True)

def auto_skill_effect(interval: float, dmg_value: float):
    return SkillEffect(type="auto_skill", auto_interval=interval, value=dmg_value)


def dmg_pct(pct: float) -> SkillEffect:
    """ATK%-based damage: actual = attacker.atk * pct / 100"""
    return SkillEffect(type="damage", atk_pct=pct)


def dmg_range_pct(min_pct: float, max_pct: float) -> SkillEffect:
    """ATK%-based random-range damage"""
    return SkillEffect(type="damage", min_val=min_pct, max_val=max_pct, atk_pct=1)


def multi_hit_pct(count: int, pct: float) -> SkillEffect:
    """Multi-hit ATK%-based damage"""
    return SkillEffect(type="damage", atk_pct=pct, hit_count=count)


def true_dmg_pct(pct: float) -> SkillEffect:
    """ATK%-based true damage (ignores defense)"""
    return SkillEffect(type="true_damage", atk_pct=pct)


def heal_pct(hp_pct: float) -> SkillEffect:
    """MaxHP%-based heal"""
    return SkillEffect(type="heal", hp_pct=hp_pct, target="self")


def dot_pct(atk_pct: float, duration: float, interval: float = 1.0) -> SkillEffect:
    """ATK%-based DoT: per_tick = attacker.atk * atk_pct / 100"""
    return SkillEffect(type="dot", dot_atk_pct=atk_pct, duration=duration,
                       tick_interval=interval)


def hot_pct(hp_pct: float, duration: float) -> SkillEffect:
    """MaxHP%-based HoT"""
    return SkillEffect(type="hot", hp_pct=hp_pct, duration=duration, target="self")


def reset_skills_cd() -> SkillEffect:
    """Reset S1/S2 cooldowns to 0 (for P010_1_1)"""
    return SkillEffect(type="reset_skills", target="self")


# ── 25 Pet Species ──

PET_SPECIES: dict[str, dict] = {}

def _register(sid: str, battle_type: str, names: list[str], stages: list[tuple[Skill, Skill | None, str]]):
    """Register a pet species line.
    names: [一阶名, 二阶名, 三阶名]
    stages: [(skill1, None, desc), (skill1, skill2, desc), (skill1, skill2, skill3, desc)]
    """
    PET_SPECIES[sid] = {
        "id": sid,
        "battle_type": battle_type,
        "names": names,
        "skills": [
            {"skill1": s1, "desc": desc},
            {"skill1": s1, "skill2": s2, "desc": desc2} if len(stages) > 1 else stage[0],
            {"skill1": s1, "skill2": s2, "skill3": s3, "desc": desc3} if len(stages) > 2 else stage[0],
        ]
    }


# TODO: This function needs proper registration for all 25 lines
# Each line: (species_id, battle_type, [一阶名, 二阶名, 三阶名], skill1, skill2, skill3)

# Let me define them one by one using a simple helper

def _add(sid: str, battle_type: str, n0: str, n1: str, n2: str,
         s0: Skill, s1: Skill, s2: Skill):
    PET_SPECIES[sid] = {
        "id": sid,
        "battle_type": battle_type,
        "names": [n0, n1, n2],
        "skills": [s0, s1, s2],
    }


# ══════════════════════════════════════════════════════════════════════
# P001: 五行猪混混 → 黑白猪煞 → 混沌猪  (ATTACK — chaos/damage)
# ══════════════════════════════════════════════════════════════════════
_add("P001", "attack",
     "五行猪混混", "黑白猪煞", "混沌猪",
     Skill("五行乱拳", 4, "ATK×130%~180% 随机属性伤害",
           [dmg_range_pct(130, 180)]),
     Skill("五行乱拳", 5, "2次攻击各 ATK×200%",
           [multi_hit_pct(2, 200)]),
     Skill("五行乱拳", 8, "ATK×30% 真实伤害 + 混乱50% 3s",
           [true_dmg_pct(30), confuse(3, 50)]),
)

# P002: 实习魔猪 → 魔猪学徒 → 魔猪大师  (SPEED — multi-hit magic)
_add("P002", "speed",
     "实习魔猪", "魔猪学徒", "魔猪大师",
     Skill("魔法飞猪", 3, "ATK×130% 魔法伤害",
           [dmg_pct(130)]),
     Skill("魔法飞猪", 5, "3次攻击各 ATK×100%",
           [multi_hit_pct(3, 100)]),
     Skill("魔法飞猪", 8, "ATK×40%/s 持续3s + 魔抗-20%",
           [dot_pct(40, 3), debuff("magic_resist", 20, 3)]),
)

# P003: 小香猪 → 培根猪卷 → 烤猪传奇  (ATTACK — physical/fire)
_add("P003", "attack",
     "小香猪", "培根猪卷", "烤猪传奇",
     Skill("香脆翻滚", 4, "ATK×160% 物理伤害",
           [dmg_pct(160)]),
     Skill("香脆翻滚", 5, "ATK×250% + 流血 ATK×25%/s 3s",
           [dmg_pct(250), dot_pct(25, 3)]),
     Skill("香脆翻滚", 8, "ATK×400% + DEF-30% 3s",
           [dmg_pct(400), debuff("def", 30, 3)]),
)

# P004: 水晶猪 → 闪闪猪 → 透明猪王  (DEFENSE — barrier/dodge)
_add("P004", "defense",
     "水晶猪", "闪闪猪", "透明猪王",
     Skill("折射光弹", 3, "ATK×140% 法术伤害",
           [dmg_pct(140)]),
     Skill("折射光弹", 5, "下次攻击必暴，暴伤120%",
           [crit_next(120)]),
     Skill("折射光弹", 8, "EVA+30% 4s + 结束后双倍攻击",
           [buff("eva", 30, 4)]),
)

# P005: 天堂猪使 → 天猪兵 → 光环守猪者  (DEFENSE — healing/silence)
_add("P005", "defense",
     "天堂猪使", "天猪兵", "光环守猪者",
     Skill("圣光护佑", 5, "ATK×100% + 自愈 MaxHP×5%",
           [dmg_pct(100), heal_pct(5)]),
     Skill("圣光护佑", 5, "ATK×120% + ATK+20% 3s + 自愈 MaxHP×3%/s 3s",
           [dmg_pct(120), buff("atk", 20, 3), hot_pct(3, 3)]),
     Skill("圣光护佑", 8, "ATK×250% + 沉默1.5s",
           [dmg_pct(250), control("silence", 1.5)]),
)

# P006: 龟猪勇士 → 铁甲猪龟 → 究极猪龟王  (DEFENSE — tank/shield)
_add("P006", "defense",
     "龟猪勇士", "铁甲猪龟", "究极猪龟王",
     Skill("铁甲冲撞", 5, "ATK×150% 物理伤害",
           [dmg_pct(150)]),
     Skill("铁甲冲撞", 6, "护盾 MaxHP×15% + 反伤30% 6s",
           [shield(15, 6), reflect_dmg(30, 6)]),
     Skill("铁甲冲撞", 8, "ATK×300% + 护盾 MaxHP×30% + 禁锢1s",
           [dmg_pct(300), shield(30, 8), control("imprison", 1)]),
)

# P007: 爆破小猪 → 炸裂猪王 → C猪4王  (ATTACK — burst damage)
_add("P007", "attack",
     "爆破小猪", "炸裂猪王", "C猪4王",
     Skill("引信点燃", 4, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("引信点燃", 5, "3次各 ATK×130% + 减速20% 2s",
           [multi_hit_pct(3, 130), debuff("spd", 20, 2)]),
     Skill("引信点燃", 9, "ATK×500% + 眩晕1.5s",
           [dmg_pct(500), control("stun", 1.5)]),
)

# P008: 骷髅猪 → 骷髅猪士 → 骷髅猪王  (ATTACK — summon/dot)
_add("P008", "attack",
     "骷髅猪", "骷髅猪士", "骷髅猪王",
     Skill("骸骨召唤", 4, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("骸骨召唤", 6, "3次各 ATK×130%",
           [multi_hit_pct(3, 130)]),
     Skill("骸骨召唤", 8, "ATK×40%/s 3s + 虚影 ATK×180% + 致盲1s",
           [dot_pct(40, 3), dmg_pct(180), control("blind", 1)]),
)

# P009: 猪肉串 → 火烤猪串 → 烤猪巨神  (ATTACK — fire/dot)
_add("P009", "attack",
     "猪肉串", "火烤猪串", "烤猪巨神",
     Skill("烈焰串烧", 3, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("烈焰串烧", 5, "ATK×100% + 灼烧 ATK×30%/s 3s",
           [dmg_pct(100), dot_pct(30, 3)]),
     Skill("烈焰串烧", 8, "3连击 ATK×180%/200%/280% + 爆炸 ATK×150%",
           [dmg_pct(180), dmg_pct(200), dmg_pct(280), dmg_pct(150)]),
)

# P010: 安卓猪 → 安卓猪手 → 终极智能猪  (SPEED — tech/auto)
_add("P010", "speed",
     "安卓猪", "安卓猪手", "终极智能猪",
     Skill("系统重装", 4, "ATK×120% + 下次攻击+30%",
           [dmg_pct(120), buff("atk", 30, 4)]),
     Skill("系统重装", 5, "ATK×150% + 打断",
           [dmg_pct(150), interrupt()]),
     Skill("系统重装", 10, "ATK×350% + 重置S1/S2 CD",
           [dmg_pct(350), reset_skills_cd()]),
)

# P011: 小猪布林 → 猪布林 → 猪布林大王  (ATTACK — ranged/disarm)
_add("P011", "attack",
     "小猪布林", "猪布林", "猪布林大王",
     Skill("投掷飞斧", 3, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("投掷飞斧", 5, "2次各 ATK×130%，第二击必暴",
           [multi_hit_pct(2, 130), crit_next(0)]),
     Skill("投掷飞斧", 8, "3次各 ATK×140% + 缴械1s",
           [multi_hit_pct(3, 140), control("disarm", 1)]),
)

# P012: 沙猪 → 沙雕猪 → 沙雕猪堡  (DEFENSE — mitigation/shield)
_add("P012", "defense",
     "沙猪", "沙雕猪", "沙雕猪堡",
     Skill("沙暴迷踪", 4, "ATK×100% + 命中-20% 2s",
           [dmg_pct(100), debuff("hit_rate", 20, 2)]),
     Skill("沙暴迷踪", 6, "分身承伤30% 4s",
           [SkillEffect(type="damage_share", value_pct=30, duration=4, target="self")]),
     Skill("沙暴迷踪", 8, "ATK×35%/s 3s + 护盾 MaxHP×15% + 减速15% 3s",
           [dot_pct(35, 3), shield(15, 3), debuff("spd", 15, 3)]),
)

# P013: 咸猪仔 → 咸猪老大 → 终极咸猪王  (SPEED — blind/debuff)
_add("P013", "speed",
     "咸猪仔", "咸猪老大", "终极咸猪王",
     Skill("咸味喷发", 4, "ATK×100% + 致盲1s",
           [dmg_pct(100), control("blind", 1)]),
     Skill("咸味喷发", 5, "ATK×130% + ATK-20% 2s",
           [dmg_pct(130), debuff("atk", 20, 2)]),
     Skill("咸味喷发", 8, "ATK×60%/s 3s + DEF-20% 3s",
           [dot_pct(60, 3), debuff("def", 20, 3)]),
)

# P014: 肥宅猪 → 宅猪帝 → 宅界猪霸王  (DEFENSE — recovery/dodge)
_add("P014", "defense",
     "肥宅猪", "宅猪帝", "宅界猪霸王",
     Skill("宅家召唤", 5, "ATK×100% + 自愈 MaxHP×4%",
           [dmg_pct(100), heal_pct(4)]),
     Skill("宅家召唤", 5, "EVA+30% 3s",
           [buff("eva", 30, 3)]),
     Skill("宅家召唤", 9, "SPD-15% 3s + 自愈 MaxHP×3%/2s 转护盾",
           [debuff("spd", 15, 3), hot_pct(3, 3)]),
)

# P015: 颜艺少猪 → 表情猪王 → 表情猪帝  (SPEED — mental/taunt)
_add("P015", "speed",
     "颜艺少猪", "表情猪王", "表情猪帝",
     Skill("颜艺爆发", 4, "ATK×130% 精神伤害",
           [dmg_pct(130)]),
     Skill("颜艺爆发", 5, "困惑2s（50%概率）",
           [confuse(2, 50)]),
     Skill("颜艺爆发", 8, "3次各 ATK×100% + 嘲讽1s",
           [multi_hit_pct(3, 100), control("taunt", 1)]),
)

# P016: 电吉猪手 → 摇滚猪 → 摇滚巨猪  (ATTACK — sonic/fear)
_add("P016", "attack",
     "电吉猪手", "摇滚猪", "摇滚巨猪",
     Skill("摇滚独奏", 3, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("摇滚独奏", 5, "ATK×200% + 恐惧1s",
           [dmg_pct(200), control("fear", 1)]),
     Skill("摇滚独奏", 8, "3次各 ATK×230% + 震退1s",
           [multi_hit_pct(3, 230), control("fear", 1)]),
)

# P017: 动漫猪 → 动漫猪狂 → 二次元猪  (SPEED — true damage)
_add("P017", "speed",
     "动漫猪", "动漫猪狂", "二次元猪",
     Skill("次元斩击", 4, "ATK×160% 伤害",
           [dmg_pct(160)]),
     Skill("次元斩击", 5, "ATK×220% 法术伤害",
           [dmg_pct(220)]),
     Skill("次元斩击", 8, "ATK×30% 真实伤害 + 无视护甲3s",
           [true_dmg_pct(30), debuff("def", 100, 3)]),
)

# P018: 奶猪 → 奶茶猪 → 奶茶霸猪桶  (DEFENSE — heal/slow)
_add("P018", "defense",
     "奶猪", "奶茶猪", "奶茶霸猪桶",
     Skill("奶茶喷射", 4, "ATK×80% + 自愈 MaxHP×4%",
           [dmg_pct(80), heal_pct(4)]),
     Skill("奶茶喷射", 5, "ATK×150% + 减速20% 2s",
           [dmg_pct(150), debuff("spd", 20, 2)]),
     Skill("奶茶喷射", 8, "ATK×250% + 自愈 MaxHP×4%/s 3s",
           [dmg_pct(250), hot_pct(4, 3)]),
)

# P019: 芝士猪 → 拉丝芝士猪 → 芝士猪神  (SPEED — imprison/reflect)
_add("P019", "speed",
     "芝士猪", "拉丝芝士猪", "芝士猪神",
     Skill("芝士拉丝", 3, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("芝士拉丝", 5, "禁锢1s",
           [control("imprison", 1)]),
     Skill("芝士拉丝", 8, "ATK×35%/s 3s + 反伤30% 3s",
           [dot_pct(35, 3), reflect_dmg(30, 3)]),
)

# P020: 泡泡猪 → 大泡泡猪 → 超级泡泡猪  (SPEED — multi-hit/float)
_add("P020", "speed",
     "泡泡猪", "大泡泡猪", "超级泡泡猪",
     Skill("泡泡弹射", 3, "ATK×100% 伤害",
           [dmg_pct(100)]),
     Skill("泡泡弹射", 5, "3次各 ATK×100%",
           [multi_hit_pct(3, 100)]),
     Skill("泡泡弹射", 8, "ATK×35%/s 3s + 漂浮2.5s",
           [dot_pct(35, 3), control("float", 2.5)]),
)

# P021: 星球猪 → 银河猪 → 宇宙猪  (DEFENSE — area/debuff)
_add("P021", "defense",
     "星球猪", "银河猪", "宇宙猪",
     Skill("星体牵引", 4, "ATK×130% 伤害",
           [dmg_pct(130)]),
     Skill("星体牵引", 5, "ATK×220% 伤害",
           [dmg_pct(220)]),
     Skill("星体牵引", 8, "ATK×50%/s 3s + 攻防-20% 3s",
           [dot_pct(50, 3), debuff("atk", 20, 3), debuff("def", 20, 3)]),
)

# P022: 脑坑猪 → 脑洞猪 → 脑洞猪神  (ATTACK — random/true damage)
_add("P022", "attack",
     "脑坑猪", "脑洞猪", "脑洞猪神",
     Skill("脑洞具现", 4, "ATK×140% 伤害",
           [dmg_pct(140)]),
     Skill("脑洞具现", 5, "漂浮2s + 命中-20% 2s",
           [control("float", 2), debuff("hit_rate", 20, 2)]),
     Skill("脑洞具现", 8, "ATK×25% 真实伤害 + 混乱50% 3s",
           [true_dmg_pct(25), confuse(3, 50)]),
)

# P023: 雪猪怪 → 雪猪王 → 雪人巨猪  (SPEED — freeze/ice)
_add("P023", "speed",
     "雪猪怪", "雪猪王", "雪人巨猪",
     Skill("冰霜吐息", 4, "ATK×100% + 减速20% 2s",
           [dmg_pct(100), debuff("spd", 20, 2)]),
     Skill("冰霜吐息", 5, "ATK×160% + 冻结1s",
           [dmg_pct(160), control("freeze", 1)]),
     Skill("冰霜吐息", 8, "ATK×60%/s 3s + 冰封2s",
           [dot_pct(60, 3), control("freeze", 2)]),
)

# P024: 蘑菇猪 → 香菇猪 → 蘑菇猪王  (SPEED — dot/blind)
_add("P024", "speed",
     "蘑菇猪", "香菇猪", "蘑菇猪王",
     Skill("孢子喷发", 3, "ATK×130% 法术伤害",
           [dmg_pct(130)]),
     Skill("孢子喷发", 5, "ATK×30%/s 3s",
           [dot_pct(30, 3)]),
     Skill("孢子喷发", 8, "ATK×280% + 致盲1.5s",
           [dmg_pct(280), control("blind", 1.5)]),
)

# P025: 仙猪萌 → 仙猪灵 → 仙猪女  (DEFENSE — healing/purify)
_add("P025", "defense",
     "仙猪萌", "仙猪灵", "仙猪女",
     Skill("仙气缭绕", 5, "ATK×100% + 自愈 MaxHP×5%",
           [dmg_pct(100), heal_pct(5)]),
     Skill("仙气缭绕", 5, "护盾 MaxHP×10% 3s",
           [shield(10, 3)]),
     Skill("仙气缭绕", 8, "ATK×200% + 净化",
           [dmg_pct(200), purify()]),
)


# ══════════════════════════════════════════════════════════════════════
# Pet Image URL Mapping
# ══════════════════════════════════════════════════════════════════════

def get_pet_image_url(species_id: str, evolution_stage: int,
                      pig_source: str, callback_domain: str) -> str:
    """根据宠物ID和进化阶段计算对应形象图片的完整URL。

    Args:
        species_id: "P001" ~ "P025"
        evolution_stage: 0/1/2
        pig_source: 图片来源目录名（如 "cropped_pigs1"）
        callback_domain: 回调域名（含协议）

    Returns:
        完整的图片URL字符串
    """
    return f"{callback_domain}/static/images/{pig_source}/{species_id}_{evolution_stage}.png"


def get_pet_image_local_path(species_id: str, evolution_stage: int,
                              base_dir: str) -> str:
    """根据宠物ID和进化阶段计算本地图片绝对路径（用于Playwright渲染）。

    Args:
        species_id: "P001" ~ "P025"
        evolution_stage: 0/1/2
        base_dir: 宠物形象图本地绝对路径基础目录（如 "D:/QQBot/data/images/cropped_pigs1"）
                  需在 config.yaml image.pet_image_base_dir 中配置为绝对路径

    Returns:
        本地图片文件绝对路径
    """
    return f"{base_dir}/{species_id}_{evolution_stage}.png"


# ══════════════════════════════════════════════════════════════════════
# Growth Tables (from levelandAtt.md §六)
# ══════════════════════════════════════════════════════════════════════

PET_GROWTH: dict[str, dict[str, tuple[float, float]]] = {
    # battle_type → {stat: (base_initial, per_level_growth)}
    "attack": {
        "hp":    (520, 42),
        "atk":   (65, 8.3),
        "def":   (18, 4.2),
        "spd":   (0.58, 0.0083),
        "crit":  (8, 0.42),
        "eva":   (4, 0.12),
    },
    "defense": {
        "hp":    (650, 75),
        "atk":   (40, 3.3),
        "def":   (30, 11.5),
        "spd":   (0.50, 0.0041),
        "crit":  (4, 0.17),
        "eva":   (5, 0.08),
    },
    "speed": {
        "hp":    (430, 29),
        "atk":   (55, 5.0),
        "def":   (18, 3.3),
        "spd":   (0.65, 0.0116),
        "crit":  (6, 0.25),
        "eva":   (6, 0.23),
    },
}

# Evolution coefficient: E = 1.0/1.1/1.21 for stage 0/1/2
EVOLUTION_COEFFICIENTS = [1.00, 1.10, 1.21]

# Fixed stats by stage
FIXED_STATS = {
    # stage: {crit_dmg, lifesteal}
    0: {"crit_dmg": 1.50, "lifesteal": 0.05},
    1: {"crit_dmg": 1.60, "lifesteal": 0.08},
    2: {"crit_dmg": 1.70, "lifesteal": 0.11},
}

# Stat caps
STAT_CAPS = {
    "spd": 2.00,
    "crit": 75.0,
    "eva": 60.0,
    "lifesteal": 35.0,
    "crit_dmg": 300.0,
}
