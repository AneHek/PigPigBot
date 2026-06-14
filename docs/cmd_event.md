# /活动 指令详细流程

## 概述

查看当前进行中的活动列表。活动由管理员通过 Redis 配置，机器人自动扫描并过滤出当前时间范围内的活跃活动。纯文本回复。

## /活动 调用链路

```
用户发送 "/活动"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/活动") → cmd="活动", arg=""
    │  get_handler("活动") → EventMixin.event_list  (装饰器注册)
    │
    ▼
game/event.py :: EventMixin.event_list(user_id, user_name, arg, group_id)
    │
    ├─ 1. 扫描活动配置
    │     └─ for key in _redis_client.scan_iter(match="qqbot:event:*")
    │         └─ data/models.py → Redis SCAN 遍历所有活动 key
    │
    ├─ 2. 过滤活跃活动
    │     ├─ data = _redis_client.hgetall(key)
    │     │   └─ Redis HGETALL qqbot:event:{event_id}
    │     │   └─ 返回 hash: {type, name, start, end, multiplier, active}
    │     ├─ data.get("active", "0") != "1" → 跳过（未启用）
    │     ├─ start = float(data.get("start", 0))
    │     ├─ end = float(data.get("end", 0))
    │     └─ start <= now <= end → 加入 events 列表
    │
    ├─ 3. [无活动] 返回 "🎉 当前没有进行中的活动"
    │
    └─ 4. 构建活动列表文本
          ├─ 遍历 events
          ├─ 每个活动：
          │   ├─ name = ev.get("name", "未知活动")
          │   ├─ ev_type = ev.get("type", "")
          │   │   └─ 映射中文：double_exp→双倍经验, drop_boost→掉落加成,
          │   │      temp_boss→限时 Boss, checkin_boost→签到加成
          │   ├─ multiplier = ev.get("multiplier", "1")
          │   ├─ end_ts = float(ev.get("end", 0))
          │   └─ remaining = int((end_ts - now) / 3600)  # 剩余小时数
          └─ 输出格式：
              🎊 {name}
                 类型：{type_label}  倍率：×{multiplier}
                 剩余：约 {remaining} 小时
```

## Redis 活动配置结构

```
Key:   qqbot:event:{event_id}
Type:  hash
Fields:
  type       — 活动类型（double_exp / drop_boost / temp_boss / checkin_boost）
  name       — 活动名称（显示用）
  start      — 开始时间戳（Unix timestamp）
  end        — 结束时间戳（Unix timestamp）
  multiplier — 倍率（如 2.0 = 双倍）
  active     — 1=开启 / 0=关闭
```

管理员通过 Redis CLI 或管理脚本配置活动，机器人启动时加载活动列表，运行时按 `start/end` 自动生效/过期。

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `_redis_client.scan_iter()` | data/models.py | 扫描 Redis 中所有活动 key |
| `_redis_client.hgetall()` | data/models.py | 获取单个活动的完整配置 |
