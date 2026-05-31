# -*- coding: utf-8 -*-
"""
Live2D OpenGL 渲染画布
基于 QOpenGLWidget，负责模型渲染、鼠标交互映射、视线跟踪、呼吸动画
"""
import sys
import math
import os
import random
from typing import Optional, Callable

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QMouseEvent

from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine, CharacterState
from utils.logger import get_logger

logger = get_logger(__name__)


class Live2DCanvas(QOpenGLWidget):
    """
    Live2D 渲染画布
    - 初始化 OpenGL / GLEW
    - 60 FPS 渲染循环
    - 鼠标映射到 ParamEyeBallX/Y、ParamAngleX/Y/Z
    - 呼吸动画（正弦波驱动 ParamBreath + ParamBodyAngleX/Y）
    - 点击检测（Head / Body）
    """

    # 模型初始化完成信号（用于关闭启动画面）
    model_ready = Signal()
    # 加载进度信号（0~100，用于更新启动画面进度条）
    loading_progress = Signal(int)

    def __init__(
        self,
        model_wrapper: Live2DModelWrapper,
        state_machine: StateMachine,
        parent=None
    ):
        super().__init__(parent)
        self._model = model_wrapper
        self._state = state_machine

        # 开启鼠标追踪（鼠标不按下时也能接收 mouseMoveEvent，视线跟踪必需）
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # 渲染循环 60 FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # 约 60 FPS

        # 动画与交互状态
        self._time = 0.0
        self._dragging = False
        self._has_moved = False  # 标记是否发生了拖拽移动（区分单击与拖拽）
        self._press_pos = QPoint(0, 0)  # 鼠标按下时的本地坐标
        self._return_timer: Optional[QTimer] = None  # 用于自动返回 idle 的定时器
        self._mouse_pos = QPoint(0, 0)
        self._norm_x = 0.0  # 归一化鼠标 X (-1 ~ 1)
        self._norm_y = 0.0  # 归一化鼠标 Y (-1 ~ 1)

        # 呼吸动画周期（秒）
        self._breath_period = 3.5

        # 鼠标是否悬停在模型上（用于 Windows 鼠标穿透）
        self._mouse_over_model = False

        # 绑定状态机回调
        self._state.motion_callback = self._on_state_motion
        self._state.state_change_callback = self._on_state_change

        # 点击音效（Phase 1 可选播放）
        self._sound_enabled = True
        self._sound_players: list = []  # 持有播放器引用防止被回收

        # 定时器：每 30ms 更新一次鼠标悬停状态（响应更快，避免上下区域穿透延迟）
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._update_mouse_over_model_async)
        self._hover_timer.start(30)

        # 全局视线跟踪定时器：即使鼠标离开窗口，也能让角色看向鼠标方向
        self._global_eye_timer = QTimer(self)
        self._global_eye_timer.timeout.connect(self._update_global_eye)
        self._global_eye_timer.start(16)

    def initializeGL(self) -> None:
        """
        OpenGL 初始化
        注意：glewInit() 必须在此方法中调用，不可提前
        """
        self.loading_progress.emit(10)

        try:
            if not self._model.init_core():
                logger.error("Live2D Core 初始化失败，模型将无法渲染")
                self.loading_progress.emit(100)
                self.model_ready.emit()
                return
        except Exception as e:
            logger.error(f"initializeGL 异常: {e}")
            self.loading_progress.emit(100)
            self.model_ready.emit()
            return

        self.loading_progress.emit(35)

        # 加载模型
        model_path = os.path.abspath(
            "resources/model/live2d-widget-model-haru/haru02.model.json"
        )
        if not os.path.exists(model_path):
            logger.error(f"模型文件不存在: {model_path}")
            self.loading_progress.emit(100)
            self.model_ready.emit()
            return

        self.loading_progress.emit(45)

        if not self._model.load(model_path):
            logger.error("模型加载失败，请检查模型文件是否完整")
            self.loading_progress.emit(100)
            self.model_ready.emit()
            return

        self.loading_progress.emit(75)

        # 关闭内置自动呼吸，由应用层完全控制
        self._model._model.SetAutoBreathEnable(False)
        self._model._model.SetAutoBlinkEnable(True)

        # 模型默认 center_x=0、layout.width=2.9，而 Resize(400,600) 会按 height>width
        # 把绘制宽度覆写为 2.0，导致 translateX=-1.45 的偏移让模型偏左约 0.45。
        # 手动补偿 offset 让模型水平居中。
        self._model._model.SetOffset(0.45, 0.0)

        self.loading_progress.emit(85)

        # 设置纹理参数：CLAMP_TO_EDGE 消除 texture seam 浅线
        try:
            import OpenGL.GL as gl
            textures = self._model._model.live2DModel.drawParamGL.textures
            for tex_id in textures:
                if tex_id is not None:
                    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
                    # 放大/缩小均使用 NEAREST：彻底消除 texture atlas 内部边界采样导致的细线
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            logger.info(f"已设置 {len([t for t in textures if t is not None])} 个纹理的 CLAMP_TO_EDGE + NEAREST")
        except Exception as e:
            logger.debug(f"纹理参数设置失败: {e}")

        self.loading_progress.emit(100)

        # 启动时不自动播放动作，保持 IDLE，等待用户交互

        logger.info("Live2DCanvas OpenGL 初始化完成")
        self.model_ready.emit()

    def paintGL(self) -> None:
        """
        每帧渲染
        """
        try:
            import OpenGL.GL as gl

            # 禁用 depth test，避免模型部件间出现深度裁剪
            gl.glDisable(gl.GL_DEPTH_TEST)

            # 清屏（完全透明）
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            if self._model.is_initialized:
                # 先更新模型动画
                self._model.update(1.0 / 60.0)
                # 再覆盖参数（视线、呼吸）
                self._update_model_params()
                # 状态机更新（空闲时自动轮播 idle 动作，不播放声音）
                self._state.update(1.0 / 60.0)
                # 绘制
                self._model.draw()

        except Exception as e:
            logger.warning(f"paintGL 异常: {e}")

    def resizeGL(self, width: int, height: int) -> None:
        """OpenGL 视口调整"""
        try:
            import OpenGL.GL as gl
            gl.glViewport(0, 0, width, height)
            self._model.resize(width, height)
            # Resize 会重置 matrix，需要重新补偿居中偏移
            self._model._model.SetOffset(0.45, 0.0)
        except Exception as e:
            logger.warning(f"resizeGL 异常: {e}")

    def _update_model_params(self) -> None:
        """
        更新模型动态参数：视线跟踪、呼吸动画
        注意：必须在 Update() 之后调用，否则动画会覆盖手动参数
        关键：非 IDLE 状态下不覆盖身体/呼吸参数，避免 tap/greeting 等动作被抹掉
        """
        self._time += 1.0 / 60.0

        # 1. 视线跟踪：始终启用（交互核心）
        eye_x = max(-1.2, min(1.2, self._norm_x * 1.5))
        eye_y = max(-1.2, min(1.2, self._norm_y * 1.5))
        self._model.set_param("PARAM_EYE_BALL_X", eye_x)
        self._model.set_param("PARAM_EYE_BALL_Y", eye_y)

        # 2. 头部跟随 + 呼吸动画：仅在 IDLE 时应用，避免覆盖 tap/greeting/thinking 动作
        if self._state.current_state == CharacterState.IDLE:
            self._model.set_param("PARAM_ANGLE_X", self._norm_x * 15.0)
            self._model.set_param("PARAM_ANGLE_Y", self._norm_y * 10.0)
            self._model.set_param("PARAM_ANGLE_Z", self._norm_x * 5.0)

            breath = math.sin(2.0 * math.pi * self._time / self._breath_period)
            self._model.set_param("PARAM_BREATH", breath * 0.25 + 0.5)
            self._model.set_param("PARAM_BODY_ANGLE_X", breath * 2.0)
            self._model.set_param("PARAM_BODY_ANGLE_Y", breath * 0.8)
            self._model.set_param("PARAM_BODY_ANGLE_Z", breath * 0.5)

    def _update_global_eye(self) -> None:
        """
        全局视线跟踪：即使鼠标离开窗口，角色也会看向鼠标方向
        """
        from PySide6.QtGui import QCursor
        pos = self.mapFromGlobal(QCursor.pos())
        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        if w > 0 and h > 0:
            self._norm_x = (x / w) * 2.0 - 1.0
            self._norm_y = -((y / h) * 2.0 - 1.0)
            # 限制在合理范围，避免眼睛翻得太夸张
            self._norm_x = max(-1.5, min(1.5, self._norm_x))
            self._norm_y = max(-1.5, min(1.5, self._norm_y))

    def _on_state_motion(self, group: str, no: int, priority: int) -> None:
        """状态机动作回调"""
        # 空闲时自动播放动作需要能替换当前循环的 idle 动作，
        # 将优先级提升到 NORMAL 以覆盖正在播放的 MotionPriority.IDLE 动作
        if self._state.current_state == CharacterState.IDLE:
            priority = max(priority, 15)
        self._model.start_motion(group, no, priority)

    def _on_state_change(self, state: CharacterState) -> None:
        """状态变更回调（预留）"""
        pass

    # ---- 鼠标事件 ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下：记录起始位置，准备拖拽"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._has_moved = False
            self._press_pos = event.position().toPoint()
            self._mouse_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动：更新视线跟踪 + 拖拽窗口"""
        x = event.position().x()
        y = event.position().y()

        # 更新视线归一化坐标
        w = self.width()
        h = self.height()
        if w > 0 and h > 0:
            self._norm_x = (x / w) * 2.0 - 1.0
            self._norm_y = -((y / h) * 2.0 - 1.0)

        # 拖拽窗口移动
        if self._dragging:
            # 如果移动超过 4px，认为是拖拽而非单击
            if not self._has_moved:
                delta_press = event.position().toPoint() - self._press_pos
                if abs(delta_press.x()) > 4 or abs(delta_press.y()) > 4:
                    self._has_moved = True

            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._mouse_pos
            self._mouse_pos = global_pos
            top_window = self.window()
            if top_window:
                top_window.move(top_window.pos() + delta)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放：区分单击与拖拽，拖拽结束时尝试任务栏吸附"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            # 如果几乎没移动，视为单击，触发 hit test
            if not self._has_moved:
                self._do_hit_test(event.position().x(), event.position().y())
            # 无论单击还是拖拽，只要窗口靠近任务栏就尝试吸附
            # （不靠近时 _snap_to_taskbar 内部什么都不做）
            top_window = self.window()
            if top_window and hasattr(top_window, "_snap_to_taskbar"):
                top_window._snap_to_taskbar()
            self._has_moved = False
        super().mouseReleaseEvent(event)

    def _update_mouse_over_model_async(self) -> None:
        """
        异步更新鼠标是否悬停在模型上的标志（定时器调用，不阻塞 mouseMoveEvent）
        用于 Windows 鼠标穿透：透明区域不阻挡底层操作
        使用几何矩形区域替代 v2 hitTestSimple（兼容性更稳定）
        """
        if not self._model.is_initialized:
            self._mouse_over_model = False
            return

        # 获取鼠标在当前窗口内的坐标
        try:
            from PySide6.QtGui import QCursor
            pos = self.mapFromGlobal(QCursor.pos())
            x = pos.x()
            y = pos.y()
        except Exception:
            self._mouse_over_model = True
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            self._mouse_over_model = False
            return

        # 只有鼠标在窗口范围内才检测
        if x < 0 or x > w or y < 0 or y > h:
            self._mouse_over_model = False
            return

        # 几何矩形近似（haru 模型）：头部在上半区，身体在中下半区
        head_hit = (0.25 * w <= x <= 0.75 * w and 0.05 * h <= y <= 0.45 * h)
        body_hit = (0.20 * w <= x <= 0.80 * w and 0.40 * h <= y <= 0.90 * h)
        self._mouse_over_model = head_hit or body_hit

    def _do_hit_test(self, x: float, y: float) -> None:
        """
        执行点击区域检测
        使用几何矩形区域替代 v2 hitTestSimple（兼容性更稳定）
        """
        if not self._model.is_initialized:
            return

        # 非 IDLE 状态时忽略点击（单击触发 TAP 等状态期间）
        if self._state.current_state != CharacterState.IDLE:
            logger.debug(f"点击被忽略，当前状态: {self._state.current_state}")
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # 几何矩形近似（haru 模型）
        head_hit = (0.25 * w <= x <= 0.75 * w and 0.05 * h <= y <= 0.45 * h)
        body_hit = (0.20 * w <= x <= 0.80 * w and 0.40 * h <= y <= 0.90 * h)
        logger.debug(f"点击 ({x:.0f},{y:.0f}) head={head_hit} body={body_hit}")

        # 检测头部
        if head_hit:
            logger.debug("点击命中: head")
            self._state.force_transit(CharacterState.TAP_HEAD)
            self._play_sound("flickHead_00.mp3")
            self._schedule_return_to_idle(3000)
            return

        # 检测身体
        if body_hit:
            logger.debug("点击命中: body")
            self._state.force_transit(CharacterState.TAP_BODY)
            snd_no = random.randint(0, 2)
            self._play_sound(f"tapBody_0{snd_no}.mp3")
            self._schedule_return_to_idle(3000)
            return

    def _schedule_return_to_idle(self, delay_ms: int) -> None:
        """安排延迟返回 idle，先取消旧的定时器避免冲突"""
        if self._return_timer is not None:
            self._return_timer.stop()
            self._return_timer.deleteLater()
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._state.return_to_idle)
        self._return_timer.start(delay_ms)

    def _play_sound(self, filename: str) -> None:
        """
        播放点击音效（使用 QMediaPlayer，支持 MP3）
        :param filename: 音效文件名
        """
        if not self._sound_enabled:
            return
        path = f"resources/model/live2d-widget-model-haru/snd/{filename}"
        if not os.path.exists(path):
            return
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl

            player = QMediaPlayer(self)
            audio_output = QAudioOutput(self)
            audio_output.setVolume(0.5)
            player.setAudioOutput(audio_output)
            player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            player.play()
            self._sound_players.append(player)

            # 播放结束后自动清理
            def _cleanup(status):
                if status == QMediaPlayer.MediaStatus.EndOfMedia:
                    if player in self._sound_players:
                        self._sound_players.remove(player)
                    player.deleteLater()

            player.mediaStatusChanged.connect(_cleanup)
        except Exception as e:
            logger.debug(f"音效播放失败: {e}")
