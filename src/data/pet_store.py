import json
import time
from typing import Optional

from src.data.models import Pet, _redis_client, KEY_PET, KEY_COOLDOWN, KEY_SCREENSHOT, KEY_LEADERBOARD


class PetStoreMixin:

    def _pet_key(self, user_id: str) -> str:
        return KEY_PET.format(user_id=user_id)

    def _cooldown_key(self, user_id: str) -> str:
        return KEY_COOLDOWN.format(user_id=user_id)

    def _screenshot_key(self, user_id: str, scene: str = "") -> str:
        return KEY_SCREENSHOT.format(user_id=user_id, scene=scene)

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
        pet = self.get_pet(user_id)
        if pet is None:
            return None

        for k, v in kwargs.items():
            if hasattr(pet, k):
                setattr(pet, k, v)

        pet.last_update = time.time()

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

        if level_up_occurred or kwargs.pop("_recalc_stats", False):
            from src.pet.stats import calc_stats
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

    def evolve_pet(self, user_id: str) -> Optional[Pet]:
        import logging
        logger = logging.getLogger("DataManager")

        pet = self.get_pet(user_id)
        if pet is None:
            return None
        if pet.evolution_stage >= 2:
            return None
        gate_level = 29 if pet.evolution_stage == 0 else 59
        if pet.level < gate_level:
            return None

        old_stage = pet.evolution_stage
        old_species_name = pet.species_name
        old_pet_name = pet.name

        logger.info(f"[进化] user={user_id}, 进化前: stage={old_stage}, "
                   f"pet.name='{old_pet_name}', species_name='{old_species_name}'")

        pet.evolution_stage += 1
        pet.level += 1
        pet.last_update = time.time()

        new_species_name = pet.species_name
        logger.info(f"[进化] 进化后: stage={pet.evolution_stage}, "
                   f"new_species_name='{new_species_name}'")

        from src.pet.config import PET_SPECIES
        all_species_names = PET_SPECIES.get(pet.species_id, {}).get("names", [])
        if pet.name in all_species_names:
            logger.info(f"[进化] 自动改名: '{pet.name}' → '{new_species_name}'")
            pet.name = new_species_name
        else:
            logger.info(f"[进化] 不改名: pet.name='{pet.name}' 不是默认种族名")

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

        from src.pet.stats import calc_stats
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

    def get_cooldown(self, user_id: str, action: str) -> float:
        raw = _redis_client.hget(self._cooldown_key(user_id), action)
        if raw is None:
            return 0.0
        cd = float(raw)
        return max(0.0, cd - time.time())

    def set_cooldown(self, user_id: str, action: str, seconds: int):
        _redis_client.hset(self._cooldown_key(user_id), action,
                          time.time() + seconds)

    def get_screenshot_uuid(self, user_id: str, scene: str = "") -> str | None:
        return _redis_client.get(self._screenshot_key(user_id, scene))

    def set_screenshot_uuid(self, user_id: str, uuid_str: str, scene: str = "") -> None:
        _redis_client.set(self._screenshot_key(user_id, scene), uuid_str)

    def get_all_pets(self) -> list[Pet]:
        pets = []
        for key in _redis_client.scan_iter(match="qqbot:pet:*"):
            data = _redis_client.get(key)
            if data:
                pets.append(Pet.from_dict(json.loads(data)))
        return pets
