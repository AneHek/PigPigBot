from src.game.commands import command

INTERACT_CONFIG = {
    "喂食": {"self_cd": 7200, "target_cd": 3600, "exp_mult": 30, "intimacy": 1, "contribution": 2},
    "抚摸": {"self_cd": 3600, "target_cd": 1800, "exp_mult": 15, "intimacy": 1, "contribution": 1},
    "玩耍": {"self_cd": 10800, "target_cd": 7200, "exp_mult": 50, "intimacy": 2, "contribution": 3},
    "鼓励": {"self_cd": 1800, "target_cd": 900, "exp_mult": 10, "intimacy": 0, "contribution": 1},
}

INTIMACY_LEVELS = [
    (0, "陌生"),
    (1, "点头"),
    (6, "熟识"),
    (21, "信赖"),
    (51, "挚友"),
]


def _intimacy_label(value: int) -> str:
    label = "陌生"
    for threshold, name in INTIMACY_LEVELS:
        if value >= threshold:
            label = name
    return label


class InteractMixin:

    def _resolve_target(self, arg: str) -> str | None:
        if not arg or not arg.isdigit():
            return None
        target_game_uid = int(arg)
        return self.dm.get_user_by_game_uid(target_game_uid)

    def _do_interact(self, user_id: str, action: str, arg: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        target_id = self._resolve_target(arg)
        if not target_id:
            return "❌ 请输入正确的游戏用户 ID（/排行 可查）"

        if target_id == user_id:
            return "❌ 不能对自己使用互动哦！"

        target_pet = self.dm.get_pet(target_id)
        if target_pet is None:
            return "❌ 对方还没有宠物！"

        cfg = INTERACT_CONFIG[action]

        cd_key = f"interact_{action}"
        cd_remaining = self.dm.get_cooldown(user_id, cd_key)
        if cd_remaining > 0:
            minutes = int(cd_remaining / 60)
            return f"⏳ {action}冷却中，剩 {minutes} 分钟"

        target_cd_key = f"interacted_{action}_{user_id}"
        target_cd_remaining = self.dm.get_cooldown(target_id, target_cd_key)
        if target_cd_remaining > 0:
            minutes = int(target_cd_remaining / 60)
            return f"⏳ 对方{action}冷却中，剩 {minutes} 分钟"

        self.dm.set_cooldown(user_id, cd_key, cfg["self_cd"])
        self.dm.set_cooldown(target_id, target_cd_key, cfg["target_cd"])

        exp = pet.level * cfg["exp_mult"]
        self.dm.add_exp(user_id, exp)

        if cfg["intimacy"] > 0:
            new_intimacy = self.dm.add_intimacy(user_id, target_id, cfg["intimacy"])
        else:
            new_intimacy = self.dm.get_intimacy(user_id, target_id)

        self.dm.add_contribution(user_id, cfg["contribution"])
        self.dm.add_contribution(target_id, cfg["contribution"])

        old_label = _intimacy_label(new_intimacy - cfg["intimacy"])
        new_label = _intimacy_label(new_intimacy)
        intimacy_info = f"💕 亲密度 {new_intimacy}（{new_label}）"
        if old_label != new_label:
            intimacy_info += f"  {old_label} → {new_label}"

        lines = [
            f"🎉 {action}成功！",
            f"   🎯 经验 +{exp}（{action}奖励）",
            f"   {intimacy_info}",
            f"   🏅 群贡献点 +{cfg['contribution']}（双方各得）",
        ]

        return "\n".join(lines)

    @command("喂食", "feed")
    def feed(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        return self._do_interact(user_id, "喂食", arg)

    @command("抚摸", "pet")
    def pet_interact(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        return self._do_interact(user_id, "抚摸", arg)

    @command("玩耍", "play")
    def play(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        return self._do_interact(user_id, "玩耍", arg)

    @command("鼓励", "encourage")
    def encourage(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        return self._do_interact(user_id, "鼓励", arg)

    @command("群训练", "grouptrain")
    def group_train(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not group_id:
            return "❌ 群训练只能在群聊中使用！"

        cd_key = "group_train"
        cd_remaining = self.dm.get_cooldown(user_id, cd_key)
        if cd_remaining > 0:
            minutes = int(cd_remaining / 60)
            return f"⏳ 群训练冷却中，剩 {minutes} 分钟"

        if not self.dm.use_energy(user_id, 20):
            energy = self.dm.get_energy(user_id)
            return f"❌ 行动力不足（当前 {energy['value']}/20），回复时间约 60 分钟"

        self.dm.set_cooldown(user_id, cd_key, 21600)

        exp = pet.level * 80
        self.dm.add_exp(user_id, exp)
        self.dm.add_contribution(user_id, 3)

        lines = [
            f"🏋️ 群训练完成！",
            f"   🎯 经验 +{exp}",
            f"   🏅 群贡献点 +3",
            f"   🔋 行动力 -20",
        ]

        return "\n".join(lines)

    @command("亲密", "intimacy")
    def intimacy_list(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        all_intimacy = self.dm.get_all_intimacy(user_id)
        if not all_intimacy:
            return "💕 还没有亲密度记录~\n📌 使用 /喂食、/抚摸 等互动命令与其他玩家建立亲密度"

        sorted_intimacy = sorted(all_intimacy.items(), key=lambda x: x[1], reverse=True)

        lines = ["💕 亲密度列表", ""]
        for target_id, value in sorted_intimacy[:10]:
            label = _intimacy_label(value)
            target_pet = self.dm.get_pet(target_id)
            name = target_pet.owner_name if target_pet else target_id
            lines.append(f"  {name} — {value} ({label})")

        lines.append("")
        lines.append("亲密度等级：陌生(0) → 点头(1) → 熟识(6) → 信赖(21) → 挚友(51)")

        return "\n".join(lines)
