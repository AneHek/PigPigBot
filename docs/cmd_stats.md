# /属性 (stats) 指令详细流程

## 概述

查看宠物详尽属性信息，包含六维 IV、战斗属性、经验条、进化门槛警告，返回截图+按钮消息。

## 调用链路

```
用户发送 "/属性"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/属性") → cmd="属性", arg=""
    │  get_handler("属性") → StatsMixin.stats_detail  (装饰器注册)
    │
    ▼
game/stats_cmd.py :: StatsMixin.stats_detail(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py :: PetStoreMixin.get_pet()
    │        └─ Redis GET qqbot:pet:{user_id}
    │        └─ JSON 反序列化 → Pet.from_dict()
    │        └─ 无宠物 → 返回错误提示
    │
    ├─ 2. self.dm.update_leaderboard(pet)
    │     └─ data/leaderboard.py → 刷新排行榜分数
    │
    ├─ 3. 进化门槛检查
    │     ├─ stage=0 且 level>=29 → 追加 "已达29级上限，需要进化"
    │     └─ stage=1 且 level>=59 → 追加 "已达59级上限，需要进化"
    │
    ├─ 4. 构建 title / tip / rows
    │     ├─ title: "{species_name}({game_uid}) 属性详情"
    │     ├─ tip: "品质：{pet.quality}  |  战力：{cp}  |  IV总和:{pet.iv_sum}/186"
    │     │       （cp = calc_cp(pet) 计算综合战力）
    │     └─ rows: [进化, 训练] / [战斗] 按钮
    │
    └─ 5. await self._build_pet_message(pet, title, tip, rows)
          └─ game/base.py → 调用 _generate_screenshot(pet) 生成通用截图
          └─ 若被 adopt/evolve/end_training 预生成过 → 缓存命中，~0ms
          └─ 若未预生成 → 实时截图，~170ms
          └─ 截图流程 → 详见 screenshot_flow.md
          └─ 返回 dict (msg_type=2, markdown, keyboard)
```

## 缓存命中场景

`/属性` 是后台预生成的目标场景。以下指令执行后，用户紧接着查看 `/属性` 时会直接命中缓存：

- `/领养` → 预生成通用截图
- `/进化` → 预生成通用截图
- `/休息` → 预生成通用截图

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 从 Redis 读取宠物数据 |
| `update_leaderboard()` | data/leaderboard.py | 刷新排行榜 |
| `quality_label()` | pet/stats.py | 品质字母→中文标签 |
| `_generate_screenshot()` | game/base.py | 截图核心：缓存/渲染/截图/并发控制 |
| `_build_pet_message()` | game/base.py | 调用截图核心 + 构建消息 |
