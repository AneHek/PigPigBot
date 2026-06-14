CHAPTERS = {
    1: {"name": "萌新猪舍", "level_range": (1, 14), "boss": "草棚大王", "cp_range": (200, 800)},
    2: {"name": "翠玉猪林", "level_range": (15, 29), "boss": "林中巨猪", "cp_range": (900, 2400)},
    3: {"name": "进化之塔", "level_range": (30, 44), "boss": "塔顶长老猪", "cp_range": (2800, 5500)},
    4: {"name": "深渊之底", "level_range": (45, 59), "boss": "深渊猪神", "cp_range": (6000, 11000)},
    5: {"name": "星空之巅", "level_range": (60, 74), "boss": "银河猪皇", "cp_range": (12000, 22000)},
    6: {"name": "仙猪秘境", "level_range": (75, 89), "boss": "仙猪道人", "cp_range": (24000, 42000)},
    7: {"name": "宇宙之心", "level_range": (90, 100), "boss": "宇宙猪神", "cp_range": (45000, 70000)},
}

STAGES = {
    "1": {"name": "杂兵关", "type": "normal", "daily_limit": 3, "exp_mult": 80, "first_mult": 3},
    "2": {"name": "连续关", "type": "normal", "daily_limit": 3, "exp_mult": 110, "first_mult": 3},
    "3": {"name": "陷阱关", "type": "normal", "daily_limit": 3, "exp_mult": 130, "first_mult": 3},
    "boss": {"name": "BOSS关", "type": "boss", "daily_limit": 2, "exp_mult": 450, "first_mult": 5},
    "hide": {"name": "隐藏关", "type": "hidden", "daily_limit": 1, "exp_mult": 600, "first_mult": 5},
}

STAGE_MATERIALS = {
    "1": {"stone": (0, 1), "rare": (0, 0), "gold_mult": 50},
    "2": {"stone": (1, 2), "rare": (0, 0), "gold_mult": 80},
    "3": {"stone": (2, 3), "rare": (0, 0), "gold_mult": 120},
    "boss": {"stone": (3, 5), "rare": (0, 1), "gold_mult": 200},
    "hide": {"stone": (5, 8), "rare": (1, 2), "gold_mult": 400},
}

CHAPTER_FIRST_REWARDS = {
    1: {"stone": 10, "rare": 0, "legend": 0, "gold": 5000},
    2: {"stone": 20, "rare": 0, "legend": 0, "gold": 10000},
    3: {"stone": 30, "rare": 2, "legend": 0, "gold": 20000},
    4: {"stone": 40, "rare": 4, "legend": 0, "gold": 40000},
    5: {"stone": 50, "rare": 6, "legend": 0, "gold": 80000},
    6: {"stone": 60, "rare": 8, "legend": 0, "gold": 150000},
    7: {"stone": 80, "rare": 0, "legend": 2, "gold": 300000},
}

ENERGY_COST = 5
RESET_COST = 10

