# -*- coding: utf-8 -*-
"""
通知服务模块
"""

import logging
import smtplib
import markdown
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from typing import Optional

import requests

from config import get_config

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务"""

    def __init__(self):
        config = get_config()
        self._webhook_url = config.wechat_webhook_url
        self._email_sender = config.email_sender
        self._email_password = config.email_password
        self._email_receiver = config.email_receiver
        self._smtp_server = config.smtp_server
        self._smtp_port = config.smtp_port

        if not self.is_available():
            logger.warning("通知服务未配置（邮件/企业微信）")

    def is_available(self) -> bool:
        """检查是否可用"""
        email_ready = bool(
            self._email_sender and self._email_password and self._email_receiver
        )
        return bool(self._webhook_url) or email_ready

    def send_to_wechat(self, content: str) -> bool:
        """推送消息（支持企业微信和邮件）"""
        if not self.is_available():
            logger.warning("通知服务未配置，跳过推送")
            return False

        if len(content) > 4000:
            content = content[:3950] + "\n\n...(内容过长已截断)"

        success = False

        # 尝试企业微信
        if self._webhook_url:
            try:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {"content": content}
                }
                response = requests.post(self._webhook_url, json=payload, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('errcode') == 0:
                        logger.info("企业微信推送成功")
                        success = True
                    else:
                        logger.error(f"企业微信返回错误: {result}")
            except Exception as e:
                logger.error(f"企业微信推送失败: {e}")

        # 尝试邮件
        if self._email_sender and self._email_receiver:
            try:
                if self._send_email(content):
                    success = True
            except Exception as e:
                logger.error(f"邮件推送失败: {e}")

        return success

    def _send_email(self, content: str) -> bool:
        """发送邮件"""
        bj_time = datetime.now(timezone(timedelta(hours=8)))
        subject = f"时政经济情报 {bj_time.strftime('%Y-%m-%d %H:%M')}"

        # Markdown 转 HTML，替换利好/利空为带颜色的标签
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        # 利好用红色（A股红涨），利空用绿色（A股绿跌）
        html_content = html_content.replace('🟢', '<span class="bullish">🟢 利好</span>')
        html_content = html_content.replace('🔴', '<span class="bearish">🔴 利空</span>')
        html_content = html_content.replace('⚪', '<span class="neutral">⚪ 中性</span>')

        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }}
                h2, h3 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f5f5f5; }}
                hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
                code {{ background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
                .bullish {{ color: #e53935; font-weight: bold; }}
                .bearish {{ color: #43a047; font-weight: bold; }}
                .neutral {{ color: #757575; }}
            </style>
        </head>
        <body>{html_content}</body>
        </html>
        """

        msg = MIMEText(html_body, 'html', 'utf-8')
        msg['From'] = formataddr(("时政经济助手", self._email_sender))
        msg['To'] = formataddr(("投资者", self._email_receiver))
        msg['Subject'] = Header(subject, 'utf-8')
        server = smtplib.SMTP_SSL(self._smtp_server, self._smtp_port)
        server.login(self._email_sender, self._email_password)
        server.sendmail(self._email_sender, [self._email_receiver], msg.as_string())
        server.quit()

        logger.info(f"邮件发送成功: {self._email_receiver}")
        return True
