from src.game.commands import command


class LeaderboardMixin:

    @command("排行", "top")
    def top(self, user_id: str = "", user_name: str = "", arg: str = "", group_id: str = "") -> str:
        board = self.dm.get_leaderboard(10)
        if not board:
            return "📊 排行榜还是空的，快来领养宠物吧！"

        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 宠物排行榜 TOP10"]
        lines.append("━━━━━━━━━━━━━━━━━━")
        for i, entry in enumerate(board):
            medal = medals[i] if i < 3 else f"{i+1}."
            stage_names = ["一阶", "二阶", "三阶"]
            stage = stage_names[entry["evolution_stage"]] if entry["evolution_stage"] < 3 else "三阶"
            lines.append(
                f"{medal} {entry['species_name']}「{entry['pet_name']}」"
                f"(Lv.{entry['level']} {stage})"
                f" - {entry['owner_name']}"
            )
        return "\n".join(lines)
