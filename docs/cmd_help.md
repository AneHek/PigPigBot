# /帮助 (help) 指令详细流程

## 概述

返回帮助菜单，以 Markdown 模板 + 按钮键盘的形式输出。
Markdown 模板中嵌入帮助菜单截图（`data/images/help.png`），下方附带快捷操作按钮。

注意：`/注册` 命令不在帮助页显示，仅用于兼容旧用户。

## 帮助菜单截图

帮助菜单的视觉内容由根目录下的 `help_menu.html` 提供，
通过 Playwright 截图生成 `data/images/help.png`，作为 Markdown 模板的图片嵌入。

| 文件 | 用途 |
|------|------|
| `help_menu.html`（根目录） | 帮助菜单 HTML 源文件，定义菜单布局和样式 |
| `data/images/help.png` | Playwright 截图输出，Markdown 模板中引用的图片 |
| `test/test_image_gen.py :: test_real_help_menu` | 测试用例，执行截图生成并验证输出 |

截图更新流程：修改 `help_menu.html` → 运行 `python -m unittest test.test_image_gen.TestRealImageGeneration.test_real_help_menu` → 新截图覆盖 `data/images/help.png`。

## 调用链路

```
用户发送 "/帮助" 或 "/菜单"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/帮助") → cmd="帮助", arg=""
    │  get_handler("帮助") → HelpMixin.help  (装饰器注册)
    │  get_handler("菜单") → HelpMixin.help  (别名)
    │
    ▼
game/help_cmd.py :: HelpMixin.help(user_id, user_name, arg, group_id)
    │
    ├─ 1. 构建图片 URL
    │     └─ callback_domain + /static/images/help.png
    │
    ├─ 2. 构建按钮行
    │     ├─ [/领养] [/属性] [/训练]
    │     ├─ [/副本] [/boss] [/签到]
    │     ├─ [/背包] [/排行] [/被动]
    │     └─ [/活动]
    │
    └─ 3. 调用 build_markdown_with_buttons()
          └─ 返回 msg_type=2 的 Markdown + keyboard 消息字典
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `help()` | game/help_cmd.py | 构建 Markdown + 按钮消息 |
| `build_markdown_with_buttons()` | msg_templates.py | 组合 Markdown 模板和按钮键盘 |
