# -*- coding: utf-8 -*-
"""
监听主调度器
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from telethon.tl.types import Channel, Message

from config import get_config
from notification import NotificationService
from client import TelegramClientWrapper
from message_filter import MessageFilter, ImpactLevel
from analyzer import NewsAnalyzer
from storage import Storage
from daily_report import DailyReport
from trend_updater import TrendUpdater

logger = logging.getLogger(__name__)


@dataclass
class QueuedMessage:
    text: str
    channel_title: str
    channel_id: int
    timestamp: datetime


@dataclass
class Stats:
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone(timedelta(hours=8))))
    total: int = 0
    queued: int = 0
    excluded: int = 0
    analyzed: int = 0
    valuable: int = 0
    pushed: int = 0


class Monitor:
    """Telegram 监听器"""

    IMPACT_THRESHOLD = 4

    def __init__(self, batch_interval: int = 5, debug: bool = False):
        config = get_config()

        self._channel_ids = config.telegram_channels
        self._batch_interval = batch_interval
        self._debug = debug

        self._client: Optional[TelegramClientWrapper] = None
        self._filter = MessageFilter()
        self._analyzer = NewsAnalyzer()
        self._notifier = NotificationService()
        self._storage = Storage()
        self._daily_report = DailyReport()
        self._trend_updater = TrendUpdater()

        self._queue: deque = deque(maxlen=200)
        self._stats = Stats()
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None
        self._daily_report_task: Optional[asyncio.Task] = None
        self._trend_task: Optional[asyncio.Task] = None

        logger.info(f"监听器初始化: 频道={len(self._channel_ids)}, 间隔={batch_interval}分钟")

    async def start(self) -> bool:
        if self._running:
            return True

        try:
            self._client = TelegramClientWrapper()
            if not await self._client.start():
                return False

            subscribed = await self._client.subscribe_channels(
                self._channel_ids, self._on_message
            )

            if subscribed == 0:
                await self._client.stop()
                return False

            self._running = True
            logger.info(f"监听器启动，已订阅 {subscribed} 个频道")
            return True

        except Exception as e:
            logger.error(f"启动失败: {e}")
            return False

    async def run(self):
        if not self._running:
            return

        self._batch_task = asyncio.create_task(self._batch_loop())
        self._daily_report_task = asyncio.create_task(self._daily_report_loop())
        self._trend_task = asyncio.create_task(self._trend_loop())
        logger.info("开始监听...")

        try:
            await self._client.run_forever()
        finally:
            await self.stop()

    async def stop(self):
        if not self._running:
            return

        self._running = False

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        if self._daily_report_task:
            self._daily_report_task.cancel()
            try:
                await self._daily_report_task
            except asyncio.CancelledError:
                pass

        if self._trend_task:
            self._trend_task.cancel()
            try:
                await self._trend_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.stop()

        logger.info(f"已停止，统计: 总={self._stats.total}, 有价值={self._stats.valuable}")

    async def _on_message(self, message: Message, channel: Channel):
        try:
            text = message.text or ""
            if not text:
                return

            self._stats.total += 1
            channel_title = getattr(channel, 'title', str(channel.id))

            logger.info(f"[#{self._stats.total}] {channel_title}: {text[:60]}...")

            result = self._filter.filter_message(text)

            if result.impact_level == ImpactLevel.EXCLUDED:
                self._stats.excluded += 1
                return

            self._queue.append(QueuedMessage(
                text=text,
                channel_title=channel_title,
                channel_id=channel.id,
                timestamp=datetime.now(timezone(timedelta(hours=8)))
            ))
            self._stats.queued += 1

        except Exception as e:
            logger.error(f"处理消息错误: {e}")

    async def _batch_loop(self):
        interval = self._batch_interval * 60

        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._queue:
                    await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批量处理错误: {e}")

    async def _daily_report_loop(self):
        """每日早报定时任务，每天 8:30 发送"""
        REPORT_HOUR = 8
        REPORT_MINUTE = 30

        while self._running:
            try:
                now = datetime.now(timezone(timedelta(hours=8)))
                # 计算下次 8:30 的时间
                target = now.replace(hour=REPORT_HOUR, minute=REPORT_MINUTE, second=0, microsecond=0)
                if now >= target:
                    # 已过今天 8:30，等明天
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                logger.info(f"每日早报将在 {target.strftime('%Y-%m-%d %H:%M')} 发送，等待 {wait_seconds/3600:.1f} 小时")

                await asyncio.sleep(wait_seconds)

                # 发送早报
                logger.info("===== 开始生成每日早报 =====")
                success = await asyncio.to_thread(self._daily_report.run)
                if success:
                    logger.info("每日早报发送成功")
                else:
                    logger.warning("每日早报未生成或发送失败")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"每日早报任务错误: {e}")
                # 出错后等待 1 小时再重试
                await asyncio.sleep(3600)

    async def _trend_loop(self):
        """动态热词更新任务，每天 6:00 更新"""
        UPDATE_HOUR = 6
        UPDATE_MINUTE = 0

        # 启动时先尝试更新一次（如果不阻塞太久的话，或者放后台）
        # 这里选择先运行一次，确保启动时是最新的
        logger.info("启动热词更新...")
        await asyncio.to_thread(self._trend_updater.update)
        self._filter.reload()

        while self._running:
            try:
                now = datetime.now(timezone(timedelta(hours=8)))
                target = now.replace(hour=UPDATE_HOUR, minute=UPDATE_MINUTE, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                logger.info(f"下次热词更新将在 {target.strftime('%Y-%m-%d %H:%M')}，等待 {wait_seconds/3600:.1f} 小时")

                await asyncio.sleep(wait_seconds)

                logger.info("===== 开始更新动态热词 =====")
                success = await asyncio.to_thread(self._trend_updater.update)
                if success:
                    self._filter.reload()
                    logger.info("动态热词更新成功并已重载")
                else:
                    logger.warning("动态热词更新失败")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"热词更新任务错误: {e}")
                await asyncio.sleep(3600)

    async def _process_batch(self):
        messages = list(self._queue)
        self._queue.clear()

        logger.info(f"===== 批量分析 {len(messages)} 条消息 =====")

        batch_text = self._build_batch_text(messages)

        result = await asyncio.to_thread(
            self._analyzer.analyze_batch, batch_text, len(messages)
        )

        self._stats.analyzed += len(messages)

        if not result.success:
            logger.warning(f"分析失败: {result.error_message}")
            return

        valuable = [i for i in result.items if i.get('impact_magnitude', 0) >= self.IMPACT_THRESHOLD]
        self._stats.valuable += len(valuable)

        logger.info(f"分析完成: {len(messages)} 条 → {len(valuable)} 条有价值")

        if valuable:
            self._storage.save_batch(valuable)

            notification = self._format_notification(valuable, len(messages))
            if await self._push(notification):
                self._stats.pushed += 1

    def _build_batch_text(self, messages: List[QueuedMessage]) -> str:
        lines = []
        for i, msg in enumerate(messages, 1):
            t = msg.timestamp.strftime('%H:%M')
            text = msg.text[:200] + ('...' if len(msg.text) > 200 else '')
            lines.append(f"[{i}] [{t}] {msg.channel_title}: {text}")
        return '\n\n'.join(lines)

    def _format_notification(self, items: List[Dict], total: int) -> str:
        # 按影响程度从大到小排序
        items = sorted(items, key=lambda x: x.get('impact_magnitude', 0), reverse=True)

        bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')

        lines = [
            f"## 📊 时政经济情报",
            f"",
            f"**时间**: {bj_time}",
            f"**分析**: {total} 条 → 有价值: {len(items)} 条",
            f"",
            "---",
            "",
        ]

        for item in items:
            emoji = {'利好': '🔴', '利空': '🟢'}.get(item.get('impact_direction', ''), '⚪')
            mag = item.get('impact_magnitude', 0)
            summary = item.get('summary', '')
            sectors = item.get('affected_sectors', [])

            lines.append(f"### {emoji} {summary}")
            lines.append(f"- **影响程度**: {'█' * mag}{'░' * (10-mag)} {mag}/10")
            lines.append(f"- **影响方向**: {item.get('impact_direction', '中性')}")
            if sectors:
                lines.append(f"- **相关板块**: {', '.join(sectors[:5])}")

            if item.get('action_suggestion'):
                lines.append(f"- **建议**: {item['action_suggestion']}")

            lines.append("")

        return '\n'.join(lines)

    async def _push(self, content: str) -> bool:
        try:
            if len(content) > 3800:
                content = content[:3800] + "\n...(已截断)"

            if self._notifier.is_available():
                return self._notifier.send_to_wechat(content)
            return False
        except Exception as e:
            logger.error(f"推送失败: {e}")
            return False


async def run_monitor(batch_interval: int = 5, debug: bool = False):
    """运行监听器"""
    config = get_config()

    if not config.telegram_enabled:
        logger.warning("Telegram 未启用")
        return

    if not config.telegram_channels:
        logger.error("未配置频道")
        return

    monitor = Monitor(batch_interval=batch_interval, debug=debug)

    if not await monitor.start():
        logger.error("启动失败")
        return

    try:
        await monitor.run()
    except KeyboardInterrupt:
        pass
    finally:
        await monitor.stop()
