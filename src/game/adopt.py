import asyncio
import random

from src.game.commands import command
from src.pet.config import PET_SPECIES
from src.pet.stats import generate_ivs, generate_quality, QUALITY_INDEX_TO_LABEL, calc_stats, calc_cp, quality_label


class AdoptMixin:

    @command("领养", "adopt")
    async def adopt(self, user_id: str, user_name: str, arg: str = "", group_id: str = "") -> str | dict:
        if self.dm.has_pet(user_id):
            pet = self.dm.get_pet(user_id)
            return (f"❌ 你已经有一只 {pet.species_name}「{pet.name}」了！\n"
                    f"使用「/遗弃」先放生当前宠物才能领养新的哦~")

        game_uid = self.dm.get_user_game_uid(user_id)
        if game_uid == 0:
            game_uid = self.dm.assign_game_uid(user_id)

        species_num = random.randint(1, 25)
        species_id = f"P{species_num:03d}"
        species = PET_SPECIES[species_id]
        pet_name = species["names"][0]

        quality_index = generate_quality()
        ivs = generate_ivs(quality_index)
        q_rating = QUALITY_INDEX_TO_LABEL[quality_index]

        stats = calc_stats(species_id, 0, 1, ivs)
        battle_type = species["battle_type"]

        pet = self.dm.create_pet(user_id, user_name, species_id, pet_name,
                                 battle_type, ivs, stats)
        pet.game_uid = game_uid
        self.dm.update_pet(user_id, game_uid=game_uid)
        self.dm.update_leaderboard(pet)

        type_names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
        btype_cn = type_names.get(battle_type, battle_type)

        title = f"🎉 {pet_name} 成为了你的伙伴！"
        cp = calc_cp(pet)
        tip = (f"品质：{q_rating}({quality_label(q_rating)})  |  类型：{btype_cn}  |  "
               f"游戏ID：{game_uid}  |  战力：{cp}  |  可使用「/改名」给宠物取一个喜欢的名字哦~")
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "⚔️ 战斗", "command": "/战斗"}],
            [{"text": "💪 训练", "command": "/训练"}],
        ]
        msg = await self._build_pet_message(pet, title, tip, rows)
        asyncio.create_task(self._pre_generate_screenshot(pet))
        return msg
