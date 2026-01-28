# -*- coding: utf-8 -*-
"""
Telegram 时政经济监控系统 - 主入口
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config import get_config


def setup_logging(debug: bool = False):
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO

    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d')
    log_file = log_dir / f"telegram_monitor_{today}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        '%Y-%m-%d %H:%M:%S'
    ))
    root.addHandler(console)

    # 文件
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        '%Y-%m-%d %H:%M:%S'
    ))
    root.addHandler(file_handler)

    # 降低第三方库日志级别
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(description='Telegram 时政经济监控系统')

    parser.add_argument('--monitor', action='store_true', help='启动实时监听')
    parser.add_argument('--report', action='store_true', help='生成每日早报')
    parser.add_argument('--interval', type=int, default=5, help='批量分析间隔（分钟）')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    parser.add_argument('--generate-session', action='store_true', help='生成 Telegram Session')

    return parser.parse_args()


def run_monitor(interval: int, debug: bool):
    """运行监听"""
    from monitor import run_monitor as _run
    asyncio.run(_run(batch_interval=interval, debug=debug))


def run_report():
    """运行早报"""
    from daily_report import run_daily_report
    run_daily_report()


def generate_session():
    """生成 Session"""
    import asyncio
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    config = get_config()

    if not config.telegram_api_id or not config.telegram_api_hash:
        print("❌ 请先配置 TELEGRAM_API_ID 和 TELEGRAM_API_HASH")
        return

    async def main():
        print("=" * 50)
        print("Telegram Session 生成器")
        print("=" * 50)

        # 文件 Session
        session_dir = Path("./data/telegram")
        session_dir.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(
            str(session_dir / "telegram_monitor"),
            config.telegram_api_id,
            config.telegram_api_hash
        )

        await client.start(phone=config.telegram_phone)
        me = await client.get_me()
        print(f"\n✅ 登录成功: {me.first_name}")
        print(f"✅ Session 文件: {session_dir}/telegram_monitor.session")

        # StringSession
        string_client = TelegramClient(
            StringSession(),
            config.telegram_api_id,
            config.telegram_api_hash
        )
        await string_client.start(phone=config.telegram_phone)
        session_string = string_client.session.save()

        print(f"\n{'=' * 50}")
        print("StringSession（用于服务器部署）:")
        print("-" * 50)
        print(session_string)
        print("-" * 50)
        print(f"\n添加到 .env: TELEGRAM_SESSION={session_string[:50]}...")

        await client.disconnect()
        await string_client.disconnect()

    asyncio.run(main())


def main():
    args = parse_args()
    setup_logging(args.debug)

    logger = logging.getLogger(__name__)

    config = get_config()
    warnings = config.validate()
    for w in warnings:
        logger.warning(w)

    logger.info("=" * 50)
    logger.info("Telegram 时政经济监控系统")
    logger.info("=" * 50)

    if args.generate_session:
        generate_session()
        return 0

    if args.report:
        logger.info("模式: 每日早报")
        run_report()
        return 0

    if args.monitor:
        logger.info(f"模式: 实时监听 (间隔={args.interval}分钟)")
        run_monitor(args.interval, args.debug)
        return 0

    # 默认启动监听
    logger.info("默认模式: 实时监听")
    run_monitor(args.interval, args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
