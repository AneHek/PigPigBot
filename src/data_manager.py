"""
data_manager.py - Data persistence using Redis.

Pet dataclass models battle pets with IV, evolution, and training state.
"""
import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import redis

from src.config import config

# Redis connection
_redis_cfg = config["redis"]
_redis_client = redis.Redis(
    host=_redis_cfg["host"],
    port=_redis_cfg["port"],
    password=_redis_cfg["password"] or None,
    db=_redis_cfg.get("db", 0),
    decode_responses=True,
)

# Redis key prefixes
KEY_PET = "qqbot:pet:{user_id}"
KEY_COOLDOWN = "qqbot:cooldown:{user_id}"
KEY_LEADERBOARD = "qqbot:leaderboard"
KEY_SCREENSHOT = "qqbot:screenshot:{user_id}"
KEY_GROUP_MEMBERS = "qqbot:group:{group_id}"
KEY_GAME_UID_COUNTER = "qqbot:game_uid_counter"
KEY_GAME_UID_MAP = "qqbot:game_uid:{game_uid}"
KEY_USER_GAME_UID = "qqbot:user_game_uid:{user_id}"

# Ensure image directory exists
_IMAGE_DIR = Path(__file__).parent.parent / config["image"]["dir"]
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Pet:
    """Battle pet data model."""
    owner_id: str                  # owner QQ ID
    owner_name: str                # owner nickname
    name: str                      # pet name
    level: int = 1                 # level 1-100
    exp: int = 0                   # current experience
    create_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    # ── Species & Evolution ──
    species_id: str = ""           # P001-P025
    evolution_stage: int = 0       # 0=一阶, 1=二阶, 2=三阶
    battle_type: str = ""          # attack / defense / speed
    rename_count: int = 0

    # ── IV (Individual Values) ──
    iv_hp: int = 15
    iv_atk: int = 15
    iv_def: int = 15
    iv_spd: int = 15
    iv_crit: int = 15
    iv_eva: int = 15

    # ── Computed battle stats ──
    hp: float = 0
    atk: float = 0
    def_: float = 0
    spd: float = 0
    crit: float = 0
    crit_dmg: float = 1.5
    eva: float = 0
    lifesteal: float = 0.05

    # ── Training state ──
    training: bool = False
    training_start: float = 0.0

    # ── Game user ID ──
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
            from src.pet_config import PET_SPECIES
            return PET_SPECIES[self.species_id]["names"][self.evolution_stage]
        except Exception:
            return self.species_id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class DataManager:
    """Data manager: Redis read/write for battle pets."""

    def __init__(self):
        self._connected = False
        try:
            _redis_client.ping()
            self._connected = True
        except Exception:
            pass

    # ── Key helpers ──

    def _pet_key(self, user_id: str) -> str:
        return KEY_PET.format(user_id=user_id)

    def _cooldown_key(self, user_id: str) -> str:
        return KEY_COOLDOWN.format(user_id=user_id)

    def _screenshot_key(self, user_id: str) -> str:
        return KEY_SCREENSHOT.format(user_id=user_id)

    # ── Pet CRUD ──

    def has_pet(self, user_id: str) -> bool:
        return _redis_client.exists(self._pet_key(user_id)) > 0

    def get_pet(self, user_id: str) -> Optional[Pet]:
        data = _redis_client.get(self._pet_key(user_id))
        if data is None:
            return None
        return Pet.from_dict(json.loads(data))

    def create_pet(self, user_id: str, user_name: str,
                   species_id: str, pet_name: str,
                   battle_type: str, ivs: dict[str, int],
                   stats: dict[str, float]) -> Pet:
        pet = Pet(
            owner_id=user_id,
            owner_name=user_name,
            name=pet_name,
            species_id=species_id,
            battle_type=battle_type,
            evolution_stage=0,
            **ivs,
            **stats,
        )
        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def delete_pet(self, user_id: str) -> bool:
        key = self._pet_key(user_id)
        if _redis_client.exists(key):
            _redis_client.delete(key)
            _redis_client.delete(self._cooldown_key(user_id))
            _redis_client.zrem(KEY_LEADERBOARD, user_id)
            return True
        return False

    def rename_pet(self, user_id: str, new_name: str) -> Optional[Pet]:
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        pet.name = new_name
        pet.rename_count += 1
        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def update_pet(self, user_id: str, **kwargs) -> Optional[Pet]:
        """Update pet fields, auto-save, handle level-up with evolution gates."""
        pet = self.get_pet(user_id)
        if pet is None:
            return None

        for k, v in kwargs.items():
            if hasattr(pet, k):
                setattr(pet, k, v)

        pet.last_update = time.time()

        # Level-up loop with evolution gate check
        level_up_occurred = False
        while True:
            # Evolution gate: stop at 29 (stage 0) or 59 (stage 1)
            if pet.evolution_stage == 0 and pet.level >= 29:
                pet.level = 29
                pet.exp = min(pet.exp, pet.max_exp - 1)
                break
            if pet.evolution_stage == 1 and pet.level >= 59:
                pet.level = 59
                pet.exp = min(pet.exp, pet.max_exp - 1)
                break

            if pet.exp < pet.max_exp:
                break

            pet.exp -= pet.max_exp
            pet.level += 1
            level_up_occurred = True

        # Recalculate stats on level-up or when explicitly requested
        if level_up_occurred or kwargs.pop("_recalc_stats", False):
            from src.pet_stats import calc_stats
            stats = calc_stats(pet.species_id, pet.evolution_stage,
                             pet.level, pet.iv_dict)
            pet.hp = stats["hp"]
            pet.atk = stats["atk"]
            pet.def_ = stats["def_"]
            pet.spd = stats["spd"]
            pet.crit = stats["crit"]
            pet.crit_dmg = stats["crit_dmg"]
            pet.eva = stats["eva"]
            pet.lifesteal = stats["lifesteal"]

        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def add_exp(self, user_id: str, amount: int) -> Optional[Pet]:
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        return self.update_pet(user_id, exp=pet.exp + amount)

    # ── Evolution ──

    def evolve_pet(self, user_id: str) -> Optional[Pet]:
        """Evolve pet if at gate level. Returns updated pet or None.

        进化后保留多余经验并继续升级，若宠物名等于旧种族名则同步更新为新种族名。
        """
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        if pet.evolution_stage >= 2:
            return None
        gate_level = 29 if pet.evolution_stage == 0 else 59
        if pet.level < gate_level:
            return None

        old_species_name = pet.species_name

        pet.evolution_stage += 1
        pet.level += 1
        pet.last_update = time.time()

        if pet.name == old_species_name:
            pet.name = pet.species_name

        level_up_occurred = False
        while True:
            if pet.evolution_stage == 0 and pet.level >= 29:
                pet.level = 29
                pet.exp = min(pet.exp, pet.max_exp - 1)
                break
            if pet.evolution_stage == 1 and pet.level >= 59:
                pet.level = 59
                pet.exp = min(pet.exp, pet.max_exp - 1)
                break

            if pet.exp < pet.max_exp:
                break

            pet.exp -= pet.max_exp
            pet.level += 1
            level_up_occurred = True

        from src.pet_stats import calc_stats
        stats = calc_stats(pet.species_id, pet.evolution_stage,
                          pet.level, pet.iv_dict)
        pet.hp = stats["hp"]
        pet.atk = stats["atk"]
        pet.def_ = stats["def_"]
        pet.spd = stats["spd"]
        pet.crit = stats["crit"]
        pet.crit_dmg = stats["crit_dmg"]
        pet.eva = stats["eva"]
        pet.lifesteal = stats["lifesteal"]

        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    # ── Training ──

    def start_training(self, user_id: str) -> Optional[Pet]:
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        if pet.training:
            return None
        pet.training = True
        pet.training_start = time.time()
        pet.last_update = time.time()
        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def end_training(self, user_id: str) -> tuple[Optional[Pet], int]:
        """End training, grant exp. Returns (pet, exp_gained).
        exp_gained = -1 means too early (< 10 min).
        """
        pet = self.get_pet(user_id)
        if pet is None:
            return None, 0
        if not pet.training:
            return None, 0

        elapsed = time.time() - pet.training_start
        minutes = int(elapsed / 60)
        if minutes < 10:
            return None, -1

        exp_gained = 50 * pet.level * minutes
        pet.training = False
        pet.training_start = 0.0
        pet.last_update = time.time()

        _redis_client.set(self._pet_key(user_id),
                          json.dumps(pet.to_dict(), ensure_ascii=False))

        self.add_exp(user_id, exp_gained)
        return self.get_pet(user_id), exp_gained

    # ── Cooldown ──

    def get_cooldown(self, user_id: str, action: str) -> float:
        raw = _redis_client.hget(self._cooldown_key(user_id), action)
        if raw is None:
            return 0.0
        cd = float(raw)
        return max(0.0, cd - time.time())

    def set_cooldown(self, user_id: str, action: str, seconds: int):
        _redis_client.hset(self._cooldown_key(user_id), action,
                          time.time() + seconds)

    # ── Screenshot UUID ──

    def get_screenshot_uuid(self, user_id: str) -> str | None:
        """获取用户当前截图 UUID 记录"""
        return _redis_client.get(self._screenshot_key(user_id))

    def set_screenshot_uuid(self, user_id: str, uuid_str: str) -> None:
        """保存用户截图 UUID 记录"""
        _redis_client.set(self._screenshot_key(user_id), uuid_str)

    # ── Leaderboard ──

    def update_leaderboard(self, pet: Pet):
        score = pet.level + pet.exp / 1000.0
        _redis_client.zadd(KEY_LEADERBOARD, {pet.owner_id: score})
        detail = {
            "owner_id": pet.owner_id,
            "owner_name": pet.owner_name,
            "pet_name": pet.name,
            "species_name": pet.species_name,
            "level": str(pet.level),
            "exp": str(pet.exp),
            "evolution_stage": str(pet.evolution_stage),
            "quality": pet.quality,
        }
        _redis_client.hset(f"{KEY_LEADERBOARD}:detail", pet.owner_id,
                          json.dumps(detail, ensure_ascii=False))

    def get_leaderboard(self, top_n: int = 10) -> list[dict]:
        top_users = _redis_client.zrevrange(KEY_LEADERBOARD, 0, top_n - 1)
        results = []
        for uid in top_users:
            raw = _redis_client.hget(f"{KEY_LEADERBOARD}:detail", uid)
            if raw:
                entry = json.loads(raw)
                entry["level"] = int(entry["level"])
                entry["exp"] = int(entry["exp"])
                entry["evolution_stage"] = int(entry["evolution_stage"])
                results.append(entry)
        return results

    # ── Group members ──

    def add_group_member(self, group_id: str, user_id: str) -> None:
        """记录群组ID和用户ID关系（SET表）"""
        _redis_client.sadd(KEY_GROUP_MEMBERS.format(group_id=group_id), user_id)

    # ── Game UID ──

    def get_user_game_uid(self, user_id: str) -> int:
        """获取用户的游戏用户ID，不存在返回0"""
        val = _redis_client.get(KEY_USER_GAME_UID.format(user_id=user_id))
        return int(val) if val else 0

    def assign_game_uid(self, user_id: str) -> int:
        """为用户分配游戏用户ID（原子递增），已存在则返回现有"""
        existing = self.get_user_game_uid(user_id)
        if existing > 0:
            return existing
        game_uid = _redis_client.incr(KEY_GAME_UID_COUNTER)
        _redis_client.set(KEY_USER_GAME_UID.format(user_id=user_id), game_uid)
        _redis_client.set(KEY_GAME_UID_MAP.format(game_uid=game_uid), user_id)
        return game_uid

    def get_user_by_game_uid(self, game_uid: int) -> str | None:
        """通过游戏用户ID反查QQ用户ID"""
        return _redis_client.get(KEY_GAME_UID_MAP.format(game_uid=game_uid))

    # ── All pets ──

    def get_all_pets(self) -> list[Pet]:
        pets = []
        for key in _redis_client.scan_iter(match="qqbot:pet:*"):
            data = _redis_client.get(key)
            if data:
                pets.append(Pet.from_dict(json.loads(data)))
        return pets


# Global singleton
data_manager = DataManager()
