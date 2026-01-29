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

    def _send_email(self, content: str, title: str = "时政经济情报") -> bool:
        """
        通过邮件推送消息

        Args:
            content: Markdown 内容 (将被转换为 HTML 发送)
            title: 邮件标题

        Returns:
            是否发送成功
        """
        if not (self._email_sender and self._email_password and self._email_receiver):
            return False

        # 提取标题
        lines = content.strip().split('\n')
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip()

        try:
            # Markdown 转 HTML
            html_body = markdown.markdown(
                content,
                extensions=['tables', 'fenced_code', 'nl2br']
            )

            # 邮件 CSS 样式 (适配 QQ 邮箱等主流客户端)
            css_style = """
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; }
                h1, h2, h3 { color: #2c3e50; margin-top: 24px; margin-bottom: 16px; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
                h1 { font-size: 24px; }
                h2 { font-size: 20px; }
                h3 { font-size: 18px; }
                p { margin-bottom: 16px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 16px; display: block; overflow-x: auto; }
                th, td { border: 1px solid #dfe2e5; padding: 6px 13px; }
                th { background-color: #f6f8fa; font-weight: 600; }
                tr:nth-child(2n) { background-color: #f6f8fa; }
                blockquote { border-left: 4px solid #dfe2e5; color: #6a737d; padding: 0 1em; margin: 0; background-color: #f9f9f9; }
                code { background-color: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-family: monospace; font-size: 85%; }
                pre { background-color: #f6f8fa; padding: 16px; overflow: auto; border-radius: 3px; }
                ul, ol { padding-left: 2em; }
                hr { height: 0.25em; padding: 0; margin: 24px 0; background-color: #e1e4e8; border: 0; }
                .footer { margin-top: 40px; font-size: 12px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }
            </style>
            """

            # 组合完整 HTML
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                {css_style}
            </head>
            <body>
                {html_body}
                <div class="footer">
                    <p>本邮件由 Telegram 时政经济监控系统 自动生成</p>
                </div>
            </body>
            </html>
            """

            # 构造邮件
            message = MIMEText(full_html, 'html', 'utf-8')

            # 显式使用 Header 编码中文昵称，避免客户端无法识别
            message['From'] = formataddr((Header("时政经济监控助手", 'utf-8').encode(), self._email_sender))
            message['To'] = formataddr((Header("投资者", 'utf-8').encode(), self._email_receiver))
            message['Subject'] = Header(title, 'utf-8')

            # 连接 SMTP 服务器
            if self._smtp_port == 465:
                server = smtplib.SMTP_SSL(self._smtp_server, self._smtp_port)
            else:
                server = smtplib.SMTP(self._smtp_server, self._smtp_port)
                server.starttls()

            server.login(self._email_sender, self._email_password)
            server.sendmail(self._email_sender, [self._email_receiver], message.as_string())
            server.quit()

            logger.info(f"邮件发送成功: {self._email_receiver}")
            return True

        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False
