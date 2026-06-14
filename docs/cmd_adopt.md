# /领养 (adopt) 指令详细流程

## 概述

随机领养一只猪猪宠物（P001~P025），生成 IV、品质、初始属性，返回截图+按钮消息。首次领养自动分配游戏用户ID（从1开始递增）。

## 调用链路

```
用户发送 "/领养"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/领养") → cmd="领养", arg=""
    │  get_handler("领养") → AdoptMixin.adopt  (装饰器注册)
    │
    ▼
game/adopt.py :: AdoptMixin.adopt(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.has_pet(user_id)
    │     └─ 已有宠物 → 返回错误提示文本
    │
    ├─ 2. 游戏用户ID分配
    │     ├─ self.dm.get_user_game_uid(user_id)
    │     │   └─ data/group.py → Redis GET qqbot:user_game_uid:{user_id}
    │     ├─ 若返回 0（首次）→ self.dm.assign_game_uid(user_id)
    │     │   └─ Redis INCR qqbot:game_uid_counter → 原子递增
    │     │   └─ Redis SET qqbot:user_game_uid:{user_id} {game_uid}
    │     │   └─ Redis SET qqbot:game_uid:{game_uid} {user_id}（反查映射）
    │     └─ 若已有 → 复用（遗弃后重新领养保留原ID）
    │
    ├─ 3. random.randint(1, 25) → species_id = f"P{num:03d}"
    │
    ├─ 4. generate_quality() + generate_ivs() + calc_stats()
    │     └─ pet/stats.py → 生成品质、IV、初始属性
    │
    ├─ 5. self.dm.create_pet(...) + update_pet(game_uid=game_uid)
    │     └─ data/pet_store.py → 创建宠物并写入 game_uid
    │
    ├─ 6. self.dm.update_leaderboard(pet)
    │
    ├─ 7. 构建 title / tip / rows
    │     ├─ title: "🎉 {pet_name} 成为了你的伙伴！"
    │     ├─ tip: "品质：{q_rating}({quality_label})  |  类型：{btype_cn}  |  游戏ID：{game_uid}  |  战力：{cp}  |  可使用「/改名」给宠物取一个喜欢的名字哦~"
    │     │       （cp = calc_cp(pet) 计算综合战力）
    │     └─ rows: [属性详情, 战斗] / [训练] 按钮
    │
    ├─ 8. msg = await self._build_pet_message(pet, title, tip, rows)
    │     └─ game/base.py → 调用 _generate_screenshot(pet) 生成通用截图
    │     └─ 截图流程 → 详见 screenshot_flow.md
    │
    └─ 9. asyncio.create_task(self._pre_generate_screenshot(pet))
          └─ 后台预生成通用截图（fire-and-forget）
```

## 游戏用户ID机制

- 首次领养时自动分配，从 1 开始原子递增
- 遗弃宠物后重新领养，保留原游戏用户ID
- 游戏用户ID用于 `/战斗` 命令的目标指定
- 旧用户可通过 `/注册` 命令补领

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `has_pet()` | data/pet_store.py | 检查用户是否已有宠物 |
| `get_user_game_uid()` | data/group.py | 获取用户游戏用户ID |
| `assign_game_uid()` | data/group.py | 原子分配游戏用户ID + 建立双向映射 |
| `generate_quality()` | pet/stats.py | 二项分布生成品质档位 |
| `generate_ivs()` | pet/stats.py | 生成 6 维 IV 个体值 |
| `calc_stats()` | pet/stats.py | 计算战斗属性 |
| `create_pet()` | data/pet_store.py | 创建宠物并写入 Redis |
| `update_pet()` | data/pet_store.py | 更新宠物 game_uid 字段 |
| `update_leaderboard()` | data/leaderboard.py | 更新排行榜 |
| `_generate_screenshot()` | game/base.py | 截图核心 |
| `_pre_generate_screenshot()` | game/base.py | 后台预生成通用截图 |
| `_build_pet_message()` | game/base.py | 调用截图核心 + 构建消息 |
