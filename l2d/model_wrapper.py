# -*- coding: utf-8 -*-
"""
Live2D 模型封装层
对第三方 live2d-py 的 LAppModel 进行包装，提供异常安全的方法
"""
import sys
import os
from typing import Optional

from l2d import live2d_v2, MotionPriority
from utils.logger import get_logger

logger = get_logger(__name__)


class Live2DModelWrapper:
    """
    Live2D 模型封装器
    提供加载、更新、绘制、参数设置、动作播放、点击检测等接口
    """

    def __init__(self):
        self._model: Optional[live2d_v2.LAppModel] = None
        self._initialized = False
        self._width = 400
        self._height = 600

    @property
    def is_initialized(self) -> bool:
        """模型是否已初始化"""
        return self._initialized and self._model is not None

    def init_core(self) -> bool:
        """
        初始化 Live2D Core 与 OpenGL 环境
        注意：glewInit() 必须在 QOpenGLWidget.initializeGL() 中调用
        :return: 是否成功
        """
        try:
            # 必须先调用 init() 初始化 Framework，否则 PlatformManager 为 None
            live2d_v2.init()
            live2d_v2.glInit()
            logger.info("Live2D Core 初始化成功")
            return True
        except Exception as e:
            logger.error(f"Live2D Core 初始化失败: {e}")
            return False

    def load(self, model_path: str) -> bool:
        """
        加载 Live2D 模型
        :param model_path: model.json 的绝对路径
        :return: 是否加载成功
        """
        try:
            self._model = live2d_v2.LAppModel()
            self._model.LoadModelJson(model_path)
            self._model.Resize(self._width, self._height)
            # 关闭内置自动呼吸，由应用层自行控制以实现更平滑的效果
            self._model.SetAutoBreathEnable(False)
            self._model.SetAutoBlinkEnable(True)
            self._initialized = True
            logger.info(f"模型加载成功: {model_path}")
            return True
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._model = None
            self._initialized = False
            return False

    def update(self, delta_time: float) -> None:
        """
        更新模型状态
        :param delta_time: 距离上一帧的时间（秒）
        """
        if self._model is None:
            return
        try:
            self._model.Update()
        except Exception as e:
            logger.warning(f"模型更新异常: {e}")

    def draw(self) -> None:
        """绘制模型"""
        if self._model is None:
            return
        try:
            self._model.Draw()
        except Exception as e:
            logger.warning(f"模型绘制异常: {e}")

    def resize(self, width: int, height: int) -> None:
        """
        调整画布大小
        :param width: 画布宽度
        :param height: 画布高度
        """
        self._width = width
        self._height = height
        if self._model is not None:
            try:
                self._model.Resize(width, height)
            except Exception as e:
                logger.warning(f"模型 resize 异常: {e}")

    def set_param(self, param_name: str, value: float) -> None:
        """
        设置模型参数
        :param param_name: 参数名，如 PARAM_EYE_BALL_X
        :param value: 参数值
        """
        if self._model is None:
            return
        try:
            self._model.SetParameterValue(param_name, value)
        except Exception as e:
            logger.warning(f"设置参数 {param_name} 失败: {e}")

    def add_param(self, param_name: str, value: float) -> None:
        """
        累加模型参数值
        :param param_name: 参数名
        :param value: 累加值
        """
        if self._model is None:
            return
        try:
            self._model.AddParameterValue(param_name, value)
        except Exception as e:
            logger.debug(f"累加参数 {param_name} 失败: {e}")

    def start_motion(self, motion_group: str, motion_no: int, priority: int = 3) -> None:
        """
        播放指定动作
        :param motion_group: 动作组名，如 idle / tapBody / flickHead
        :param motion_no: 动作编号
        :param priority: 优先级（数值越大优先级越高）
        """
        if self._model is None:
            return
        try:
            # MotionPriority 枚举值：NONE=0, IDLE=1, NORMAL=2, FORCE=3
            if priority >= 20:
                mp = MotionPriority.FORCE
            elif priority >= 10:
                mp = MotionPriority.NORMAL
            else:
                mp = MotionPriority.IDLE

            self._model.StartMotion(motion_group, motion_no, mp)
            logger.debug(f"播放动作: {motion_group} [{motion_no}], priority={priority}->MotionPriority={mp}")
        except Exception as e:
            logger.warning(f"播放动作 {motion_group}[{motion_no}] 失败: {e}")

    def hit_test(self, hit_area_name: str, x: float, y: float) -> bool:
        """
        点击区域检测
        :param hit_area_name: 检测区域名，如 head / body
        :param x: 归一化 x 坐标 (-1 ~ 1)
        :param y: 归一化 y 坐标 (-1 ~ 1)
        :return: 是否命中
        """
        if self._model is None:
            return False
        try:
            result = self._model.HitTest(hit_area_name, x, y)
            return result is not None
        except Exception as e:
            logger.debug(f"HitTest 异常: {e}")
            return False

    def drag(self, x: float, y: float) -> None:
        """
        设置拖拽位置（影响视线与头部跟随）
        :param x: 归一化 x 坐标 (-1 ~ 1)
        :param y: 归一化 y 坐标 (-1 ~ 1)
        """
        if self._model is None:
            return
        try:
            self._model.Drag(x, y)
        except Exception as e:
            logger.debug(f"Drag 设置失败: {e}")

    def set_lip_sync(self, value: float) -> None:
        """
        设置口型同步值
        :param value: 0.0 ~ 1.0
        """
        if self._model is None:
            return
        try:
            self._model.setLipSyncValue(value)
        except Exception as e:
            logger.debug(f"口型同步设置失败: {e}")
