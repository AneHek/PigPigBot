# QQ 宠物战斗机器人 - 项目文档

## 一、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.10+ | 主语言 |
| Web 框架 | aiohttp | HTTP Webhook 服务 + 异步 API 调用 |
| 数据库 | Redis | 宠物数据持久化、排行榜、Token 存储 |
| 签名验证 | PyNaCl (Ed25519) | Webhook URL 验证签名 |
| 配置解析 | PyYAML | 加载 config.yaml / bot_config.yaml |
| 证书生成 | Cryptography | 自签名 SSL 证书自动生成 |
| 截图引擎 | Playwright (Chromium/Edge) | HTML → PNG 截图渲染 |
| 平台 API | QQ 开放平台 API v2 | Webhook 模式消息收发 |

## 二、项目文件摘要

| 文件 | 职责 |
|------|------|
| `main.py` | 入口文件。检查配置、创建 QQBot 实例、注入 game.bot 引用、启动事件循环 |
| `src/config.py` | 配置加载模块。合并 `config.yaml` 和 `bot_config.yaml` 为全局 `config` dict |
| `src/bot.py` | Webhook 服务核心。HTTPS 服务启动、签名验证、消息去重/防抖、事件分发、API 消息发送、Playwright 浏览器生命周期管理 |
| `src/handler.py` | 命令路由器。解析用户消息提取命令和参数，路由到 `PetGame` 对应方法 |
| `src/pet_game.py` | 游戏核心逻辑。领养、属性、进化、训练、战斗、排行、帮助等全部指令的业务实现 |
| `src/data_manager.py` | 数据持久化层。`Pet` 数据模型定义、Redis CRUD 操作、排行榜、截图 UUID 管理 |
| `src/pet_config.py` | 静态数据配置。26 种宠物定义、技能数据、成长表、进化系数、图片路径映射 |
| `src/pet_stats.py` | 属性计算引擎。IV 生成（二项分布品质）、属性公式计算、品质评级、格式化输出 |
| `src/battle.py` | 实时自动战斗引擎。0.1s tick 循环、伤害管线、状态效果、技能轮换、战斗报告生成 |
| `src/image_gen.py` | HTML 渲染 + Playwright 截图。宠物信息卡片 HTML 模板、CSS 样式、HTML→PNG 转换 |
| `src/image_lifecycle.py` | 截图生命周期管理。确定性 UUID 生成、延迟删除、启动清理、每日 0 点兜底清理 |
| `src/msg_templates.py` | 消息模板封装。QQ 官方 Markdown 模板消息、按钮键盘消息、组合消息构建 |
| `src/token_manager.py` | Token 管理器。QQ API access_token 获取、Redis 存储、后台定时刷新 |

## 三、信息处理前置流程

用户消息从 QQ 平台到最终回复的完整前置链路如下：

```
QQ 平台 (Webhook 推送)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  bot.py :: webhook_handler(request)                     │
│                                                         │
│  1. 解析 JSON 请求体                                     │
│  2. op=13 → URL 验证：                                   │
│     _verify_signature(event_ts, plain_token)             │
│     → Ed25519 签名 → 返回 {plain_token, signature}      │
│  3. op=0 → 事件分发：                                    │
│     ├─ msg_id 去重（10s TTL）                            │
│     ├─ user_id 防抖（2s 间隔）                           │
│     ├─ GROUP_AT_MESSAGE_CREATE → handle_group_at()      │
│     └─ C2C_MESSAGE_CREATE → handle_c2c()                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  bot.py :: handle_group_at / handle_c2c                 │
│                                                         │
│  1. 提取 content / user_id / user_name / msg_id         │
│  2. [群聊] data_manager.add_group_member(group, user)   │
│     └─ Redis SADD qqbot:group:{group_id} {user_id}     │
│  3. 调用 handle_message(user_id, user_name, content)    │
│  4. 获取 reply → 检测类型：                              │
│     ├─ list → 多消息模式（战斗）：                       │
│     │   ├─ send_reply(msg_seq=1) → 第一条消息           │
│     │   ├─ asyncio.sleep(1) → 间隔至少 1 秒             │
│     │   └─ send_reply(msg_seq=2) → 第二条消息           │
│     └─ 其他 → 单消息模式：send_reply(reply)             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  handler.py :: handle_message(user_id, user_name, content)│
│                                                         │
│  1. parse_command(content) → 正则提取命令名 + 参数        │
│     - 去除 <@!xxx> / @xxx 标记                           │
│     - 匹配 /命令 或 ／命令 格式                           │
│  2. 命令路由表匹配（中英文双语）                          │
│     - /战斗 <游戏ID> → 参数作为 game_uid                 │
│       → data_manager.get_user_by_game_uid() 反查 QQ ID  │
│     - 匹配成功 → 调用 game.xxx() 方法                    │
│     - 匹配失败 → 返回未知命令提示                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  pet_game.py :: PetGame 方法                            │
│                                                         │
│  业务逻辑处理 → 可能触发截图生成                          │
│  → 返回 str（纯文本）或 dict（Markdown+按钮消息）        │
│  → 战斗指令返回 list[str, str]（两次消息）               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  bot.py :: send_group_reply / send_c2c_reply            │
│                                                         │
│  1. _build_msg_payload(reply, msg_id, msg_seq)          │
│     └─ msg_seq > 0 时添加 "msg_seq" 到 POST 载荷       │
│  2. _post_api(url, payload) → POST 到 QQ API v2         │
│     - 从 Redis 获取 access_token (token_manager)        │
│     - 构建 Authorization: QQBot {token} 请求头          │
└─────────────────────────────────────────────────────────┘
```

