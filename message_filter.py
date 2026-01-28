# -*- coding: utf-8 -*-
"""
消息过滤器
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class ImpactLevel(Enum):
    """消息影响级别"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EXCLUDED = "excluded"


@dataclass
class FilterResult:
    """过滤结果"""
    impact_level: ImpactLevel
    matched_keywords: List[str] = field(default_factory=list)
    category: str = ""
    reason: str = ""


class MessageFilter:
    """消息过滤器"""

    # 高影响关键词
    HIGH_IMPACT_KEYWORDS = {
        "货币政策": ["央行", "降准", "降息", "加息", "LPR", "MLF", "逆回购", "货币政策"],
        "地缘政治": ["制裁", "关税", "贸易战", "出口管制", "实体清单", "战争", "冲突"],
        "重大事件": ["熔断", "崩盘", "暴跌", "暴涨", "黑天鹅", "救市", "国家队"],
        "关键人物": ["特朗普", "Trump", "拜登", "马斯克", "Musk", "鲍威尔", "Powell"],
    }

    # 中等影响关键词
    MEDIUM_IMPACT_KEYWORDS = {
        "宏观数据": ["GDP", "CPI", "PPI", "PMI", "失业率", "通胀"],
        "国际市场": ["美股", "纳斯达克", "道琼斯", "港股", "恒生", "A50"],
        "大宗商品": ["原油", "黄金", "白银", "铜", "铁矿石", "天然气"],
        "行业政策": ["新能源", "光伏", "芯片", "半导体", "AI", "人工智能", "医药"],
    }

    # 排除关键词
    EXCLUDE_KEYWORDS = [
        "广告", "推广", "代理", "招商", "VIP", "会员",
        "加群", "私聊", "微信", "QQ群",
        "稳赚", "包赚", "无风险", "内幕", "荐股",
    ]

    URL_PATTERN = re.compile(r'https?://\S+')

    def __init__(self, min_length: int = 10, max_url_count: int = 3):
        self._min_length = min_length
        self._max_url_count = max_url_count

        self._all_high: Set[str] = set()
        for keywords in self.HIGH_IMPACT_KEYWORDS.values():
            self._all_high.update(keywords)

        self._all_medium: Set[str] = set()
        for keywords in self.MEDIUM_IMPACT_KEYWORDS.values():
            self._all_medium.update(keywords)

        logger.info(f"过滤器初始化: 高影响 {len(self._all_high)}个, 中等 {len(self._all_medium)}个")

    def filter_message(self, text: str) -> FilterResult:
        """过滤消息"""
        if not text or len(text.strip()) < self._min_length:
            return FilterResult(ImpactLevel.EXCLUDED, reason="消息过短")

        urls = self.URL_PATTERN.findall(text)
        if len(urls) > self._max_url_count:
            return FilterResult(ImpactLevel.EXCLUDED, reason="URL过多")

        for keyword in self.EXCLUDE_KEYWORDS:
            if keyword in text:
                return FilterResult(ImpactLevel.EXCLUDED, matched_keywords=[keyword], reason=f"排除: {keyword}")

        # 高影响
        high_matches = []
        high_category = ""
        for category, keywords in self.HIGH_IMPACT_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    high_matches.append(kw)
                    if not high_category:
                        high_category = category

        if high_matches:
            return FilterResult(ImpactLevel.HIGH, high_matches, high_category, f"高影响: {high_matches[:3]}")

        # 中等影响
        medium_matches = []
        medium_category = ""
        for category, keywords in self.MEDIUM_IMPACT_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    medium_matches.append(kw)
                    if not medium_category:
                        medium_category = category

        if medium_matches:
            return FilterResult(ImpactLevel.MEDIUM, medium_matches, medium_category, f"中等: {medium_matches[:3]}")

        return FilterResult(ImpactLevel.LOW, reason="无匹配")
