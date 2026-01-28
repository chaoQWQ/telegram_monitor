# -*- coding: utf-8 -*-
"""
Telegram 客户端封装
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, List, Optional, Awaitable

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Message

from config import get_config

logger = logging.getLogger(__name__)


class TelegramClientWrapper:
    """Telegram 客户端封装"""

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None,
        session_string: Optional[str] = None,
        session_dir: str = "./data/telegram"
    ):
        config = get_config()

        self._api_id = api_id or config.telegram_api_id
        self._api_hash = api_hash or config.telegram_api_hash
        self._phone = phone or config.telegram_phone
        self._session_string = session_string or config.telegram_session

        if not self._api_id or not self._api_hash:
            raise ValueError(
                "Telegram API 凭证未配置。请在 .env 中设置 TELEGRAM_API_ID 和 TELEGRAM_API_HASH"
            )

        # 选择 session 类型
        if self._session_string:
            session = StringSession(self._session_string)
            logger.info("使用 StringSession 模式")
        else:
            session_path = Path(session_dir)
            session_path.mkdir(parents=True, exist_ok=True)
            session = str(session_path / "telegram_monitor")
            logger.info(f"使用文件 Session 模式: {session}.session")

        self._client = TelegramClient(
            session,
            self._api_id,
            self._api_hash,
            system_version="4.16.30-vxCUSTOM"
        )

        self._running = False
        self._subscribed_channels: List[int] = []

        logger.info("Telegram 客户端初始化完成")

    async def start(self) -> bool:
        """启动客户端"""
        try:
            logger.info("正在连接 Telegram...")

            if self._session_string:
                await self._client.connect()
                if not await self._client.is_user_authorized():
                    logger.error("StringSession 无效或已过期")
                    return False
            else:
                await self._client.start(phone=self._phone)

            me = await self._client.get_me()
            logger.info(f"Telegram 登录成功: {me.first_name} (@{me.username})")

            self._running = True
            return True

        except Exception as e:
            logger.error(f"Telegram 连接失败: {e}")
            return False

    async def subscribe_channels(
        self,
        channel_ids: List[int],
        message_callback: Callable[[Message, Channel], Awaitable[None]]
    ) -> int:
        """订阅频道"""
        if not self._running:
            return 0

        subscribed = 0
        valid_channels = []

        for channel_id in channel_ids:
            try:
                entity = await self._client.get_entity(channel_id)
                if isinstance(entity, Channel):
                    valid_channels.append(channel_id)
                    subscribed += 1
                    logger.info(f"已订阅频道: {entity.title} ({channel_id})")
            except Exception as e:
                logger.warning(f"无法订阅频道 {channel_id}: {e}")

        if not valid_channels:
            return 0

        @self._client.on(events.NewMessage(chats=valid_channels))
        async def handler(event):
            try:
                message = event.message
                chat = await event.get_chat()
                logger.info(f"[收到消息] {chat.title}: {message.text[:50] if message.text else '(无文本)'}...")
                await message_callback(message, chat)
            except Exception as e:
                logger.error(f"处理消息错误: {e}")

        self._subscribed_channels = valid_channels
        return subscribed

    async def run_forever(self):
        """持续运行"""
        if not self._running:
            return

        logger.info("开始监听消息...")

        try:
            await self._client.run_until_disconnected()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """停止"""
        if self._running:
            self._running = False
            await self._client.disconnect()
            logger.info("Telegram 客户端已断开")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscribed_channels(self) -> List[int]:
        return self._subscribed_channels.copy()
