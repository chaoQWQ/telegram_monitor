# -*- coding: utf-8 -*-
"""
每日早报生成器
"""

import logging
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from config import get_config
from notification import NotificationService
from storage import Storage
from analyzer import NewsAnalyzer

logger = logging.getLogger(__name__)


class DailyReport:
    """每日早报生成器"""

    def __init__(self):
        self._storage = Storage()
        self._analyzer = NewsAnalyzer()
        self._notifier = NotificationService()

    def generate(self, target_date: Optional[date] = None) -> Optional[str]:
        """生成早报"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        logger.info(f"生成 {target_date} 早报...")

        messages = self._storage.get_daily_messages(target_date, min_impact=4)

        if not messages:
            logger.warning(f"{target_date} 无有价值消息")
            return None

        stats = self._storage.get_daily_stats(target_date)

        # AI 分析
        messages_text = '\n'.join([
            f"{i}. [{m.get('impact_direction')}][{m.get('impact_magnitude')}] {m.get('summary')} | {', '.join(m.get('affected_sectors', [])[:3])}"
            for i, m in enumerate(messages[:20], 1)
        ])

        ai_analysis = self._analyzer.generate_daily_report(messages_text, stats)

        # 格式化
        report = self._format(target_date, messages, stats, ai_analysis)

        # 标记已报告
        ids = [m.get('id') for m in messages if m.get('id')]
        if ids:
            self._storage.mark_reported(ids)

        return report

    def _format(self, target_date, messages, stats, ai_analysis) -> str:
        bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M')
        sectors = stats.get('sectors', {})
        top_sectors = ' | '.join([f"{s}({c})" for s, c in list(sectors.items())[:5]]) or '无'

        lines = [
            f"## 📰 时政经济早报 | {target_date}",
            f"",
            f"**生成时间**: {bj_time}",
            "",
            "---",
            "",
            "### 📊 昨日概览",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 监听消息 | {stats.get('total_count', 0)} 条 |",
            f"| 有价值 | {stats.get('valuable_count', 0)} 条 |",
            f"| 利好/利空 | {stats.get('bullish_count', 0)}/{stats.get('bearish_count', 0)} |",
            f"| 热门板块 | {top_sectors} |",
            "",
            "---",
            "",
            "### 🤖 AI 分析",
            "",
            ai_analysis,
            "",
            "---",
            "",
            "### 📋 重要消息",
            "",
        ]

        high = [m for m in messages if m.get('impact_magnitude', 0) >= 7]
        medium = [m for m in messages if 4 <= m.get('impact_magnitude', 0) < 7]

        if high:
            lines.append("**🔴 高影响**")
            for m in high[:5]:
                emoji = '🟢' if m.get('impact_direction') == '利好' else '🔴' if m.get('impact_direction') == '利空' else '⚪'
                lines.append(f"- {emoji} {m.get('summary', '')}")
            lines.append("")

        if medium:
            lines.append("**🟡 中等影响**")
            for m in medium[:5]:
                emoji = '🟢' if m.get('impact_direction') == '利好' else '🔴' if m.get('impact_direction') == '利空' else '⚪'
                lines.append(f"- {emoji} {m.get('summary', '')}")

        return '\n'.join(lines)

    def send(self, report: str) -> bool:
        """发送早报"""
        if not report:
            return False

        if len(report) > 3800:
            report = report[:3800] + "\n...(已截断)"

        return self._notifier.send_to_wechat(report)

    def run(self, target_date: Optional[date] = None) -> bool:
        """生成并发送"""
        report = self.generate(target_date)
        if report:
            return self.send(report)
        return False


def run_daily_report(target_date: Optional[date] = None):
    """运行早报任务"""
    generator = DailyReport()
    if generator.run(target_date):
        logger.info("早报发送成功")
    else:
        logger.warning("早报未生成")
