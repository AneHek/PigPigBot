"""
passive_config.py — 被动技能配置表。

28 种被动技能，分为攻击/防御/速度/特殊四类。
技能来源：副本掉落。升级消耗同名技能书，最高 10 级。
"""

PASSIVE_SKILLS = {
    "PS_A01": {"name": "蛮力印记", "category": "attack", "stat": "atk",
               "pct_per_level": [3, 4.2, 5.4, 6.6, 7.8, 9, 9.9, 10.8, 11.4, 12]},
    "PS_A02": {"name": "锐利之眼", "category": "attack", "stat": "crit",
               "pct_per_level": [2, 2.8, 3.6, 4.4, 5.2, 6, 6.6, 7.2, 7.6, 8]},
    "PS_A03": {"name": "暴击精通", "category": "attack", "stat": "crit_dmg",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_A04": {"name": "破甲之力", "category": "attack", "stat": "def_pen",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_A05": {"name": "技能增幅", "category": "attack", "stat": "skill_dmg",
               "pct_per_level": [4, 5.2, 6.4, 7.6, 8.8, 10, 11.2, 12.4, 13.6, 15]},
    "PS_A06": {"name": "连击本能", "category": "attack", "stat": "extra_attack",
               "pct_per_level": [5, 6.4, 7.8, 9.2, 10.6, 12, 13.6, 15.2, 16.6, 18]},
    "PS_A07": {"name": "致命一击", "category": "attack", "stat": "crit_bonus_dmg",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_A08": {"name": "战意沸腾", "category": "attack", "stat": "rage_atk",
               "pct_per_level": [1, 1.4, 1.8, 2.2, 2.6, 3, 3.3, 3.6, 3.8, 4]},

    "PS_D01": {"name": "坚韧体魄", "category": "defense", "stat": "hp",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_D02": {"name": "铁壁", "category": "defense", "stat": "def",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_D03": {"name": "生命回复", "category": "defense", "stat": "hp_regen",
               "pct_per_level": [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]},
    "PS_D04": {"name": "减伤护体", "category": "defense", "stat": "dmg_reduce",
               "pct_per_level": [2, 2.6, 3.2, 3.8, 4.4, 5, 5.8, 6.6, 7.4, 8]},
    "PS_D05": {"name": "格挡本能", "category": "defense", "stat": "block",
               "pct_per_level": [8, 9.4, 10.8, 12.2, 13.6, 15, 16.2, 17.4, 18.8, 20]},
    "PS_D06": {"name": "不屈意志", "category": "defense", "stat": "last_stand_def",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_D07": {"name": "反刺甲", "category": "defense", "stat": "thorns",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_D08": {"name": "最后防线", "category": "defense", "stat": "revive_hp",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},

    "PS_S01": {"name": "敏捷步伐", "category": "speed", "stat": "spd",
               "pct_per_level": [2, 2.6, 3.2, 3.8, 4.4, 5, 5.8, 6.6, 7.4, 8]},
    "PS_S02": {"name": "残影", "category": "speed", "stat": "eva",
               "pct_per_level": [2, 2.6, 3.2, 3.8, 4.4, 5, 5.8, 6.6, 7.4, 8]},
    "PS_S03": {"name": "急速冷却", "category": "speed", "stat": "cd_reduce",
               "pct_per_level": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]},
    "PS_S04": {"name": "先手优势", "category": "speed", "stat": "opening_spd",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_S05": {"name": "闪避反击", "category": "speed", "stat": "dodge_counter",
               "pct_per_level": [10, 13.6, 17.2, 20.8, 24.4, 28, 31, 34, 37, 40]},
    "PS_S06": {"name": "时间扭曲", "category": "speed", "stat": "spd_flat",
               "pct_per_level": [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12]},

    "PS_X01": {"name": "吸血本能", "category": "special", "stat": "lifesteal",
               "pct_per_level": [1, 1.4, 1.8, 2.2, 2.6, 3, 3.5, 4, 4.5, 5]},
    "PS_X02": {"name": "穿透打击", "category": "special", "stat": "penetration",
               "pct_per_level": [2, 2.6, 3.2, 3.8, 4.4, 5, 5.8, 6.6, 7.4, 8]},
    "PS_X03": {"name": "元素亲和", "category": "special", "stat": "dot_dmg",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_X04": {"name": "净化之体", "category": "special", "stat": "debuff_reduce",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_X05": {"name": "战利品猎手", "category": "special", "stat": "gold_bonus",
               "pct_per_level": [5, 6.8, 8.6, 10.4, 12.2, 14, 15.5, 17, 18.5, 20]},
    "PS_X06": {"name": "混沌共鸣", "category": "special", "stat": "skill_no_cd",
               "pct_per_level": [10, 11.8, 13.6, 15.4, 17.2, 19, 20.5, 22, 23.5, 25]},
}

UPGRADE_COSTS = [0, 1, 2, 2, 3, 3, 4, 5, 6, 8]

CHAPTER_DROP_POOL = {
    1: ["PS_A01", "PS_D01", "PS_S01", "PS_X05"],
    2: ["PS_A01", "PS_A02", "PS_D01", "PS_D02", "PS_S01", "PS_S02", "PS_X01", "PS_X05"],
    3: ["PS_A02", "PS_A03", "PS_D02", "PS_D03", "PS_S02", "PS_S03", "PS_X01", "PS_X03", "PS_X05"],
    4: ["PS_A03", "PS_A04", "PS_D03", "PS_D04", "PS_S03", "PS_S04", "PS_X02", "PS_X03"],
    5: ["PS_A04", "PS_A05", "PS_A07", "PS_D04", "PS_D05", "PS_D07", "PS_S04", "PS_S05", "PS_X02", "PS_X03", "PS_X04"],
    6: ["PS_A05", "PS_A06", "PS_A07", "PS_D05", "PS_D06", "PS_D07", "PS_S04", "PS_S05", "PS_S06", "PS_X04"],
    7: ["PS_A06", "PS_A07", "PS_A08", "PS_D06", "PS_D07", "PS_D08", "PS_S05", "PS_S06", "PS_X04", "PS_X06"],
}

STAGE_DROP_RATE = {
    "1": 0.08,
    "2": 0.10,
    "3": 0.12,
    "boss": 0.20,
    "hide": 0.30,
}

STAGE_FIRST_BONUS_RATE = {
    "1": 0.10,
    "2": 0.12,
    "3": 0.15,
    "boss": 0.25,
    "hide": 0.30,
}

MAX_PASSIVE_LEVEL = 10
PASSIVE_SLOTS = 4
RESET_COST = 5