## 四、项目启动流程

```
python main.py
    │
    ├─ 1. check_config()
    │     检查 bot_config.yaml 中 app_id / secret 是否已填写
    │
    ├─ 2. QQBot() 实例化
    │     初始化去重/防抖字典、Playwright 引用、
    │     截图并发信号量 (_screenshot_semaphore)、页面预热池 (_page_pool)
    │
    ├─ 3. game.bot = bot
    │     注入 bot 引用到 PetGame，使截图功能可用
    │
    └─ 4. await bot.start()
          │
          ├─ 4a. token_manager.start()
          │      连接 Redis → 首次获取 access_token → 启动后台刷新协程
          │
          ├─ 4b. asyncio.create_task(_cleanup_loop())
          │      启动去重/防抖记录过期清理协程（每 30s）
          │
          ├─ 4c. aiohttp web.Application 路由注册
          │      - POST/GET /qqbot/webhook → webhook_handler
          │      - /static/images → 静态图片服务
          │
          ├─ 4d. 截图目录初始化
          │      - cleanup_orphan_files() 清理孤儿截图
          │      - 启动每日 0 点兜底清理协程
          │
          ├─ 4e. Playwright 浏览器启动
          │      优先 chromium → 失败回退 msedge → 均失败则截图不可用
          │
          ├─ 4e2. 页面预热池初始化
          │       预创建 N 个 page 实例（N = screenshot_concurrency）
          │       截图时复用预热页面，省去 new_page 开销
          │
          ├─ 4f. SSL 配置
          │      force_https=true → 加载/生成自签名证书
          │      force_https=false → HTTP 模式（配合 nginx/ngrok）
          │
          └─ 4g. web.TCPSite 启动
                 监听 host:port，进入无限循环等待事件推送
```

## 五、各指令详细处理流程

| 指令 | 说明 | 详细文档 |
|------|------|----------|
| `/领养` | 随机领养宠物（首次自动分配游戏用户ID） | [cmd_adopt.md](cmd_adopt.md) |
| `/属性` | 查看宠物详细属性 | [cmd_stats.md](cmd_stats.md) |
| `/遗弃` | 遗弃当前宠物 | [cmd_abandon.md](cmd_abandon.md) |
| `/改名` | 给宠物改名 | [cmd_rename.md](cmd_rename.md) |
| `/排行` | 查看排行榜 | [cmd_top.md](cmd_top.md) |
| `/帮助` | 查看帮助菜单 | [cmd_help.md](cmd_help.md) |
| `/进化` | 进化宠物 | [cmd_evolve.md](cmd_evolve.md) |
| `/训练` | 开始挂机训练 | [cmd_train.md](cmd_train.md) |
| `/休息` | 结束训练领取经验 | [cmd_rest.md](cmd_rest.md) |
| `/战斗` | PvP 战斗（入参游戏用户ID） | [cmd_battle.md](cmd_battle.md) |
| `/注册` | 生成游戏用户ID（兼容旧用户，不在帮助页显示） | — |

## 六、浏览器截图流程

截图系统的完整技术流程详见：[screenshot_flow.md](screenshot_flow.md)
