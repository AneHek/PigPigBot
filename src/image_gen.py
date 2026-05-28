"""
image_gen.py — 宠物信息HTML渲染和Playwright截图。

为5种场景(adopt/status/stats/evolve/training)渲染带宠物形象图的HTML，
再通过Playwright headless chromium截图保存。
"""
from __future__ import annotations

import logging
from pathlib import Path
from copy import deepcopy

from src.data_manager import Pet

logger = logging.getLogger("QQBot")

# ── 通用 CSS（亮色主题、网格底纹、IV条渐变） ──
_BASE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    width: 380px; font-family: "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f0 100%);
    color: #333; padding: 12px 0 0 0;
    display: flex; justify-content: center; align-items: flex-start;
}
.card {
    background-color: #ffffff;
    background-image:
        radial-gradient(circle, #f1f5f9 1px, transparent 1px);
    background-size: 18px 18px;
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); overflow: hidden;
    width: 360px;
}
/* ── 头部：左图-中名-右品质 ── */
.header {
    display: flex; align-items: center; padding: 18px 20px 18px 24px;
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    position: relative; gap: 0;
}
.pet-img {
    width: 90px; height: 90px; border-radius: 12px;
    object-fit: cover; border: 2px solid #d1d5db;
    flex-shrink: 0;
}
.pet-info { margin-left: 14px; flex: 1; min-width: 0; }
.pet-name {
    font-size: 22px; font-weight: bold; color: #1e293b;
    line-height: 1.3;
}
.pet-subtitle {
    font-size: 12px; color: #94a3b8; font-weight: 400;
    margin-top: 2px; line-height: 1.4;
}
/* ── 品质菱形色块（斜向高亮渐变） ── */
.quality-wrap {
    flex-shrink: 0; margin-left: 8px;
    display: flex; align-items: center; justify-content: center;
}
.quality-diamond {
    width: 56px; height: 56px;
    display: flex; align-items: center; justify-content: center;
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
    position: relative;
}
.quality-diamond .q-text {
    font-size: 26px; font-weight: 900; color: #fff;
    line-height: 1; z-index: 1;
}
.quality-diamond.q-s { background: linear-gradient(135deg, #fff7cc 0%, #ffd700 30%, #f59e0b 70%, #e67e00 100%); }
.quality-diamond.q-a { background: linear-gradient(135deg, #fee2e2 0%, #ef4444 30%, #dc2626 70%, #991b1b 100%); }
.quality-diamond.q-b { background: linear-gradient(135deg, #ede9fe 0%, #8b5cf6 30%, #7c3aed 70%, #5b21b6 100%); }
.quality-diamond.q-c { background: linear-gradient(135deg, #dbeafe 0%, #3b82f6 30%, #2563eb 70%, #1e40af 100%); }
.quality-diamond.q-d { background: linear-gradient(135deg, #d1fae5 0%, #22c55e 30%, #16a34a 70%, #14532d 100%); }
.quality-diamond.q-e { background: linear-gradient(135deg, #f1f5f9 0%, #94a3b8 30%, #64748b 70%, #334155 100%); }
/* ── Section ── */
.section {
    padding: 14px 24px;
    border-top: 1px solid #eef1f5;
    position: relative; z-index: 1;
    background: rgba(255,255,255,0.85);
}
.section-title {
    font-size: 14px; font-weight: bolder;
    margin-bottom: 10px; letter-spacing: 0.5px;
}
/* ── 三列属性行：图标 | 名称 | 数值+进度条(右) ── */
.stat-table { width: 100%; border-collapse: collapse; }
.stat-table td { padding: 6px 0; vertical-align: middle; }
.stat-table tr { border-bottom: 1px solid #f8fafc; }
.stat-table tr:last-child { border-bottom: none; }
.stat-icon { width: 28px; text-align: center; font-size: 15px; }
.stat-name { width: 56px; font-size: 13px; color: #64748b; padding-left: 6px !important; }
.stat-right { text-align: right; padding-right: 4px; }
.stat-val { font-size: 14px; font-weight: 600; color: #1e293b; margin-right: 8px; }
/* IV进度条 — 斜向高亮渐变 */
.iv-track {
    display: inline-block; width: 100px; height: 10px;
    background: #eef1f5; border-radius: 5px;
    vertical-align: middle; overflow: hidden;
}
.iv-fill {
    display: inline-block; height: 100%; border-radius: 5px;
    vertical-align: top; position: relative;
}
.iv-fill::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 100%);
    border-radius: 5px 5px 0 0;
}
.iv-fill.iv-s { background: linear-gradient(135deg, #ffe87c 0%, #ffd700 40%, #f59e0b 100%); }
.iv-fill.iv-a { background: linear-gradient(135deg, #fca5a5 0%, #ef4444 40%, #dc2626 100%); }
.iv-fill.iv-b { background: linear-gradient(135deg, #c4b5fd 0%, #8b5cf6 40%, #7c3aed 100%); }
.iv-fill.iv-c { background: linear-gradient(135deg, #93c5fd 0%, #3b82f6 40%, #2563eb 100%); }
.iv-fill.iv-d { background: linear-gradient(135deg, #86efac 0%, #22c55e 40%, #16a34a 100%); }
.iv-fill.iv-e { background: linear-gradient(135deg, #e2e8f0 0%, #94a3b8 40%, #64748b 100%); }
/* ── EXP 行 ── */
.exp-title-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
.exp-title { font-size: 14px; font-weight: bolder; }
.exp-val { font-size: 12px; color: #64748b; }
.exp-bar-bg { background: #f1f5f9; border-radius: 7px; height: 14px; overflow: hidden; }
.exp-bar-fill { height: 100%; border-radius: 7px; background: linear-gradient(90deg, #34d399, #10b981); }
/* ── 技能信息区域（左右布局） ── */
.skill-section {
    padding: 14px 20px; border-top: 1px solid #eef1f5;
    background: rgba(255,255,255,0.85); display: flex; gap: 14px;
}
.skill-left { flex: 0 0 100px; display: flex; flex-direction: column; justify-content: center; }
.skill-left-name { font-size: 14px; font-weight: bold; color: #1e293b; margin-bottom: 6px; }
.skill-left-tip { font-size: 11px; color: #94a3b8; line-height: 1.5; }
.skill-right { flex: 1; display: flex; flex-direction: column; gap: 0; }
.skill-item {
    background: #f8fafc; border-radius: 8px; padding: 8px 10px;
    border-left: 3px solid #3b82f6;
}
.skill-item-header { font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 3px; }
.skill-item-desc { font-size: 11px; color: #64748b; line-height: 1.4; }
.skill-arrow {
    text-align: center; font-size: 14px; color: #94a3b8;
    padding: 2px 0; line-height: 1;
}
/* ── Footer ── */
.footer {
    padding: 12px 24px; font-size: 11px; color: #cbd5e1;
    text-align: center; border-top: 1px solid #eef1f5;
    background: rgba(255,255,255,0.85);
}
.type-attack { color: #e74c3c; }
.type-defense { color: #3498db; }
.type-speed { color: #22c55e; }
"""

# ── 常量：属性图标和名称映射 ──
_STAT_DEFS = [
    ("❤️", "生命",   "hp"),
    ("⚔️", "攻击",   "atk"),
    ("🛡️", "防御",   "def_"),
    ("⚡", "速度",   "spd"),
    ("💥", "暴击率", "crit"),
    ("👻", "闪避",   "eva"),
]

_IV_DEFS = [
    ("iv_hp",   "iv_hp"),
    ("iv_atk",  "iv_atk"),
    ("iv_def",  "iv_def"),
    ("iv_spd",  "iv_spd"),
    ("iv_crit", "iv_crit"),
    ("iv_eva",  "iv_eva"),
]


def _iv_class(value: int) -> str:
    """根据IV值返回CSS class"""
    if value >= 26: return "iv-s"
    if value >= 21: return "iv-a"
    if value >= 16: return "iv-b"
    if value >= 11: return "iv-c"
    if value >= 6:  return "iv-d"
    return "iv-e"


def _iv_bar_html(value: int) -> str:
    """IV进度条HTML（渐变纹理+圆角）"""
    pct = int(value / 31 * 100)
    cls = _iv_class(value)
    return (
        f'<span class="iv-track">'
        f'<span class="iv-fill {cls}" style="width:{pct}%"></span>'
        f'</span>'
    )


def _stat_row(icon: str, name: str, stat_key: str,
              pet: Pet, old_pet: Pet | None = None) -> str:
    """三列：图标 | 名称 | 数值+进度条(右) """
    val = getattr(pet, stat_key, 0)
    iv_val = getattr(pet, _IV_DEFS[_STAT_DEFS.index((icon, name, stat_key))][0], 0)

    if old_pet is not None:
        old_val = getattr(old_pet, stat_key, 0)
        def _fmt(v):
            if stat_key in ("crit", "eva"): return f"{v:.1f}%"
            if stat_key == "spd": return f"{v:.2f}"
            return f"{v:.0f}"
        val_str = f"{_fmt(old_val)} → {_fmt(val)}"
    else:
        if stat_key in ("crit", "eva"): val_str = f"{val:.1f}%"
        elif stat_key == "spd": val_str = f"{val:.2f}"
        else: val_str = f"{val:.0f}"

    return (
        f'<tr>'
        f'<td class="stat-icon">{icon}</td>'
        f'<td class="stat-name">{name}</td>'
        f'<td class="stat-right"><span class="stat-val">{val_str}</span>{_iv_bar_html(iv_val)}</td>'
        f'</tr>'
    )


def _quality_diamond_html(quality: str) -> str:
    """品质菱形色块HTML"""
    return (
        f'<div class="quality-wrap">'
        f'<div class="quality-diamond q-{quality.lower()}">'
        f'<span class="q-text">{quality}</span>'
        f'</div></div>'
    )


def _type_html(battle_type: str) -> str:
    """战斗类型HTML"""
    names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
    name = names.get(battle_type, battle_type)
    return f'<span class="type-{battle_type}">{name}</span>'


def _exp_bar(pet: Pet) -> str:
    """经验条HTML：标题同行右侧放数值，下方进度条"""
    ratio = pet.exp / pet.max_exp if pet.max_exp > 0 else 0
    pct = min(100, int(ratio * 100))
    return (
        f'<div class="exp-title-row">'
        f'<span class="exp-title">✨ 经验</span>'
        f'<span class="exp-val">{pet.exp}/{pet.max_exp} ({pct}%)</span>'
        f'</div>'
        f'<div class="exp-bar-bg">'
        f'<div class="exp-bar-fill" style="width:{pct}%"></div>'
        f'</div>'
    )


def _resolve_image_src(local_image_path: str, image_url: str) -> str:
    """解析宠物图片的实际 src 属性值。"""
    if local_image_path:
        return f"file:///{local_image_path.replace(chr(92), '/')}"

    marker = "/static/images/"
    idx = image_url.find(marker)
    if idx != -1:
        relative = image_url[idx + len(marker):]
        q_idx = relative.find("?")
        if q_idx != -1:
            relative = relative[:q_idx]
        local = Path(__file__).parent.parent / "data" / "images" / relative
        if local.exists():
            return f"file:///{local.resolve().as_posix()}"

    return image_url


def _skill_section_html(pet: Pet) -> str:
    """生成技能信息区域HTML（左右布局，右侧技能上下排列带↓箭头）"""
    from src.pet_config import PET_SPECIES

    stage_labels = ["一", "二", "三"]
    species = PET_SPECIES.get(pet.species_id, {})
    all_skills = species.get("skills", [])

    available = []
    for i in range(min(pet.evolution_stage + 1, len(all_skills))):
        skill = all_skills[i]
        if hasattr(skill, 'name'):
            available.append((stage_labels[i], skill))

    if not available:
        return ""

    right_items = []
    for idx, (stage_label, skill) in enumerate(available):
        cd_str = f"{skill.cd:.0f}" if skill.cd == int(skill.cd) else f"{skill.cd}"
        item = (
            f'<div class="skill-item">'
            f'<div class="skill-item-header">{stage_label}阶段（{cd_str}s）</div>'
            f'<div class="skill-item-desc">{skill.description}</div>'
            f'</div>'
        )
        right_items.append(item)
        if idx < len(available) - 1:
            right_items.append('<div class="skill-arrow">↓</div>')

    right_html = "\n".join(right_items)

    return (
        f'<div class="skill-section">'
        f'<div class="skill-left">'
        f'<div class="skill-left-name">{available[0][1].name}</div>'
        f'<div class="skill-left-tip">技能按阶段<br>轮流使用</div>'
        f'</div>'
        f'<div class="skill-right">{right_html}</div>'
        f'</div>'
    )


def render_pet_html(pet: Pet, image_url: str,
                    local_image_path: str = "",
                    old_pet: Pet | None = None,
                    base64_image: str = "") -> str:
    """渲染宠物信息HTML字符串（含技能信息区域）。

    Args:
        pet: 宠物数据对象
        image_url: 宠物形象图片URL
        local_image_path: 宠物形象图本地绝对路径
        old_pet: 进化前旧宠物，用于显示 旧值→新值 箭头预览
        base64_image: base64 data URI 格式图片，优先使用（配合 set_content 免临时文件）

    Returns:
        完整的HTML字符串（内联CSS）
    """
    stage_names = ["一阶", "二阶", "三阶"]
    stage = stage_names[pet.evolution_stage] if pet.evolution_stage < 3 else "三阶"
    quality = pet.quality
    type_str = _type_html(pet.battle_type)
    img_src = base64_image if base64_image else _resolve_image_src(local_image_path, image_url)

    # ── 头部：左图-中名-右品质菱形 ──
    subtitle = f"{type_str} · {stage} · Lv.{pet.level}"
    header = (
        f'<div class="header">'
        f'<img class="pet-img" src="{img_src}" alt="{pet.species_name}">'
        f'<div class="pet-info">'
        f'<div class="pet-name">{pet.name}</div>'
        f'<div class="pet-subtitle">{subtitle}</div>'
        f'</div>'
        f'{_quality_diamond_html(quality)}'
        f'</div>'
    )

    # ── 战斗属性 + 暴伤吸血（同一个table内） ──
    stat_rows = ""
    for icon, name, key in _STAT_DEFS:
        stat_rows += _stat_row(icon, name, key, pet, old_pet)

    stat_rows += (
        f'<tr>'
        f'<td class="stat-icon">🔪</td>'
        f'<td class="stat-name">暴伤</td>'
        f'<td class="stat-right"><span class="stat-val">{pet.crit_dmg*100:.0f}%</span></td>'
        f'</tr>'
        f'<tr>'
        f'<td class="stat-icon">🩸</td>'
        f'<td class="stat-name">吸血</td>'
        f'<td class="stat-right"><span class="stat-val">{pet.lifesteal*100:.0f}%</span></td>'
        f'</tr>'
    )

    stats_section = (
        f'<div class="section">'
        f'<div class="section-title">📊 战斗属性</div>'
        f'<table class="stat-table">{stat_rows}</table>'
        f'</div>'
    )

    # ── EXP 条 ──
    exp_part = (
        f'<div style="padding:8px 24px 12px;border-top:1px solid #f8fafc;'
        f'background:rgba(255,255,255,0.85)">'
        f'{_exp_bar(pet)}'
        f'</div>'
    )

    # ── 技能信息区域 ──
    skill_part = _skill_section_html(pet)

    footer = '<div class="footer">猪猪养成</div>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body><div class="card">
{header}
{stats_section}
{exp_part}
{skill_part}
{footer}
</div></body></html>"""


async def html_to_image(browser, html_str: str, output_path: Path,
                        page=None) -> None:
    """使用Playwright将HTML字符串渲染为PNG截图。

    通过 page.set_content() 直接注入 HTML，配合 base64 data URI 图片，
    无需写入临时文件或 file:// 协议加载，减少磁盘 I/O 开销。

    Args:
        browser: Playwright browser 实例（chromium headless）
        html_str: 完整的HTML字符串（图片应使用 base64 data URI）
        output_path: 输出PNG文件路径
        page: 可选的预热页面，传入则复用（不关闭），否则新建并关闭
    """
    import time as _time
    start = _time.time()

    own_page = page is None
    if own_page:
        page = await browser.new_page(viewport={"width": 380, "height": 800})
    try:
        await page.set_content(html_str, wait_until="load")
        body_height = await page.evaluate("document.body.scrollHeight")
        await page.set_viewport_size({"width": 380, "height": body_height + 8})
        await page.screenshot(path=str(output_path), full_page=True)
        elapsed = _time.time() - start
        logger.info(f"截图生成: {output_path.name} ({elapsed:.2f}s)")
    finally:
        if own_page:
            await page.close()
