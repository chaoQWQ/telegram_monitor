# -*- coding: utf-8 -*-
"""
消息存储层
"""

import json
import logging
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, Date, Boolean, desc
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class TelegramMessage(Base):
    """消息记录"""
    __tablename__ = 'telegram_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, index=True)
    channel_title = Column(String(200))
    message_text = Column(Text)
    received_at = Column(DateTime, index=True)
    summary = Column(String(500))
    impact_direction = Column(String(20))
    impact_magnitude = Column(Integer, default=0)
    affected_sectors = Column(Text)
    action_suggestion = Column(String(500))
    analyzed_at = Column(DateTime)
    report_date = Column(Date, index=True)
    is_pushed = Column(Boolean, default=False)
    is_reported = Column(Boolean, default=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'channel_title': self.channel_title,
            'message_text': self.message_text[:200] if self.message_text else '',
            'summary': self.summary,
            'impact_direction': self.impact_direction,
            'impact_magnitude': self.impact_magnitude,
            'affected_sectors': json.loads(self.affected_sectors) if self.affected_sectors else [],
            'action_suggestion': self.action_suggestion,
            'report_date': self.report_date.isoformat() if self.report_date else None,
        }


class Storage:
    """消息存储管理"""

    def __init__(self, db_path: str = "./data/telegram_messages.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)
        logger.info(f"存储初始化完成: {db_path}")

    def save_batch(self, items: List[Dict[str, Any]]) -> int:
        """批量保存分析结果"""
        session = self._Session()
        saved = 0

        try:
            now = datetime.now(timezone(timedelta(hours=8)))
            report_date = now.date()

            for item in items:
                record = TelegramMessage(
                    channel_id=0,
                    channel_title='',
                    message_text=item.get('original_text', ''),
                    received_at=now,
                    summary=item.get('summary', ''),
                    impact_direction=item.get('impact_direction', '中性'),
                    impact_magnitude=item.get('impact_magnitude', 0),
                    affected_sectors=json.dumps(item.get('affected_sectors', []), ensure_ascii=False),
                    action_suggestion=item.get('action_suggestion', ''),
                    analyzed_at=now,
                    report_date=report_date,
                    is_pushed=True,
                    is_reported=False
                )
                session.add(record)
                saved += 1

            session.commit()
            logger.info(f"保存 {saved} 条分析结果")
            return saved

        except Exception as e:
            session.rollback()
            logger.error(f"保存失败: {e}")
            return 0
        finally:
            session.close()

    def get_daily_messages(self, target_date: date, min_impact: int = 4) -> List[Dict[str, Any]]:
        """获取指定日期的消息"""
        session = self._Session()
        try:
            messages = session.query(TelegramMessage).filter(
                TelegramMessage.report_date == target_date,
                TelegramMessage.impact_magnitude >= min_impact
            ).order_by(desc(TelegramMessage.impact_magnitude)).all()

            return [msg.to_dict() for msg in messages]
        finally:
            session.close()

    def get_daily_stats(self, target_date: date) -> Dict[str, Any]:
        """获取每日统计"""
        session = self._Session()
        try:
            messages = session.query(TelegramMessage).filter(
                TelegramMessage.report_date == target_date
            ).all()

            if not messages:
                return {'date': target_date.isoformat(), 'total_count': 0, 'valuable_count': 0,
                        'bullish_count': 0, 'bearish_count': 0, 'sectors': {}}

            valuable = [m for m in messages if m.impact_magnitude >= 4]
            bullish = [m for m in valuable if m.impact_direction == '利好']
            bearish = [m for m in valuable if m.impact_direction == '利空']

            sector_counts = {}
            for msg in valuable:
                sectors = json.loads(msg.affected_sectors) if msg.affected_sectors else []
                for s in sectors:
                    sector_counts[s] = sector_counts.get(s, 0) + 1

            return {
                'date': target_date.isoformat(),
                'total_count': len(messages),
                'valuable_count': len(valuable),
                'bullish_count': len(bullish),
                'bearish_count': len(bearish),
                'sectors': dict(sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            }
        finally:
            session.close()

    def mark_reported(self, ids: List[int]):
        """标记为已报告"""
        session = self._Session()
        try:
            session.query(TelegramMessage).filter(
                TelegramMessage.id.in_(ids)
            ).update({TelegramMessage.is_reported: True}, synchronize_session=False)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"标记失败: {e}")
        finally:
            session.close()
