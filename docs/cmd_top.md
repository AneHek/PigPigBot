# /排行 (top) 指令详细流程

## 概述

查看全局宠物排行榜 TOP10，按等级+经验综合分数排序。纯文本回复，无截图。

## 调用链路

```
用户发送 "/排行"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/排行") → cmd="排行", arg=""
    │  handlers["排行"] → game.top()
    │
    ▼
pet_game.py :: PetGame.top()
    │
    ├─ 1. self.dm.get_leaderboard(10)
    │     └─ data_manager.py :: DataManager.get_leaderboard()
    │        ├─ Redis ZREVRANGE qqbot:leaderboard 0 9
    │        │   → 按分数降序取前 10 个 user_id
    │        └─ 逐个 Redis HGET qqbot:leaderboard:detail {uid}
    │            → JSON 反序列化获取详情
    │            → 类型转换 (level/exp/evolution_stage → int)
    │
    ├─ 2. 空排行榜 → 返回空提示
    │
    └─ 3. 格式化输出
          ├─ 前三名使用 🥇🥈🥉 奖牌
          ├─ 4~10 名使用数字序号
          └─ 每行: {medal} {species_name}「{pet_name}」(Lv.{level} {stage}) - {owner_name}
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_leaderboard()` | data_manager.py | 从 Redis 获取 TOP N 排行数据 |
