import time

from src.game.commands import command
from src.data.models import _redis_client


class EventMixin:

    @command("活动", "event")
    def event_list(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        events = []
        now = time.time()

        for key in _redis_client.scan_iter(match="qqbot:event:*"):
            data = _redis_client.hgetall(key)
            if not data:
                continue
            if data.get("active", "0") != "1":
                continue
            start = float(data.get("start", 0))
            end = float(data.get("end", 0))
            if start <= now <= end:
                events.append(data)

        if not events:
            return "🎉 当前没有进行中的活动"

        lines = ["🎉 当前活动", ""]
        for ev in events:
            name = ev.get("name", "未知活动")
            ev_type = ev.get("type", "")
            multiplier = ev.get("multiplier", "1")
            end_ts = float(ev.get("end", 0))
            remaining = int((end_ts - now) / 3600)

            type_names = {
                "double_exp": "双倍经验",
                "drop_boost": "掉落加成",
                "temp_boss": "限时 Boss",
                "checkin_boost": "签到加成",
            }
            type_label = type_names.get(ev_type, ev_type)

            lines.append(f"  🎊 {name}")
            lines.append(f"     类型：{type_label}  倍率：×{multiplier}")
            lines.append(f"     剩余：约 {remaining} 小时")
            lines.append("")

        return "\n".join(lines)
