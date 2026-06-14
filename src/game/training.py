import asyncio
import time

from src.game.commands import command
from src.pet.stats import calc_training_exp, calc_cp


class TrainingMixin:

    @command("训练", "train")
    async def start_training(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | dict:
        from datetime import datetime, timedelta
        from src.msg_templates import build_button_list_msg

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.training:
            elapsed = int((time.time() - pet.training_start) / 60)
            return (f"⏳ 宠物正在训练中！（已训练 {elapsed} 分钟）\n"
                    f"需要至少训练 10 分钟后使用「/休息」结束训练。")

        result = self.dm.start_training(user_id)
        if result is None:
            return "❌ 开始训练失败。"

        exp_10min = calc_training_exp(pet.level, 10)
        rest_time = datetime.now() + timedelta(minutes=10)
        time_str = rest_time.strftime("%H:%M")
        content = f"💪 开始训练！\n🕓  预计获得{exp_10min}经验(10分钟)。\n⚠  训练时间越长经验越多\n🗨  休息指令可用时间：{time_str}"
        rows = [
            [{"text": "🛌 结束训练", "command": "/休息"}],
            [{"text": "🧬 属性详情", "command": "/属性"}],
        ]
        return build_button_list_msg(content, rows)

    @command("休息", "rest")
    async def end_training(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | dict:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not pet.training:
            return "❌ 宠物不在训练中！使用「/训练」开始训练。"

        result, exp_gained = self.dm.end_training(user_id)
        if exp_gained == -1:
            elapsed = int((time.time() - pet.training_start) / 60)
            remaining = 10 - elapsed
            return f"⏳ 还需要训练 {remaining} 分钟才能休息！\n已训练 {elapsed} 分钟，至少需要 10 分钟。"

        if result is None:
            return "❌ 结束训练失败。"

        minutes = int((time.time() - pet.training_start) / 60)
        self.dm.update_leaderboard(result)

        level_info = ""
        if result.level > pet.level:
            level_info = f" | 🎉 Lv.{pet.level}→Lv.{result.level}"

        gate_info = ""
        if result.evolution_stage == 0 and result.level >= 29:
            gate_info = " ⚠️ 可进化"
        elif result.evolution_stage == 1 and result.level >= 59:
            gate_info = " ⚠️ 可进化"

        title = f"🛌 {result.species_name}({result.game_uid}) 训练结束"
        old_level = pet.level
        new_level = result.level
        cp = calc_cp(result)
        tip = f"训练{minutes}分钟 | Lv.{old_level}->Lv.{new_level}  |  战力：{cp}"
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "💪 再训练", "command": "/训练"}],
        ]
        msg = await self._build_pet_message(result, title, tip, rows)
        asyncio.create_task(self._pre_generate_screenshot(result))
        return msg
