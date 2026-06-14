import asyncio
import copy

from src.game.commands import command
from src.pet.stats import calc_cp


class EvolveMixin:

    @command("进化", "evolve")
    async def evolve(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | dict:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.evolution_stage >= 2:
            return "❌ 已经是三阶形态，无法再进化了！"

        gate = 29 if pet.evolution_stage == 0 else 59
        if pet.level < gate:
            return f"❌ 需要达到 Lv.{gate} 才能进化！（当前 Lv.{pet.level}）"

        old_name = pet.species_name
        old_pet = copy.deepcopy(pet)
        result = self.dm.evolve_pet(user_id)
        if result is None:
            return "❌ 进化失败，请稍后再试。"

        new_name = result.species_name
        self.dm.update_leaderboard(result)

        stage_names = ["一阶", "二阶", "三阶"]
        title = f"🎊 {old_name} → {new_name}"
        tip = f"新形态：{stage_names[result.evolution_stage]}进化 | Lv.{result.level}"
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "💪 训练", "command": "/训练"}],
        ]
        msg = await self._build_pet_message(result, title, tip, rows,
                                            old_pet=old_pet)
        asyncio.create_task(self._pre_generate_screenshot(result))
        return msg
