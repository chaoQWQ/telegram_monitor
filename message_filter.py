# -*- coding: utf-8 -*-
"""
消息过滤器
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Dict, Any

from config import get_config

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

    URL_PATTERN = re.compile(r'https?://\S+')

    def __init__(self, data_dir: str = "./data", min_length: int = 10, max_url_count: int = 3):
        self._config = get_config()
        self._filter_mode = self._config.filter_mode
        self._data_dir = Path(data_dir)
        self._min_length = min_length
        self._max_url_count = max_url_count

        # 关键词映射: keyword -> category
        self._high_keywords: Dict[str, str] = {}
        self._medium_keywords: Dict[str, str] = {}
        self._exclude_keywords: Set[str] = set()

        self.reload()
        logger.info(f"过滤器模式: {self._filter_mode}")

    def reload(self):
        """重新加载关键词库"""
        self._high_keywords.clear()
        self._medium_keywords.clear()
        self._exclude_keywords.clear()

        # 1. 加载静态基准库
        self._load_file("base_keywords.json")

        # 2. 加载动态热词库
        self._load_file("dynamic_keywords.json")

        logger.info(f"过滤器加载完成: 高影响词 {len(self._high_keywords)}个, 中等词 {len(self._medium_keywords)}个, 排除词 {len(self._exclude_keywords)}个")

    def _load_file(self, filename: str):
        """加载单个 JSON 配置文件"""
        path = self._data_dir / filename
        if not path.exists():
            logger.warning(f"配置文件不存在: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 加载 HIGH
            for category, keywords in data.get("HIGH", {}).items():
                for kw in keywords:
                    if kw:
                        self._high_keywords[kw] = category

            # 加载 MEDIUM
            for category, keywords in data.get("MEDIUM", {}).items():
                for kw in keywords:
                    if kw:
                        self._medium_keywords[kw] = category

            # 加载 EXCLUDED
            for kw in data.get("EXCLUDED", []):
                if kw:
                    self._exclude_keywords.add(kw)

        except Exception as e:
            logger.error(f"加载配置文件 {filename} 失败: {e}")

    def filter_message(self, text: str) -> FilterResult:
        """过滤消息"""
        if not text or len(text.strip()) < self._min_length:
            return FilterResult(ImpactLevel.EXCLUDED, reason="消息过短")

        urls = self.URL_PATTERN.findall(text)
        if len(urls) > self._max_url_count:
            return FilterResult(ImpactLevel.EXCLUDED, reason="URL过多")

        # 检查排除词
        for keyword in self._exclude_keywords:
            if keyword in text:
                return FilterResult(ImpactLevel.EXCLUDED, matched_keywords=[keyword], reason=f"排除: {keyword}")

        # AI 纯净模式: 仅排除广告，其余全量分析
        if self._filter_mode == 'ai_only':
            return FilterResult(ImpactLevel.LOW, reason="AI Only: 全量分析")

        # 检查高影响
        high_matches = []
        high_category = ""
        for keyword, category in self._high_keywords.items():
            if keyword in text:
                high_matches.append(keyword)
                if not high_category:
                    high_category = category

        if high_matches:
            return FilterResult(ImpactLevel.HIGH, high_matches, high_category, f"高影响: {high_matches[:3]}")

        # 检查中等影响
        medium_matches = []
        medium_category = ""
        for keyword, category in self._medium_keywords.items():
            if keyword in text:
                medium_matches.append(keyword)
                if not medium_category:
                    medium_category = category

        if medium_matches:
            return FilterResult(ImpactLevel.MEDIUM, medium_matches, medium_category, f"中等: {medium_matches[:3]}")

        return FilterResult(ImpactLevel.LOW, reason="无匹配")
