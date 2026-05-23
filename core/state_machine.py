# -*- coding: utf-8 -*-
"""
角色动作状态机
管理 Live2D 模型的 Idle / TapHead / TapBody / Greeting / Thinking 等状态
"""
import random
from enum import Enum, auto
from typing import Callable, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class CharacterState(Enum):
    """角色状态枚举"""
    IDLE = auto()       # 空闲
    GREETING = auto()   # 打招呼（启动时）
    THINKING = auto()   # 思考（等待 API 回复）
    TALKING = auto()    # 说话（TTS 播放中）
    TAP_HEAD = auto()   # 被摸头
    TAP_BODY = auto()   # 被点击身体
    HAPPY = auto()      # 积极情感
    SAD = auto()        # 消极情感


class StateMachine:
    """
    Live2D 角色状态机
    - 优先级：交互(Tap/Thinking/Talking) > 情感(Happy/Sad) > Idle
    - 非循环 motion 播放完毕后自动回到 Idle
    """

    # 各状态对应的动作文件映射（MotionGroup -> motion_no）
    # Phase 1 仅实现基础状态，Phase 2 扩展 Talking 等
    _STATE_MOTIONS: dict[CharacterState, list[tuple[str, int]]] = {
        CharacterState.IDLE: [
            ("idle", 0), ("idle", 1), ("idle", 2),
        ],
        CharacterState.GREETING: [
            ("shake", 0),
        ],
        CharacterState.THINKING: [
            ("idle", 1),
        ],
        CharacterState.TALKING: [
            ("idle", 0),
        ],
        CharacterState.TAP_HEAD: [
            ("flick_head", 0),
        ],
        CharacterState.TAP_BODY: [
            ("tap_body", 0), ("tap_body", 1), ("tap_body", 2),
        ],
        CharacterState.HAPPY: [
            ("pinch_out", 0),
        ],
        CharacterState.SAD: [
            ("pinch_in", 0),
        ],
    }

    # 状态优先级，数值越大优先级越高
    _PRIORITY_MAP: dict[CharacterState, int] = {
        CharacterState.TAP_HEAD: 30,
        CharacterState.TAP_BODY: 30,
        CharacterState.THINKING: 20,
        CharacterState.TALKING: 20,
        CharacterState.HAPPY: 15,
        CharacterState.SAD: 15,
        CharacterState.GREETING: 10,
        CharacterState.IDLE: 5,
    }

    def __init__(
        self,
        motion_callback: Optional[Callable[[str, int, int], None]] = None,
        state_change_callback: Optional[Callable[[CharacterState], None]] = None
    ):
        """
        初始化状态机
        :param motion_callback: 状态变更时触发的动作回调，签名 (group, no, priority)
        :param state_change_callback: 状态变更通知回调，签名 (new_state,)
        """
        self._current_state = CharacterState.IDLE
        self._previous_state: Optional[CharacterState] = None
        self._motion_callback = motion_callback
        self._state_change_callback = state_change_callback
        self._idle_timer = 0.0  # 用于空闲时随机切换动作
        logger.info("状态机初始化完成")

    @property
    def current_state(self) -> CharacterState:
        """获取当前状态"""
        return self._current_state

    @property
    def motion_callback(self) -> Optional[Callable[[str, int, int], None]]:
        """获取动作回调"""
        return self._motion_callback

    @motion_callback.setter
    def motion_callback(self, callback: Optional[Callable[[str, int, int], None]]) -> None:
        """设置动作回调"""
        self._motion_callback = callback

    @property
    def state_change_callback(self) -> Optional[Callable[[CharacterState], None]]:
        """获取状态变更回调"""
        return self._state_change_callback

    @state_change_callback.setter
    def state_change_callback(self, callback: Optional[Callable[[CharacterState], None]]) -> None:
        """设置状态变更回调"""
        self._state_change_callback = callback

    def _get_priority(self, state: CharacterState) -> int:
        """获取状态优先级"""
        return self._PRIORITY_MAP.get(state, 0)

    def _pick_motion(self, state: CharacterState) -> tuple[str, int]:
        """从状态中随机选取一个动作"""
        motions = self._STATE_MOTIONS.get(state, [("idle", 0)])
        return random.choice(motions)

    def _notify(self, state: CharacterState) -> None:
        """通知状态变更并触发动作"""
        group, no = self._pick_motion(state)
        priority = self._get_priority(state)
        logger.debug(f"状态变更: {self._previous_state} -> {state}, motion=({group}, {no}), priority={priority}")

        if self._motion_callback:
            try:
                self._motion_callback(group, no, priority)
            except Exception as e:
                logger.error(f"动作回调执行失败: {e}")

        if self._state_change_callback:
            try:
                self._state_change_callback(state)
            except Exception as e:
                logger.error(f"状态变更回调执行失败: {e}")

    def transit(self, new_state: CharacterState) -> bool:
        """
        尝试切换到新状态（优先级判断）
        :param new_state: 目标状态
        :return: 是否成功切换
        """
        # 如果当前状态优先级更高，则不允许低优先级打断
        if self._get_priority(self._current_state) > self._get_priority(new_state):
            return False

        self._previous_state = self._current_state
        self._current_state = new_state
        self._notify(new_state)
        return True

    def force_transit(self, new_state: CharacterState) -> None:
        """
        强制切换到新状态（无视优先级）
        用于非循环动作播放完毕后的恢复，或特殊场景
        """
        self._previous_state = self._current_state
        self._current_state = new_state
        self._notify(new_state)

    def return_to_idle(self) -> None:
        """
        恢复到空闲状态
        通常由非循环 motion 播放完毕回调触发
        """
        if self._current_state != CharacterState.IDLE:
            self._previous_state = self._current_state
            self._current_state = CharacterState.IDLE
            self._notify(CharacterState.IDLE)

    def update(self, delta_time: float) -> None:
        """
        每帧更新（目前仅用于空闲动作轮播）
        :param delta_time: 距离上一帧的时间（秒）
        """
        if self._current_state == CharacterState.IDLE:
            self._idle_timer += delta_time
            # 每 5~8 秒随机切换一次 idle 动作，避免单调
            if self._idle_timer >= random.uniform(5.0, 8.0):
                self._idle_timer = 0.0
                self._notify(CharacterState.IDLE)