ENEMY_PASSIVES: dict[int, dict[str, dict]] = {
    2: {
        "1":    {"passive_slots": {"1": "PS_D01"},
                 "passive_levels": {"PS_D01": 2}},
        "2":    {"passive_slots": {"1": "PS_D01"},
                 "passive_levels": {"PS_D01": 2}},
        "3":    {"passive_slots": {"1": "PS_D01", "2": "PS_A01"},
                 "passive_levels": {"PS_D01": 3, "PS_A01": 2}},
        "boss": {"passive_slots": {"1": "PS_D01", "2": "PS_A01"},
                 "passive_levels": {"PS_D01": 3, "PS_A01": 3}},
    },
    3: {
        "1":    {"passive_slots": {"1": "PS_A01"},
                 "passive_levels": {"PS_A01": 3}},
        "2":    {"passive_slots": {"1": "PS_A01", "2": "PS_S01"},
                 "passive_levels": {"PS_A01": 3, "PS_S01": 2}},
        "3":    {"passive_slots": {"1": "PS_A01", "2": "PS_D02"},
                 "passive_levels": {"PS_A01": 3, "PS_D02": 3}},
        "boss": {"passive_slots": {"1": "PS_A01", "2": "PS_D02", "3": "PS_S01"},
                 "passive_levels": {"PS_A01": 4, "PS_D02": 3, "PS_S01": 3}},
    },
    4: {
        "1":    {"passive_slots": {"1": "PS_A03", "2": "PS_D04"},
                 "passive_levels": {"PS_A03": 3, "PS_D04": 2}},
        "2":    {"passive_slots": {"1": "PS_A03", "2": "PS_D04"},
                 "passive_levels": {"PS_A03": 3, "PS_D04": 3}},
        "3":    {"passive_slots": {"1": "PS_A03", "2": "PS_D04", "3": "PS_X01"},
                 "passive_levels": {"PS_A03": 4, "PS_D04": 3, "PS_X01": 2}},
        "boss": {"passive_slots": {"1": "PS_A03", "2": "PS_D04", "3": "PS_X01"},
                 "passive_levels": {"PS_A03": 5, "PS_D04": 4, "PS_X01": 3}},
    },
    5: {
        "1":    {"passive_slots": {"1": "PS_A04", "2": "PS_D05"},
                 "passive_levels": {"PS_A04": 3, "PS_D05": 3}},
        "2":    {"passive_slots": {"1": "PS_A04", "2": "PS_D05", "3": "PS_S04"},
                 "passive_levels": {"PS_A04": 4, "PS_D05": 3, "PS_S04": 2}},
        "3":    {"passive_slots": {"1": "PS_A04", "2": "PS_D05", "3": "PS_S04"},
                 "passive_levels": {"PS_A04": 4, "PS_D05": 4, "PS_S04": 3}},
        "boss": {"passive_slots": {"1": "PS_A04", "2": "PS_D05", "3": "PS_S04", "4": "PS_A07"},
                 "passive_levels": {"PS_A04": 5, "PS_D05": 5, "PS_S04": 4, "PS_A07": 3}},
    },
    6: {
        "1":    {"passive_slots": {"1": "PS_A05", "2": "PS_D06", "3": "PS_S05"},
                 "passive_levels": {"PS_A05": 4, "PS_D06": 3, "PS_S05": 3}},
        "2":    {"passive_slots": {"1": "PS_A05", "2": "PS_D06", "3": "PS_S05"},
                 "passive_levels": {"PS_A05": 4, "PS_D06": 4, "PS_S05": 3}},
        "3":    {"passive_slots": {"1": "PS_A05", "2": "PS_D06", "3": "PS_S05", "4": "PS_X04"},
                 "passive_levels": {"PS_A05": 5, "PS_D06": 4, "PS_S05": 4, "PS_X04": 3}},
        "boss": {"passive_slots": {"1": "PS_A05", "2": "PS_D06", "3": "PS_S05", "4": "PS_X04"},
                 "passive_levels": {"PS_A05": 6, "PS_D06": 5, "PS_S05": 5, "PS_X04": 4}},
    },
    7: {
        "1":    {"passive_slots": {"1": "PS_A07", "2": "PS_D07", "3": "PS_S06", "4": "PS_X06"},
                 "passive_levels": {"PS_A07": 5, "PS_D07": 4, "PS_S06": 4, "PS_X06": 3}},
        "2":    {"passive_slots": {"1": "PS_A07", "2": "PS_D07", "3": "PS_S06", "4": "PS_X06"},
                 "passive_levels": {"PS_A07": 5, "PS_D07": 5, "PS_S06": 4, "PS_X06": 3}},
        "3":    {"passive_slots": {"1": "PS_A08", "2": "PS_D08", "3": "PS_S06", "4": "PS_X06"},
                 "passive_levels": {"PS_A08": 5, "PS_D08": 5, "PS_S06": 5, "PS_X06": 4}},
        "boss": {"passive_slots": {"1": "PS_A08", "2": "PS_D08", "3": "PS_S06", "4": "PS_X06"},
                 "passive_levels": {"PS_A08": 7, "PS_D08": 6, "PS_S06": 6, "PS_X06": 5}},
        "hide": {"passive_slots": {"1": "PS_A08", "2": "PS_D08", "3": "PS_S06", "4": "PS_X06"},
                 "passive_levels": {"PS_A08": 8, "PS_D08": 7, "PS_S06": 7, "PS_X06": 6}},
    },
}


def get_enemy_passives(chapter: int, stage_id: str) -> dict:
    ch_passives = ENEMY_PASSIVES.get(chapter)
    if not ch_passives:
        return {}
    stage_passives = ch_passives.get(stage_id)
    if not stage_passives:
        return {}
    return stage_passives


def get_stage_id(stage_str: str) -> str | None:
    if stage_str in STAGES:
        return stage_str
    if stage_str.isdigit() and stage_str in STAGES:
        return stage_str
    return None


def is_chapter_unlocked(first_set: set, chapter: int) -> bool:
    if chapter == 1:
        return True
    prev = chapter - 1
    required = {"1", "2", "3", "boss"}
    if prev == 7:
        required.add("hide")
    for stage in required:
        if f"{prev}-{stage}" not in first_set:
            return False
    return True
