import datetime

BOSSES = {
    "time_demon": {
        "name": "时间魔王猪",
        "hp": 1000000,
        "min_level": 30,
        "schedule": [(12, 0), (20, 0)],
        "duration_minutes": 10,
        "species_id": "P007",
        "stage": 2,
    },
    "abyss_lord": {
        "name": "深渊领主猪",
        "hp": 3000000,
        "min_level": 50,
        "schedule": [(18, 0)],
        "duration_minutes": 10,
        "species_id": "P004",
        "stage": 2,
    },
    "galaxy_emperor": {
        "name": "银河猪皇",
        "hp": 8000000,
        "min_level": 70,
        "schedule": [(21, 0)],
        "duration_minutes": 10,
        "species_id": "P021",
        "stage": 2,
    },
    "cosmic_god": {
        "name": "宇宙猪神",
        "hp": 50000000,
        "min_level": 90,
        "schedule": [],
        "duration_minutes": 20,
        "species_id": "P001",
        "stage": 2,
        "weekly": True,
    },
}

BOSS_ATTACK_CD = 10
BOSS_ENERGY_COST = 20
BOSS_BATTLE_DURATION = 30

EXP_REWARDS = {
    "top1": 5000,
    "top2_3": 3000,
    "top4_10": 1500,
    "top11_30pct": 600,
    "top30_60pct": 300,
    "top60_100pct": 100,
}


def get_active_boss() -> tuple[str, dict] | None:
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()

    if weekday == 6:
        if 21 <= hour < 22:
            return "cosmic_god", BOSSES["cosmic_god"]

    for boss_id, info in BOSSES.items():
        if info.get("weekly"):
            continue
        for sched_hour, sched_minute in info["schedule"]:
            if hour == sched_hour and minute < info["duration_minutes"]:
                return boss_id, info

    return None
