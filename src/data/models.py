import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import redis

from src.config import config

_redis_cfg = config["redis"]
_redis_client = redis.Redis(
    host=_redis_cfg["host"],
    port=_redis_cfg["port"],
    password=_redis_cfg["password"] or None,
    db=_redis_cfg.get("db", 0),
    decode_responses=True,
)

KEY_PET = "qqbot:pet:{user_id}"
KEY_COOLDOWN = "qqbot:cooldown:{user_id}"
KEY_LEADERBOARD = "qqbot:leaderboard"
KEY_SCREENSHOT = "qqbot:screenshot:{user_id}:{scene}"
KEY_GROUP_MEMBERS = "qqbot:group:{group_id}"
KEY_GAME_UID_COUNTER = "qqbot:game_uid_counter"
KEY_GAME_UID_MAP = "qqbot:game_uid:{game_uid}"
KEY_USER_GAME_UID = "qqbot:user_game_uid:{user_id}"

from pathlib import Path
_IMAGE_DIR = Path(__file__).parent.parent.parent / config["image"]["dir"]
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Pet:
    owner_id: str
    owner_name: str
    name: str
    level: int = 1
    exp: int = 0
    create_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    species_id: str = ""
    evolution_stage: int = 0
    battle_type: str = ""
    rename_count: int = 0

    iv_hp: int = 15
    iv_atk: int = 15
    iv_def: int = 15
    iv_spd: int = 15
    iv_crit: int = 15
    iv_eva: int = 15

    hp: float = 0
    atk: float = 0
    def_: float = 0
    spd: float = 0
    crit: float = 0
    crit_dmg: float = 1.5
    eva: float = 0
    lifesteal: float = 0.05

    training: bool = False
    training_start: float = 0.0

    game_uid: int = 0

    @property
    def iv_dict(self) -> dict[str, int]:
        return {
            "iv_hp": self.iv_hp, "iv_atk": self.iv_atk,
            "iv_def": self.iv_def, "iv_spd": self.iv_spd,
            "iv_crit": self.iv_crit, "iv_eva": self.iv_eva,
        }

    @property
    def iv_sum(self) -> int:
        return sum(self.iv_dict.values())

    @property
    def quality(self) -> str:
        s = self.iv_sum
        if s >= 151: return "S"
        if s >= 121: return "A"
        if s >= 91:  return "B"
        if s >= 61:  return "C"
        if s >= 31:  return "D"
        return "E"

    @property
    def max_exp(self) -> int:
        return 100 * self.level * (self.level + 5)

    @property
    def species_name(self) -> str:
        try:
            from src.pet.config import PET_SPECIES
            return PET_SPECIES[self.species_id]["names"][self.evolution_stage]
        except Exception:
            return self.species_id

    def to_dict(self) -> dict:
        return asdict(self)

    def with_passives(self, passive_slots: dict[str, str] | None = None,
                      passive_levels: dict[str, int] | None = None) -> dict:
        d = self.to_dict()
        if passive_slots:
            d["passive_slots"] = passive_slots
            d["passive_levels"] = passive_levels or {}
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
