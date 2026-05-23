# -*- coding: utf-8 -*-
"""
Kimi Claw API 提供者（Phase 1 占位实现）
目前仅返回模拟回复，Phase 3 接入真实 HTTP 请求
"""
import random
import time
from typing import Optional

from ai.base_provider import BaseAIProvider, ChatResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class KimiClawProvider(BaseAIProvider):
    """
    Kimi Claw API 封装
    请求体：{"instance_id": "...", "message": "...", "include_memory_context": true}
    响应体：choices[0].message.content
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        instance_id: Optional[str] = None,
        base_url: str = "https://api.kimi.com/v1/claw/chat"
    ):
        super().__init__()
        self.api_key = api_key or ""
        self.instance_id = instance_id or ""
        self.base_url = base_url
        self._offline_mode = True  # Phase 1 默认离线，不发起真实请求
        logger.info("KimiClawProvider 初始化完成（当前为离线占位模式）")

    def validate_config(self) -> bool:
        """
        验证 API 配置是否完整
        :return: api_key 与 instance_id 均非空时返回 True
        """
        return bool(self.api_key and self.instance_id)

    def chat(self, message: str, history: list[dict]) -> ChatResponse:
        """
        发送消息并获取 AI 回复
        Phase 1 为占位实现，随机返回模拟回复；Phase 3 接入真实 HTTP
        :param message: 用户输入
        :param history: 历史记录
        :return: ChatResponse
        """
        if not self._offline_mode and self.validate_config():
            # Phase 3 真实请求逻辑占位
            pass

        # Phase 1：模拟延迟与占位回复
        time.sleep(0.5)
        replies = [
            ("你好呀~ 葵酱今天也很开心能陪你！", "positive"),
            ("这个问题有点难，让我想想...", "neutral"),
            ("抱歉，我不太明白你的意思，可以再详细说说吗？", "negative"),
            ("哈哈，你真有趣~", "positive"),
            ("嗯嗯，我记住了！", "neutral"),
        ]
        text, sentiment = random.choice(replies)
        logger.info(f"[占位回复] {text} (sentiment={sentiment})")
        return ChatResponse(text=text, sentiment=sentiment)
