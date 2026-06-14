from src.game.commands import command
from src.pet.stats import calc_cp


class StatsMixin:

    @command("属性", "stats")
    async def stats_detail(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | dict:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        self.dm.update_leaderboard(pet)

        gate_info = ""
        if pet.evolution_stage == 0 and pet.level >= 29:
            gate_info = " | ⚠️ 已达29级上限，需要进化"
        elif pet.evolution_stage == 1 and pet.level >= 59:
            gate_info = " | ⚠️ 已达59级上限，需要进化"

        title = f"{pet.species_name}({pet.game_uid}) 属性详情"
        cp = calc_cp(pet)
        tip = f"品质：{pet.quality}  |  战力：{cp}  |  IV总和:{pet.iv_sum}/186"
        rows = [
            [{"text": "🔮 进化", "command": "/进化"},
             {"text": "💪 训练", "command": "/训练"}],
            [{"text": "⚔️ 战斗", "command": "/战斗"}],
        ]
        return await self._build_pet_message(pet, title, tip, rows)
