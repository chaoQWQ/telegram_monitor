# -*- coding: utf-8 -*-
"""
趋势热点更新器 - 负责自动感知当前热点人物和事件
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from config import get_config

logger = logging.getLogger(__name__)

class TrendUpdater:
    PROMPT_TEMPLATE = """
    你是一个全球金融情报专家。今天是 {date}。
    请基于**当前最新**的全球时政经济局势，列出需要重点监控的关键词。

    请识别以下三类热点（每类提取 3-8 个最核心的词）：
    1. **关键人物 (HIGH)**：对市场有巨大影响力的**现任**政治/经济领袖（如现任美国总统、美联储主席、科技巨头CEO）。如果某人已下台或去世，请排除。
    2. **地缘热点 (HIGH)**：**当前正在进行**的、可能影响供应链或避险情绪的冲突/事件/地点。
    3. **热门概念 (MEDIUM)**：**近期**市场炒作的科技或经济概念（如 Low-Altitude Economy, AI Agent 等）。

    请严格以 JSON 格式输出，格式如下：
    {{
        "HIGH": {{
            "关键人物": ["名字1", "名字2"],
            "地缘热点": ["地名1", "事件名1"]
        }},
        "MEDIUM": {{
            "热门概念": ["概念1", "概念2"]
        }}
    }}
    """

    def __init__(self, data_dir: str = "./data"):
        self._data_dir = Path(data_dir)
        self._output_file = self._data_dir / "dynamic_keywords.json"
        self._config = get_config()

    def update(self) -> bool:
        """调用 AI 更新热词库"""
        if not self._config.gemini_api_key:
            logger.warning("未配置 API Key，无法更新热词")
            return False

        try:
            # 延迟导入以避免循环依赖
            from google import genai

            client = genai.Client(api_key=self._config.gemini_api_key)
            prompt = self.PROMPT_TEMPLATE.format(date=datetime.now().strftime("%Y-%m-%d"))

            logger.info("正在分析当前全球热点趋势...")

            response = client.models.generate_content(
                model=self._config.gemini_model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            )

            if response.text:
                try:
                    data = json.loads(response.text)
                    self._save(data)
                    return True
                except json.JSONDecodeError:
                    # 尝试清理 markdown 标记
                    clean_text = response.text.replace("```json", "").replace("```", "")
                    data = json.loads(clean_text)
                    self._save(data)
                    return True

            return False

        except Exception as e:
            logger.error(f"热词更新失败: {e}")
            return False

    def _save(self, data: Dict[str, Any]):
        """保存到文件"""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # 记录日志
        high_people = data.get("HIGH", {}).get("关键人物", [])
        logger.info(f"动态热词库已更新，当前关注: {', '.join(high_people[:5])} 等")
