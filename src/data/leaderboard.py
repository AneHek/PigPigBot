import json

from src.data.models import Pet, _redis_client, KEY_LEADERBOARD


class LeaderboardMixin:

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
