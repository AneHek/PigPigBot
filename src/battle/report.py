from src.battle.models import BattleResult


def format_battle_report(result: BattleResult) -> str:
    lines = ["⚔️ 战斗结束！"]
    lines.append("━━━━━━━━━━━━━━━━━━")

    if result.winner:
        lines.append(f"🏆 胜利者：{result.winner_name}")
        lines.append(f"💀 战败者：{result.loser_name}")
    else:
        lines.append("🤝 平局！双方势均力敌")

    lines.append(f"⏱ 战斗时长：{result.duration} 秒")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📜 战斗日志：")

    recent = result.events[-10:] if len(result.events) > 10 else result.events
    for ev in recent:
        t = f"[{ev.time:.1f}s]"
        if ev.type in ("attack", "damage"):
            c = "💥" if ev.is_crit else "⚔️"
            lines.append(f"  {t} {c} {ev.source} → {ev.target} {ev.detail} (-{ev.damage:.0f})")
        elif ev.type == "skill":
            lines.append(f"  {t} ✨ {ev.source} {ev.detail}")
        elif ev.type == "dodge":
            lines.append(f"  {t} 👻 {ev.detail}")
        elif ev.type == "heal":
            lines.append(f"  {t} 💚 {ev.source} {ev.detail}")
        elif ev.type == "shield":
            lines.append(f"  {t} 🛡️ {ev.source} {ev.detail}")
        elif ev.type == "buff":
            lines.append(f"  {t} ⬆️ {ev.source} {ev.detail}")
        elif ev.type == "debuff":
            lines.append(f"  {t} ⬇️ {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "control":
            lines.append(f"  {t} 🔒 {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "dot":
            lines.append(f"  {t} 🔥 {ev.detail} → {ev.target}")
        elif ev.type == "reflect":
            lines.append(f"  {t} 🔄 {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "purify":
            lines.append(f"  {t} 💫 {ev.source} {ev.detail}")

    return "\n".join(lines)
