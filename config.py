# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class Config:
    """系统配置"""

    # Telegram 配置
    telegram_enabled: bool = False
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_phone: Optional[str] = None
    telegram_session: Optional[str] = None
    telegram_channels: List[int] = field(default_factory=list)

    # 过滤模式: standard (关键词分级) / ai_only (仅排除，其余全部分析)
    filter_mode: str = "standard"

    # 批量分析间隔（分钟）
    batch_interval: int = 60

    # Gemini AI 配置
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_request_delay: float = 2.0

    # 邮件配置
    email_sender: Optional[str] = None
    email_password: Optional[str] = None
    email_receiver: Optional[str] = None
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465

    # 企业微信
    wechat_webhook_url: Optional[str] = None

    # 日志
    log_level: str = "INFO"
    debug: bool = False

    # 数据目录
    data_dir: str = "./data"
    log_dir: str = "./logs"

    _instance: Optional['Config'] = None

    @classmethod
    def get_instance(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = cls._load_from_env()
        return cls._instance

    @classmethod
    def _load_from_env(cls) -> 'Config':
        # 加载 .env 文件
        env_path = Path(__file__).parent / '.env'
        load_dotenv(dotenv_path=env_path)

        # 解析频道列表
        channels_str = os.getenv('TELEGRAM_CHANNELS', '')
        channels = []
        for ch in channels_str.split(','):
            ch = ch.strip()
            if ch:
                try:
                    channels.append(int(ch))
                except ValueError:
                    pass

        # 解析 API ID
        api_id = None
        api_id_str = os.getenv('TELEGRAM_API_ID', '')
        if api_id_str:
            try:
                api_id = int(api_id_str)
            except ValueError:
                pass

        return cls(
            telegram_enabled=os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true',
            telegram_api_id=api_id,
            telegram_api_hash=os.getenv('TELEGRAM_API_HASH'),
            telegram_phone=os.getenv('TELEGRAM_PHONE'),
            telegram_session=os.getenv('TELEGRAM_SESSION'),
            telegram_channels=channels,
            filter_mode=os.getenv('FILTER_MODE', 'standard'),
            batch_interval=int(os.getenv('BATCH_INTERVAL', '60')),
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            gemini_model=os.getenv('GEMINI_MODEL', 'gemini-2.0-flash'),
            gemini_request_delay=float(os.getenv('GEMINI_REQUEST_DELAY', '2.0')),
            email_sender=os.getenv('EMAIL_SENDER'),
            email_password=os.getenv('EMAIL_PASSWORD'),
            email_receiver=os.getenv('EMAIL_RECEIVER'),
            smtp_server=os.getenv('SMTP_SERVER', 'smtp.qq.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '465')),
            wechat_webhook_url=os.getenv('WECHAT_WEBHOOK_URL'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
        )

    def validate(self) -> List[str]:
        """验证配置"""
        warnings = []

        if not self.telegram_api_id or not self.telegram_api_hash:
            warnings.append("未配置 Telegram API 凭证")

        if not self.telegram_session and not self.telegram_phone:
            warnings.append("未配置 TELEGRAM_SESSION 或 TELEGRAM_PHONE")

        if not self.telegram_channels:
            warnings.append("未配置监听频道 TELEGRAM_CHANNELS")

        if not self.gemini_api_key:
            warnings.append("未配置 GEMINI_API_KEY，AI 分析将不可用")

        has_notification = bool(self.wechat_webhook_url) or bool(
            self.email_sender and self.email_password and self.email_receiver
        )
        if not has_notification:
            warnings.append("未配置任何通知渠道（邮件/企业微信）")

        return warnings


def get_config() -> Config:
    """获取配置实例"""
    return Config.get_instance()
