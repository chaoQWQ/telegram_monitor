# -*- coding: utf-8 -*-
"""
AI 新闻分析器（使用新版 google-genai SDK）
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class BatchAnalysisResult:
    """批量分析结果"""
    items: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    valuable_count: int = 0
    raw_response: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class NewsAnalyzer:
    """新闻 AI 分析器"""

    SYSTEM_PROMPT = """你是一位专注于全球宏观分析的 A股 投资顾问。
分析新闻对 A股 市场的潜在影响。

评分标准（1-10）：
- 8-10: 重大政策/事件（降准降息、贸易战、制裁）
- 6-7: 行业重大消息、宏观数据超预期
- 4-5: 一般行业消息、国际市场联动
- 1-3: 轻微影响
- 0: 与 A股 无关"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_config().gemini_api_key
        self._client = None
        self._model_name = get_config().gemini_model

        if self._api_key:
            self._init_client()
        else:
            logger.warning("Gemini API Key 未配置")

    def _init_client(self):
        """初始化 Gemini 客户端"""
        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
            logger.info(f"Gemini 客户端初始化成功 (模型: {self._model_name})")

        except Exception as e:
            logger.error(f"Gemini 初始化失败: {e}")
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def analyze_batch(self, batch_text: str, message_count: int) -> BatchAnalysisResult:
        """批量分析消息"""
        if not self.is_available():
            return BatchAnalysisResult(success=False, error_message="AI 未配置")

        try:
            prompt = self._build_batch_prompt(batch_text, message_count)

            config = get_config()
            if config.gemini_request_delay > 0:
                time.sleep(config.gemini_request_delay)

            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config={
                    "temperature": 0.3,
                    "max_output_tokens": 4096,
                }
            )

            if response and response.text:
                return self._parse_response(response.text, message_count)
            else:
                return BatchAnalysisResult(success=False, error_message="空响应")

        except Exception as e:
            logger.error(f"批量分析失败: {e}")
            return BatchAnalysisResult(success=False, error_message=str(e))

    def _build_batch_prompt(self, batch_text: str, message_count: int) -> str:
        from datetime import datetime, timezone, timedelta
        bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')

        return f"""{self.SYSTEM_PROMPT}

## 批量消息分析

**时间**: {bj_time}
**消息数**: {message_count}

筛选出对 A股 有价值的消息（影响程度 >= 4）。

### 消息列表

{batch_text}

---

### 输出 JSON 格式

```json
{{
    "items": [
        {{
            "index": 1,
            "summary": "一句话总结（30字以内）",
            "impact_direction": "利好/利空/中性",
            "impact_magnitude": 1-10,
            "affected_sectors": ["板块1", "板块2"],
            "action_suggestion": "操作建议"
        }}
    ],
    "total_analyzed": {message_count},
    "valuable_count": 有价值数量
}}
```

只输出 JSON。如无有价值消息，items 返回空数组。"""

    def _parse_response(self, response_text: str, message_count: int) -> BatchAnalysisResult:
        try:
            cleaned = response_text
            if '```json' in cleaned:
                cleaned = cleaned.replace('```json', '').replace('```', '')
            elif '```' in cleaned:
                cleaned = cleaned.replace('```', '')

            json_start = cleaned.find('{')
            json_end = cleaned.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(cleaned[json_start:json_end])
                items = data.get('items', [])

                return BatchAnalysisResult(
                    items=items,
                    total_count=data.get('total_analyzed', message_count),
                    valuable_count=data.get('valuable_count', len(items)),
                    raw_response=response_text,
                    success=True
                )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON 解析失败: {e}")

        return BatchAnalysisResult(raw_response=response_text, success=False, error_message="解析失败")

    def generate_daily_report(self, messages_text: str, stats: Dict[str, Any]) -> str:
        """生成每日早报分析"""
        if not self.is_available():
            return "AI 分析不可用"

        prompt = f"""## 每日时政经济早报分析

### 昨日统计
- 总消息数: {stats.get('total_count', 0)}
- 有价值消息: {stats.get('valuable_count', 0)}
- 利好 / 利空: {stats.get('bullish_count', 0)} / {stats.get('bearish_count', 0)}
- 热门板块: {', '.join(list(stats.get('sectors', {}).keys())[:5])}

### 重要消息
{messages_text}

---

生成简洁早报：
1. **市场情绪**（一句话）
2. **三大核心事件**
3. **重点关注板块**（3-5个）
4. **风险提示**
5. **今日操作建议**

简洁直接，不要废话。"""

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config={"temperature": 0.4, "max_output_tokens": 1500}
            )
            return response.text if response and response.text else "分析失败"

        except Exception as e:
            logger.error(f"早报分析失败: {e}")
            return f"分析失败: {e}"
