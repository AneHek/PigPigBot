"""
main.py - 宠物养成 QQ 机器人入口 (Webhook 模式)
"""
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.bot import QQBot
from src.config import config

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Main")


def check_config():
    """检查配置是否已填写"""
    bot_cfg = config.get("bot", {})
    secret_file = Path(__file__).parent / "bot_config.yaml"

    missing = []
    if not bot_cfg.get("app_id") or bot_cfg["app_id"] == "YOUR_APP_ID":
        missing.append("app_id")
    if not bot_cfg.get("secret") or bot_cfg["secret"] == "YOUR_APP_SECRET":
        missing.append("secret")

    if missing:
        logger.error(
            f"请先在 {secret_file.name} 中填写以下配置项: {', '.join(missing)}\n"
            f"前往 QQ 开放平台 (https://q.qq.com) 获取 AppID 和 Secret\n"
            f"（access_token 将自动通过 API 获取，无需手动填写）"
        )
        sys.exit(1)


async def main():
    check_config()

    bot = QQBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.exception(f"机器人异常退出: {e}")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
