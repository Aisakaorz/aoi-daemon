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
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QEvent
from PySide6.QtGui import QMouseEvent

from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine, CharacterState
from utils.logger import get_logger
from utils.paths import app_root

logger = get_logger(__name__)

# 降采样全屏四边形着色器（核心上下文可用；失败时回退固定管线）
_QUAD_VS = """#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""
_QUAD_FS = """#version 330 core
in vec2 v_uv;
out vec4 frag_color;
uniform sampler2D u_texture;
void main() {
    frag_color = texture(u_texture, v_uv);
}
"""


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

    # 渲染超采样倍数：1 = 关闭（直接渲染），2 = 按物理分辨率 2 倍渲染后线性降采样
    # 显著改善边缘锯齿与细微移动时的闪烁；模型为轻量 2D 绘制，对性能影响很小
    # 低配机器如遇性能问题可改为 1；FBO 创建失败时自动回退直接渲染
    SSAA_SCALE = 2

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

        # 超采样离屏渲染目标（lazy 创建，物理尺寸变化时按新尺寸重建）
        self._ssaa_fbo = None
        self._ssaa_tex = None
        self._ssaa_w = 0
        self._ssaa_h = 0

        # 降采样 quad 着色器资源（lazy 创建）
        self._quad_prog = None
        self._quad_vao = 0
        self._quad_vbo = 0

        # 定时器：每 30ms 更新一次鼠标悬停状态（响应更快，避免上下区域穿透延迟）
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._update_mouse_over_model_async)
        self._hover_timer.start(30)

        # 全局视线跟踪定时器：即使鼠标离开窗口，也能让角色看向鼠标方向
        self._global_eye_timer = QTimer(self)
        self._global_eye_timer.timeout.connect(self._update_global_eye)
        self._global_eye_timer.start(16)

    def initializeGL(self) -> None:
        """OpenGL 初始化（glewInit 必须在此方法中调用，不可提前）"""
        try:
            if not self._model.init_core():
                logger.error("Live2D Core 初始化失败，模型将无法渲染")
                self.model_ready.emit()
                return
        except Exception as e:
            logger.error(f"initializeGL 异常: {e}")
            self.model_ready.emit()
            return

        # 模型入口文件（用户自备，放置于应用根目录 resources/model/ 下）
        model_path = app_root(
            "resources", "model", "live2d-widget-model-haru", "haru02.model.json"
        )
        if not os.path.exists(model_path):
            logger.error(f"模型文件不存在: {model_path}")
            self.model_ready.emit()
            return

        if not self._model.load(model_path):
            logger.error("模型加载失败，请检查模型文件是否完整")
            self.model_ready.emit()
            return

        # 关闭内置自动呼吸，由应用层完全控制
        self._model._model.SetAutoBreathEnable(False)
        self._model._model.SetAutoBlinkEnable(True)

        # 模型默认 center_x=0、layout.width=2.9，而 Resize(400,600) 会按 height>width
        # 把绘制宽度覆写为 2.0，导致 translateX=-1.45 的偏移让模型偏左约 0.45。
        # 手动补偿 offset 让模型水平居中。
        self._model._model.SetOffset(0.45, 0.0)

        # 设置纹理参数：CLAMP_TO_EDGE 消除 texture seam 浅线
        try:
            import OpenGL.GL as gl
            textures = self._model._model.live2DModel.drawParamGL.textures
            for tex_id in textures:
                if tex_id is not None:
                    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
                    # 放大/缩小使用 LINEAR 线性采样：平滑纹理，消除模型像素锯齿
                    # （接缝线由 CLAMP_TO_EDGE 解决，与采样过滤方式无关）
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            logger.info(f"已设置 {len([t for t in textures if t is not None])} 个纹理的 CLAMP_TO_EDGE + LINEAR")
        except Exception as e:
            logger.debug(f"纹理参数设置失败: {e}")

        logger.info("Live2DCanvas OpenGL 初始化完成")
        self.model_ready.emit()

    def paintGL(self) -> None:
        """
        每帧渲染
        超采样（SSAA_SCALE > 1）时：模型渲染到物理分辨率 SSAA 倍的离屏纹理，
        再线性降采样回默认帧缓冲，改善边缘锯齿与细微移动时的闪烁
        """
        try:
            import OpenGL.GL as gl

            # 禁用 depth test，避免模型部件间出现深度裁剪
            gl.glDisable(gl.GL_DEPTH_TEST)

            dpr = self.devicePixelRatio()
            pw = max(1, int(self.width() * dpr))
            ph = max(1, int(self.height() * dpr))

            fbo, fw, fh = self._ensure_ssaa_target(gl, pw, ph)

            if fbo is not None and self._model.is_initialized:
                # 1. 渲染到 SSAA 倍物理分辨率的超采样纹理
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glViewport(0, 0, fw, fh)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                self._draw_model()

                # 2. 线性降采样到 Qt 帧缓冲（预乘 alpha 合成，避免边缘暗晕）
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.defaultFramebufferObject())
                gl.glViewport(0, 0, pw, ph)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                self._blit_downsample(gl)
            else:
                # 回退：直接渲染（超采样关闭或 FBO 创建失败）
                gl.glViewport(0, 0, pw, ph)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                self._draw_model()

            self._log_gl_diagnostics_once(gl)

        except Exception as e:
            logger.warning(f"paintGL 异常: {e}")

    def event(self, event) -> bool:
        # 跨屏拖动等导致 DPR 变化：触发重绘，paintGL 会按新物理尺寸重建超采样目标
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self.update()
        return super().event(event)

    def _draw_model(self) -> None:
        """更新并绘制模型（视口与帧缓冲由调用方准备）"""
        if not self._model.is_initialized:
            return
        # 先更新模型动画
        self._model.update(1.0 / 60.0)
        # 再覆盖参数（视线、呼吸）
        self._update_model_params()
        # 状态机更新（空闲时自动轮播 idle 动作，不播放声音）
        self._state.update(1.0 / 60.0)
        # 绘制
        self._model.draw()

    def _ensure_ssaa_target(self, gl, pw: int, ph: int):
        """
        获取（必要时创建或调整）超采样离屏渲染目标
        :return: (fbo_id, 纹理宽, 纹理高)；超采样关闭或创建失败返回 (None, 0, 0)
        """
        if self.SSAA_SCALE <= 1:
            return None, 0, 0
        fw, fh = pw * self.SSAA_SCALE, ph * self.SSAA_SCALE
        try:
            if self._ssaa_fbo is not None and (self._ssaa_w, self._ssaa_h) == (fw, fh):
                return self._ssaa_fbo, fw, fh
            if self._ssaa_fbo is None:
                self._ssaa_tex = gl.glGenTextures(1)
                self._ssaa_fbo = gl.glGenFramebuffers(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._ssaa_tex)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, fw, fh, 0,
                            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._ssaa_fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                      gl.GL_TEXTURE_2D, self._ssaa_tex, 0)
            status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
            if status != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"FBO 状态异常: 0x{status:x}")
            self._ssaa_w, self._ssaa_h = fw, fh
            return self._ssaa_fbo, fw, fh
        except Exception as e:
            logger.warning(f"超采样 FBO 创建失败，回退直接渲染: {e}")
            self._ssaa_fbo = None
            return None, 0, 0

    def _blit_downsample(self, gl) -> None:
        """把超采样纹理线性降采样绘制到当前帧缓冲"""
        # live2d 绘制后 active 纹理单元可能停在 unit1（遮罩采样），显式切回 unit0
        prev_unit = gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._ssaa_tex)
        gl.glEnable(gl.GL_BLEND)
        # 模型在 FBO 中的混合结果实际为预乘 alpha，用预乘方式合成避免边缘暗晕
        gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        # live2d 绘制后可能遗留 GL_CULL_FACE + GL_CW 正面状态，
        # quad 为 CCW 绕序会被整体背面剔除，必须先关闭面剔除
        gl.glDisable(gl.GL_CULL_FACE)
        try:
            self._draw_quad_shader(gl)
        except Exception as e:
            logger.warning(f"quad 着色器路径失败，回退固定管线: {e}")
            self._draw_quad_fixed(gl)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_BLEND)
        gl.glActiveTexture(prev_unit)

    def _draw_quad_shader(self, gl) -> None:
        """着色器 + VAO 绘制全屏 quad（核心/现代上下文）"""
        prog = self._ensure_quad_program(gl)
        gl.glUseProgram(prog)
        gl.glBindVertexArray(self._quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def _ensure_quad_program(self, gl):
        """编译/链接降采样 quad 着色器并创建 VAO/VBO（惰性，只执行一次）"""
        if self._quad_prog is not None:
            return self._quad_prog
        vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vs, _QUAD_VS)
        gl.glCompileShader(vs)
        if not gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"quad 顶点着色器编译失败: {gl.glGetShaderInfoLog(vs)}")
        fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fs, _QUAD_FS)
        gl.glCompileShader(fs)
        if not gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"quad 片元着色器编译失败: {gl.glGetShaderInfoLog(fs)}")
        prog = gl.glCreateProgram()
        gl.glAttachShader(prog, vs)
        gl.glAttachShader(prog, fs)
        gl.glLinkProgram(prog)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        if not gl.glGetProgramiv(prog, gl.GL_LINK_STATUS):
            raise RuntimeError(f"quad 着色器链接失败: {gl.glGetProgramInfoLog(prog)}")

        import ctypes
        import numpy as np
        # 两个三角形组成全屏四边形：NDC 坐标 + UV，每顶点 4 个 float
        verts = np.array([
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
             1.0,  1.0, 1.0, 1.0,
            -1.0, -1.0, 0.0, 0.0,
             1.0,  1.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 1.0,
        ], dtype=np.float32)
        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, verts.nbytes, verts, gl.GL_STATIC_DRAW)
        stride = 4 * verts.itemsize
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
        gl.glEnableVertexAttribArray(1)
        gl.glBindVertexArray(0)
        self._quad_vao, self._quad_vbo = vao, vbo
        self._quad_prog = prog
        logger.info("降采样 quad 着色器初始化完成")
        return prog

    def _draw_quad_fixed(self, gl) -> None:
        """固定管线绘制全屏 quad（仅兼容型上下文可用，作为着色器失败的回退）"""
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0.0, 1.0); gl.glVertex2f(-1.0, 1.0)
        gl.glTexCoord2f(1.0, 1.0); gl.glVertex2f(1.0, 1.0)
        gl.glTexCoord2f(1.0, 0.0); gl.glVertex2f(1.0, -1.0)
        gl.glTexCoord2f(0.0, 0.0); gl.glVertex2f(-1.0, -1.0)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)

    def _log_gl_diagnostics_once(self, gl) -> None:
        """首帧输出一次 GL 运行环境诊断（排查锯齿/缩放问题时有用）"""
        if getattr(self, "_gl_diag_done", False):
            return
        self._gl_diag_done = True
        try:
            vx, vy, vw, vh = gl.glGetIntegerv(gl.GL_VIEWPORT)
            samples = gl.glGetIntegerv(gl.GL_SAMPLES)
            ssaa = self.SSAA_SCALE if self._ssaa_fbo is not None else 1
            logger.info(
                f"GL 诊断: dpr={self.devicePixelRatio()} "
                f"widget={self.width()}x{self.height()} "
                f"绘制后视口={vw}x{vh}@{vx},{vy} "
                f"MSAA采样数={samples} "
                f"超采样={ssaa}x"
            )
        except Exception as e:
            logger.debug(f"GL 诊断失败: {e}")

    def resizeGL(self, width: int, height: int) -> None:
        """OpenGL 视口调整（视口用物理像素，模型布局用逻辑像素）"""
        try:
            import OpenGL.GL as gl
            # 高 DPI 屏下 backing store 是物理分辨率，视口必须乘 DPR，
            # 否则渲染结果会被 Qt 拉伸放大，产生模糊与锯齿
            dpr = self.devicePixelRatio()
            pw = max(1, int(width * dpr))
            ph = max(1, int(height * dpr))
            gl.glViewport(0, 0, pw, ph)
            # Resize 也传物理尺寸：库内部（如遮罩裁剪）按此恢复视口，需与实际视口一致
            self._model.resize(pw, ph)
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
        path = app_root("resources", "model", "live2d-widget-model-haru", "snd", filename)
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
