# -*- coding: utf-8 -*-
"""
AI Provider 抽象基类
定义所有 AI 后端必须实现的接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatResponse:
    """AI 回复数据结构"""
    text: str
    sentiment: str  # "positive" | "neutral" | "negative"


class BaseAIProvider(ABC):
    """
    AI 对话提供者抽象基类
    所有具体 AI 后端（Kimi、OpenAI 等）均需继承此类
    """

    @abstractmethod
    def chat(self, message: str, history: list[dict]) -> ChatResponse:
        """
        发送消息并获取 AI 回复
        :param message: 用户输入文本
        :param history: 历史对话记录，格式 [{"role": "user"/"assistant", "content": "..."}]
        :return: 包含回复文本和情感标签的 ChatResponse
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        验证当前配置是否可用
        :return: 配置有效返回 True，否则返回 False
        """
        pass
