# QQ 宠物养成机器人

基于 QQ 开放平台官方 API (v2) 的宠物养成游戏娱乐机器人，**Webhook 模式 (HTTPS)**，仅处理群聊 @ 消息和私聊消息。

## 功能特性

- 🐱 **领养宠物** - 6种可爱宠物可选（猫咪、小狗、兔子、小龙、熊猫、狐狸）
- 🎮 **丰富互动** - 喂食、玩耍、休息、治疗、打工、训练
- 📈 **养成系统** - 饱食度、心情、健康、体力四维属性 + 等级经验成长
- 💰 **经济系统** - 打工赚金币，消耗金币进行各项活动
- 🏆 **排行榜** - 全服宠物等级排行
- ⚠️ **自然衰减** - 宠物属性会随时间衰减，需要持续照顾
- 💀 **死亡机制** - 疏于照顾宠物会死亡
- 🎨 **等级称号** - 幼年期到至尊级，9个成长阶段
- 📝 **Markdown 模板** - 支持 QQ 官方 Markdown 消息模板
- 🔘 **按钮列表** - 支持可配置行列的内嵌键盘按钮

## 快速开始

### 1. 获取机器人凭证

前往 [QQ 开放平台](https://q.qq.com) 创建机器人应用，获取：
- AppID（机器人 ID）
- Token（机器人令牌）
- AppSecret（密钥）

### 2. 修改配置

#### 敏感凭证（bot_config.yaml，已加入 .gitignore）

编辑 `bot_config.yaml`，填入你的凭证：

```yaml
bot:
  app_id: "123456789"
  token: "your_bot_token_here"
  secret: "your_app_secret_here"
  sandbox: true  # 首次测试建议开启沙箱模式
```

#### 公共配置（config.yaml）

```yaml
webhook:
  host: "0.0.0.0"
  port: 8443 # 自行配置端口
  path: "/qqbot/webhook"
  ssl_cert: "certs/cert.pem"   # HTTPS 证书
  ssl_key: "certs/key.pem"     # HTTPS 密钥

image:
  dir: "data/images"            # 本地图片目录
  route: "/static/images"       # 图片访问路由

redis:
  host: "localhost"
  port: 6379
  password: ""
  db: 0
```

### 3. 配置 HTTPS 证书

将 SSL 证书文件放入 `certs/` 目录：
- `certs/cert.pem` - SSL 证书
- `certs/key.pem` - 私钥文件

> 测试环境可使用自签名证书，生产环境建议使用 Let's Encrypt 等正规证书。

### 4. 启动 Redis

确保本地 Redis 服务已启动（端口 6379，无密码）：

```bash
# Windows (使用 WSL 或 Docker)
docker run -d -p 6379:6379 redis:latest

# Linux / macOS
redis-server
```

### 5. 配置 QQ 开放平台回调地址

在 QQ 开放平台机器人管理后台，配置 Webhook 回调地址为：

```
https://你的服务器IP:端口/qqbot/webhook
```

> **注意**：本地调试需要使用内网穿透工具（如 ngrok、frp），将本地端口暴露为公网地址。

### 6. 安装依赖

```bash
pip install -r requirements.txt
```

### 7. 启动机器人

```bash
python main.py
```

## 消息模板使用

### Markdown 模板

```python
from src.msg_templates import build_markdown_msg

# 构建 Markdown 消息
msg = build_markdown_msg(
    title="宠物状态",
    image="https://your-server:8443/static/images/pet_cat.png",
    tip="这是一只可爱的猫咪"
)
# 返回结构化消息字典，可直接传入 send_group_reply / send_c2c_reply
```

### 按钮列表模板

```python
from src.msg_templates import build_button_list_msg, build_auto_grid

# 方式一：自动网格排列
buttons = [("喂食", "/喂食"), ("玩耍", "/玩耍"), ("休息", "/休息"),
           ("状态", "/状态"), ("打工", "/打工"), ("帮助", "/帮助")]
rows = build_auto_grid(buttons, cols=2)

msg = build_button_list_msg(
    content="请选择操作：",
    rows=rows,
)

# 方式二：手动指定行列
msg = build_button_list_msg(
    content="请选择操作：",
    rows=[
        [{"text": "喂食", "command": "/喂食"}, {"text": "状态", "command": "/状态"}],
        [{"text": "打工", "command": "/打工"}, {"text": "帮助", "command": "/帮助"}],
    ],
)
```

### 图片服务

将图片放入 `data/images/` 目录，QQ 官方可通过以下地址访问：

```
https://你的服务器:8443/static/images/图片文件名.png
```

## 架构说明

| 项目 | 说明 |
|------|------|
| 连接模式 | **Webhook**（HTTPS 回调），无需维护长连接 |
| 事件订阅 | 群聊 `@` 机器人的消息 + 用户私聊机器人的消息 |
| 签名验证 | HMAC-SHA256，用 AppSecret 签名 plain_token |
| 数据存储 | **Redis**（高性能 KV 存储） |
| 消息回复 | 异步调用 QQ 开放平台消息 API，支持文本/模板消息 |

## 命令列表

| 命令 | 说明 | 消耗 |
|------|------|------|
| `/领养 <种类>` | 领养一只宠物 | - |
| `/状态` | 查看宠物详细状态 | - |
| `/喂食` | 喂食宠物 | 5💰 |
| `/玩耍` | 和宠物玩耍 | 体力≥10 |
| `/休息` | 让宠物休息恢复体力 | - |
| `/治疗` | 带宠物去医院 | 15💰 |
| `/打工` | 打工赚金币 | 体力≥15, 心情≥10 |
| `/训练` | 特训获取大量经验 | 体力≥20, 饱食≥15 |
| `/改名 <名字>` | 给宠物改名字 | 30💰 |
| `/遗弃` | 遗弃当前宠物 | - |
| `/排行` | 查看全局排行榜 | - |
| `/帮助` | 查看帮助菜单 | - |

## 宠物类型

| 宠物 | 特点 |
|------|------|
| 🐱 猫咪 | 各项均衡，适合新手 |
| 🐶 小狗 | 体力成长高，活泼好动 |
| 🐰 兔子 | 心情好，不易沮丧 |
| 🐲 小龙 | 初始属性高，稀有品种 |
| 🐼 熊猫 | 体质强壮，健康值高 |
| 🦊 狐狸 | 聪明伶俐，训练加成 |

## 成长阶段

| 等级 | 称号 |
|------|------|
| 1-2 | 🥚 宠物蛋 |
| 3-4 | 🌟 幼年期 |
| 5-9 | ⭐ 成长期 |
| 10-19 | 💫 成熟期 |
| 20-34 | 🔥 完全体 |
| 35-49 | 👑 究极体 |
| 50-79 | 🌌 传说级 |
| 80-99 | ✨ 神话级 |
| 100+ | 💎 至尊级 |

## 项目结构

```
QQBot/
├── main.py              # 入口文件
├── config.yaml          # 公共配置文件
├── bot_config.yaml      # 敏感凭证配置（已加入 .gitignore）
├── .gitignore
├── requirements.txt     # 依赖列表
├── certs/               # SSL 证书目录
├── data/
│   └── images/          # 本地图片存储目录
├── src/
│   ├── __init__.py
│   ├── bot.py           # Webhook HTTPS 服务 + 事件处理 + API 调用
│   ├── config.py        # 配置加载（合并 bot_config.yaml 和 config.yaml）
│   ├── data_manager.py  # Redis 数据持久化
│   ├── handler.py       # 命令路由
│   ├── msg_templates.py # Markdown / 按钮列表消息模板
│   └── pet_game.py      # 游戏核心逻辑
└── README.md
```

## 技术栈

- **Python 3.10+**
- **aiohttp** - HTTPS 服务器 + 异步 API 调用
- **Redis** - 高性能数据存储
- **PyYAML** - 配置文件解析
- **QQ 开放平台 API v2** - 官方机器人接口 (Webhook 模式)
