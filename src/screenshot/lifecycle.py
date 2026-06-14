"""
image_lifecycle.py — 截图文件生命周期管理。

提供延迟删除、启动清理、每日兜底清理、基于 last_update 的确定性 UUID 生成。
"""
import uuid
import asyncio
import datetime
import logging
from pathlib import Path

logger = logging.getLogger("QQBot")


def generate_screenshot_uuid(user_id: str, last_update: float,
                              scene: str = "") -> str:
    """基于 user_id、last_update 和 scene 生成确定性 UUID。

    只要 pet.last_update 和 scene 不变，UUID 就不变，对应的截图无需重新生成。

    Args:
        user_id: 用户 ID
        last_update: 宠物数据最后更新时间戳
        scene: 场景标识 (adopt/stats/evolve/training)

    Returns:
        确定性 UUID 字符串
    """
    seed = f"{user_id}:{last_update}:{scene}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


async def schedule_deletion(filepath: Path, delay_seconds: int = 60) -> None:
    """异步延迟指定秒后删除文件。

    使用 asyncio.create_task 创建的独立任务，静默处理异常。

    Args:
        filepath: 要删除的文件路径
        delay_seconds: 延迟秒数，默认60
    """
    async def _delete():
        try:
            await asyncio.sleep(delay_seconds)
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"截图已清理: {filepath.name}")
        except Exception as e:
            logger.warning(f"截图清理失败 {filepath}: {e}")

    asyncio.create_task(_delete())


def cleanup_orphan_files(dir_path: Path) -> int:
    """同步清理指定目录下所有文件（启动时清理孤儿文件）。

    Args:
        dir_path: 要清理的目录路径

    Returns:
        清理的文件数量
    """
    if not dir_path.exists():
        return 0
    count = 0
    for f in dir_path.iterdir():
        if f.is_file():
            try:
                f.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"清理孤儿文件失败 {f}: {e}")
    if count > 0:
        logger.info(f"启动清理: 已删除 {dir_path} 下 {count} 个孤儿截图")
    return count


async def daily_cleanup_loop(dir_path: Path) -> None:
    """后台协程：每天 0 点清理截图目录所有文件（兜底机制）。

    计算到下一个 0 点的秒数休眠，到达后调用 cleanup_orphan_files 全量清理。

    Args:
        dir_path: 截图目录路径
    """
    while True:
        now = datetime.datetime.now()
        # 计算到下一个 0 点的秒数
        next_midnight = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + datetime.timedelta(days=1)
        wait_seconds = (next_midnight - now).total_seconds()
        logger.info(f"截图每日清理: 将在 {wait_seconds:.0f}s 后 ({next_midnight:%H:%M}) 执行")
        await asyncio.sleep(wait_seconds)
        count = cleanup_orphan_files(dir_path)
        if count > 0:
            logger.info(f"截图每日清理完成: 已删除 {count} 个文件")
