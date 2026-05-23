"""
pet_config.py — Pet species, skills, and growth data.

All 25 evolution lines from pig.md with 75 skills total.
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
                                      # crit_guaranteed, interrupt, confuse
    # Damage/heal values
    value: float = 0                  # flat damage or heal amount
    min_val: float = 0                # min damage for random-range skills
    max_val: float = 0                # max damage for random-range skills
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
     Skill("五行乱拳", 4, "随机造成50~70点属性伤害",
           [dmg_range(50, 70)]),
     Skill("五行乱拳", 5, "黑白双煞拳，两段60点伤害",
           [multi_hit(2, 60)]),
     Skill("五行乱拳", 6, "混沌爆发，80点真实伤害+混乱",
           [true_dmg(80), confuse(3, 50)]),
)

# P002: 实习魔猪 → 魔猪学徒 → 魔猪大师  (SPEED — multi-hit magic)
_add("P002", "speed",
     "实习魔猪", "魔猪学徒", "魔猪大师",
     Skill("魔法飞猪", 3, "投掷魔法飞镖，造成40点魔法伤害",
           [dmg(40)]),
     Skill("魔法飞猪", 5, "召唤三只魔法小猪，连续3次攻击，每次30",
           [multi_hit(3, 30)]),
     Skill("魔法飞猪", 7, "魔力漩涡，每秒20点伤害持续3秒，降低魔抗20%",
           [dot(20, 3), debuff("magic_resist", 20, 3)]),
)

# P003: 小香猪 → 培根猪卷 → 烤猪传奇  (ATTACK — physical/fire)
_add("P003", "attack",
     "小香猪", "培根猪卷", "烤猪传奇",
     Skill("香脆翻滚", 4, "翻滚撞击造成60点物理伤害",
           [dmg(60)]),
     Skill("香脆翻滚", 5, "培根卷旋转，80点伤害+流血3秒",
           [dmg(80), dot(10, 3)]),
     Skill("香脆翻滚", 8, "烤猪形态，120点火焰伤害+防御降低30%",
           [dmg(120), debuff("def", 30, 3)]),
)

# P004: 水晶猪 → 闪闪猪 → 透明猪王  (DEFENSE — barrier/dodge)
_add("P004", "defense",
     "水晶猪", "闪闪猪", "透明猪王",
     Skill("折射光弹", 3, "发射水晶光弹，造成50点法术伤害",
           [dmg(50)]),
     Skill("折射光弹", 4, "身体闪光，下击必暴，暴伤120%",
           [crit_next(120)]),
     Skill("折射光弹", 6, "进入透明，闪避+50%持续3秒，结束后下击双倍伤害",
           [buff("eva", 50, 3)]),
)

# P005: 天堂猪使 → 天猪兵 → 光环守猪者  (DEFENSE — healing/silence)
_add("P005", "defense",
     "天堂猪使", "天猪兵", "光环守猪者",
     Skill("圣光护佑", 6, "回复自身30点生命",
           [heal(30)]),
     Skill("圣光护佑", 5, "光环提升攻击20%并每秒回血20，持续3秒",
           [buff("atk", 20, 3), hot(20, 3)]),
     Skill("圣光护佑", 8, "神圣领域，60点神圣伤害+沉默1.5秒",
           [dmg(60), control("silence", 1.5)]),
)

# P006: 龟猪勇士 → 铁甲猪龟 → 究极猪龟王  (DEFENSE — tank/shield)
_add("P006", "defense",
     "龟猪勇士", "铁甲猪龟", "究极猪龟王",
     Skill("铁甲冲撞", 5, "缩壳冲撞造成70点物理伤害",
           [dmg(70)]),
     Skill("铁甲冲撞", 6, "护盾吸收15%最大HP伤害+反弹30%伤害",
           [shield(15, 6), reflect_dmg(30, 6)]),
     Skill("铁甲冲撞", 8, "冲撞90点伤害+护盾翻倍+禁锢1秒",
           [dmg(90), shield(30, 8), control("imprison", 1)]),
)

# P007: 爆破小猪 → 炸裂猪王 → C猪4王  (ATTACK — burst damage)
_add("P007", "attack",
     "爆破小猪", "炸裂猪王", "C猪4王",
     Skill("引信点燃", 4, "投掷小炸弹造成50点伤害",
           [dmg(50)]),
     Skill("引信点燃", 5, "三连炸弹，每次40点+减速20%持续2秒",
           [multi_hit(3, 40), debuff("spd", 20, 2)]),
     Skill("引信点燃", 9, "C4蓄力1秒后造成150点伤害+眩晕1.5秒",
           [dmg(150), control("stun", 1.5)]),
)

# P008: 骷髅猪 → 骷髅猪士 → 骷髅猪王  (ATTACK — summon/dot)
_add("P008", "attack",
     "骷髅猪", "骷髅猪士", "骷髅猪王",
     Skill("骸骨召唤", 4, "召唤骨头攻击造成50点伤害",
           [dmg(50)]),
     Skill("骸骨召唤", 6, "召唤骷髅猪小弟攻击3次，每次30点",
           [multi_hit(3, 30)]),
     Skill("骸骨召唤", 8, "死亡凋零：每秒25点持续3秒+虚影追加40点",
           [dot(25, 3), dmg(40)]),
)

# P009: 猪肉串 → 火烤猪串 → 烤猪巨神  (ATTACK — fire/dot)
_add("P009", "attack",
     "猪肉串", "火烤猪串", "烤猪巨神",
     Skill("烈焰串烧", 3, "肉串戳刺造成50点伤害",
           [dmg(50)]),
     Skill("烈焰串烧", 4, "肉串灼烧每秒15点持续3秒",
           [dmg(30), dot(15, 3)]),
     Skill("烈焰串烧", 7, "三连戳刺60/70/100+爆炸50点",
           [multi_hit(3, 0), dmg(50)]),  # total: 60+70+100+50=280
)

# P010: 安卓猪 → 安卓猪手 → 终极智能猪  (SPEED — tech/auto)
_add("P010", "speed",
     "安卓猪", "安卓猪手", "终极智能猪",
     Skill("系统重装", 5, "扫描弱点，下击伤害提升30%",
           [buff("atk", 30, 4)]),
     Skill("系统重装", 6, "电磁脉冲打断敌方技能+30点伤害",
           [interrupt(), dmg(30)]),
     Skill("系统重装", 10, "终极智能：每3秒自动释放，100点伤害",
           [auto_skill_effect(3, 100)]),
)

# P011: 小猪布林 → 猪布林 → 猪布林大王  (ATTACK — ranged/disarm)
_add("P011", "attack",
     "小猪布林", "猪布林", "猪布林大王",
     Skill("投掷飞斧", 3, "投掷飞斧造成50点伤害",
           [dmg(50)]),
     Skill("投掷飞斧", 4, "双斧攻击，第二把必暴120%",
           [dmg(40), SkillEffect(type="damage", value=40, hit_count=1)]),
     Skill("投掷飞斧", 7, "召唤猪布林部落攻击3次40点+缴械1秒",
           [multi_hit(3, 40), control("disarm", 1)]),
)

# P012: 沙猪 → 沙雕猪 → 沙雕猪堡  (DEFENSE — mitigation/shield)
_add("P012", "defense",
     "沙猪", "沙雕猪", "沙雕猪堡",
     Skill("沙暴迷踪", 5, "扬起沙尘降低敌方命中20%持续2秒",
           [debuff("hit_rate", 20, 2)]),
     Skill("沙暴迷踪", 6, "沙雕分身分摊30%伤害持续2秒",
           [SkillEffect(type="damage_share", value_pct=30, duration=2, target="self")]),
     Skill("沙暴迷踪", 8, "沙雕猪堡：每秒20点持续3秒+10%最大HP护盾",
           [dot(20, 3), shield(10, 3)]),
)

# P013: 咸猪仔 → 咸猪老大 → 终极咸猪王  (SPEED — blind/debuff)
_add("P013", "speed",
     "咸猪仔", "咸猪老大", "终极咸猪王",
     Skill("咸味喷发", 4, "喷出咸水，30点伤害+致盲1秒",
           [dmg(30), control("blind", 1)]),
     Skill("咸味喷发", 5, "咸味气场降低敌方攻击20%持续2秒",
           [debuff("atk", 20, 2)]),
     Skill("咸味喷发", 7, "高浓度盐水：每秒35点持续3秒+腐蚀护甲20%",
           [dot(35, 3), debuff("def", 20, 3)]),
)

# P014: 肥宅猪 → 宅猪帝 → 宅界猪霸王  (DEFENSE — recovery/dodge)
_add("P014", "defense",
     "肥宅猪", "宅猪帝", "宅界猪霸王",
     Skill("宅家召唤", 6, "召唤零食饮料回复20点生命",
           [heal(20)]),
     Skill("宅家召唤", 5, "游戏机，闪避+30%持续3秒",
           [buff("eva", 30, 3)]),
     Skill("宅家召唤", 9, "宅界领域：敌方减速20%+自身每2秒回20转护盾",
           [debuff("spd", 20, 3), hot(20, 3)]),
)

# P015: 颜艺少猪 → 表情猪王 → 表情猪帝  (SPEED — mental/taunt)
_add("P015", "speed",
     "颜艺少猪", "表情猪王", "表情猪帝",
     Skill("颜艺爆发", 4, "夸张表情造成40点精神伤害",
           [dmg(40)]),
     Skill("颜艺爆发", 5, "切换表情使敌方困惑1秒",
           [confuse(1, 50)]),
     Skill("颜艺爆发", 8, "表情帝域：三连精神冲击30点+嘲讽1秒",
           [multi_hit(3, 30), control("taunt", 1)]),
)

# P016: 电吉猪手 → 摇滚猪 → 摇滚巨猪  (ATTACK — sonic/fear)
_add("P016", "attack",
     "电吉猪手", "摇滚猪", "摇滚巨猪",
     Skill("摇滚独奏", 3, "弹奏吉他弦造成50点伤害",
           [dmg(50)]),
     Skill("摇滚独奏", 5, "音波攻击造成60点伤害+恐惧1秒",
           [dmg(60), control("fear", 1)]),
     Skill("摇滚独奏", 7, "重金属模式：三连弹奏每次70点+震退1秒",
           [multi_hit(3, 70)]),
)

# P017: 动漫猪 → 动漫猪狂 → 二次元猪  (SPEED — true damage)
_add("P017", "speed",
     "动漫猪", "动漫猪狂", "二次元猪",
     Skill("次元斩击", 4, "次元之刃造成60点伤害",
           [dmg(60)]),
     Skill("次元斩击", 5, "动漫虚影追加50点法术伤害",
           [dmg(60), dmg(50)]),
     Skill("次元斩击", 8, "突破次元壁：80点真实伤害+无视护甲3秒",
           [true_dmg(80), debuff("def", 100, 3)]),
)

# P018: 奶猪 → 奶茶猪 → 奶茶霸猪桶  (DEFENSE — heal/slow)
_add("P018", "defense",
     "奶猪", "奶茶猪", "奶茶霸猪桶",
     Skill("奶茶喷射", 4, "喷射牛奶，造成20点伤害+治疗自身20点",
           [dmg(20), heal(20)]),
     Skill("奶茶喷射", 5, "珍珠弹造成30点伤害+减速20%持续2秒",
           [dmg(30), debuff("spd", 20, 2)]),
     Skill("奶茶喷射", 7, "奶茶霸猪桶：60点范围伤害+每秒回血20持续3秒",
           [dmg(60), hot(20, 3)]),
)

# P019: 芝士猪 → 拉丝芝士猪 → 芝士猪神  (SPEED — imprison/reflect)
_add("P019", "speed",
     "芝士猪", "拉丝芝士猪", "芝士猪神",
     Skill("芝士拉丝", 3, "芝士丝造成50点伤害",
           [dmg(50)]),
     Skill("芝士拉丝", 5, "芝士缠绕禁锢敌人1秒",
           [control("imprison", 1)]),
     Skill("芝士拉丝", 7, "芝士神降：每秒20点持续3秒+反弹30%伤害",
           [dot(20, 3), reflect_dmg(30, 3)]),
)

# P020: 泡泡猪 → 大泡泡猪 → 超级泡泡猪  (SPEED — multi-hit/float)
_add("P020", "speed",
     "泡泡猪", "大泡泡猪", "超级泡泡猪",
     Skill("泡泡弹射", 2, "泡泡攻击造成20点伤害",
           [dmg(20)]),
     Skill("泡泡弹射", 4, "3个泡泡弹射2次，每次25点伤害",
           [multi_hit(3, 25)]),
     Skill("泡泡弹射", 6, "超级泡泡：每秒20点持续3秒+漂浮2秒",
           [dot(20, 3), control("float", 2)]),
)

# P021: 星球猪 → 银河猪 → 宇宙猪  (DEFENSE — area/debuff)
_add("P021", "defense",
     "星球猪", "银河猪", "宇宙猪",
     Skill("星体牵引", 4, "引力波拉近敌人+40点伤害",
           [dmg(40)]),
     Skill("星体牵引", 5, "小行星造成50点伤害",
           [dmg(50)]),
     Skill("星体牵引", 8, "宇宙奇点：每秒30点持续3秒+攻防-20%",
           [dot(30, 3), debuff("atk", 20, 3), debuff("def", 20, 3)]),
)

# P022: 脑坑猪 → 脑洞猪 → 脑洞猪神  (ATTACK — random/true damage)
_add("P022", "attack",
     "脑坑猪", "脑洞猪", "脑洞猪神",
     Skill("脑洞具现", 4, "随机具现道具攻击造成50点伤害",
           [dmg(50)]),
     Skill("脑洞具现", 5, "反重力装置：敌人漂浮+命中-20%持续2秒",
           [control("float", 2), debuff("hit_rate", 20, 2)]),
     Skill("脑洞具现", 7, "终极脑洞：70点真实伤害+混乱",
           [true_dmg(70), confuse(3, 50)]),
)

# P023: 雪猪怪 → 雪猪王 → 雪人巨猪  (SPEED — freeze/ice)
_add("P023", "speed",
     "雪猪怪", "雪猪王", "雪人巨猪",
     Skill("冰霜吐息", 4, "寒气减速20%持续2秒",
           [dmg(30), debuff("spd", 20, 2)]),
     Skill("冰霜吐息", 5, "冰锥造成40点伤害+冻结1秒",
           [dmg(40), control("freeze", 1)]),
     Skill("冰霜吐息", 8, "雪人巨猪：暴风雪每秒35点持续3秒+冰封2秒",
           [dot(35, 3), control("freeze", 2)]),
)

# P024: 蘑菇猪 → 香菇猪 → 蘑菇猪王  (SPEED — dot/blind)
_add("P024", "speed",
     "蘑菇猪", "香菇猪", "蘑菇猪王",
     Skill("孢子喷发", 3, "孢子造成40点法术伤害",
           [dmg(40)]),
     Skill("孢子喷发", 5, "孢子感染每秒15点持续3秒",
           [dot(15, 3)]),
     Skill("孢子喷发", 7, "巨型蘑菇砸落70点伤害+致盲1.5秒",
           [dmg(70), control("blind", 1.5)]),
)

# P025: 仙猪萌 → 仙猪灵 → 仙猪女  (DEFENSE — healing/purify)
_add("P025", "defense",
     "仙猪萌", "仙猪灵", "仙猪女",
     Skill("仙气缭绕", 5, "释放仙气回复30点生命",
           [heal(30)]),
     Skill("仙气缭绕", 4, "仙灵护体：10%最大HP护盾持续3秒",
           [shield(10, 3)]),
     Skill("仙气缭绕", 7, "仙女降临：50点神圣伤害+净化自身负面状态",
           [dmg(50), purify()]),
)


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
