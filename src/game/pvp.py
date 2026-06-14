from src.game.commands import command
from src.battle import battle_engine, format_battle_report


class PvPMixin:

    @command("战斗", "battle")
    async def battle_pvp(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | list[str]:
        if not arg or not arg.isdigit():
            return "❌ 请提供对方的游戏用户ID！\n例如：/战斗 123"

        target_game_uid = int(arg)
        target_id = self.dm.get_user_by_game_uid(target_game_uid)
        if not target_id:
            return "❌ 请提供对方的游戏用户ID！\n例如：/战斗 123"

        challenger_id = user_id

        if challenger_id == target_id:
            return "❌ 不能挑战自己哦！"

        pet_a = self.dm.get_pet(challenger_id)
        if pet_a is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet_a.training:
            return "❌ 你的宠物正在训练中，无法战斗！使用「/休息」结束训练。"

        pet_b = self.dm.get_pet(target_id)
        if pet_b is None:
            return "❌ 对方还没有宠物！"

        if pet_b.training:
            return "❌ 对方的宠物正在训练中，暂时无法挑战！"

        start_msg = f"⚔️ {pet_a.species_name}「{pet_a.name}」 VS {pet_b.species_name}「{pet_b.name}」\n战斗开始，结果生成中..."

        result = battle_engine.run(pet_a.to_dict(), pet_b.to_dict())

        exp_winner = 50 * pet_a.level if result.winner else 0
        exp_loser = 20 * pet_a.level

        if result.winner == challenger_id:
            self.dm.add_exp(challenger_id, exp_winner)
            self.dm.add_exp(target_id, exp_loser)
            self.dm.update_leaderboard(self.dm.get_pet(challenger_id))
            self.dm.update_leaderboard(self.dm.get_pet(target_id))
        elif result.winner == target_id:
            self.dm.add_exp(target_id, exp_winner)
            self.dm.add_exp(challenger_id, exp_loser)
            self.dm.update_leaderboard(self.dm.get_pet(target_id))
            self.dm.update_leaderboard(self.dm.get_pet(challenger_id))

        result_msg = format_battle_report(result)

        return [start_msg, result_msg]
