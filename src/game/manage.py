from src.game.commands import command


class ManageMixin:

    @command("遗弃", "abandon")
    def abandon(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        name = pet.name
        self.dm.delete_pet(user_id)
        return (f"😢 你含泪放生了 {pet.species_name}「{name}」...\n"
                f"使用「/领养」可以重新领养一只新的伙伴。")

    @command("注册", "register")
    def register(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        existing_uid = self.dm.get_user_game_uid(user_id)
        if existing_uid > 0:
            return f"✅ 你已经注册过了！你的游戏用户ID是：{existing_uid}"

        game_uid = self.dm.assign_game_uid(user_id)
        self.dm.update_pet(user_id, game_uid=game_uid)
        return f"✅ 注册成功！你的游戏用户ID是：{game_uid}\n其他人可以通过「/战斗 {game_uid}」来挑战你！"

    @command("改名", "rename")
    def rename(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        new_name = arg
        if not new_name or len(new_name) > 8:
            return "❌ 名字长度需在 1-8 个字符之间！"
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        old = pet.name
        self.dm.rename_pet(user_id, new_name)
        return f"✅ 改名成功！「{old}」→「{new_name}」"
