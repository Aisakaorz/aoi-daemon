#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
葵之使魔 ~AoiDaemon~ 入口文件
葵酱（Aoi）是基于 Live2D 免费模型 haru 的桌面看板娘。
v0.1：透明置顶窗口 + Live2D 渲染 + 视线跟踪 + 呼吸动画 + 聊天占位 + 系统托盘

运行前请确保：
1. 已安装依赖: pip install -r requirements.txt
2. resources/model/ 下已有 haru 模型文件

使用方法:
    python main.py
"""
import glob
import io
import os
import subprocess
import sys

# ------------------------------------------------------------------
# 关键：在导入任何 Qt 模块之前，把 C 层 stderr (fd 2) 重定向到 devnull。
# FFmpeg 直接从 C 运行时写 fd 2 输出 MP3 解析日志，Python 层无法拦截。
# 但 logger 使用 sys.stdout，不受影响；Python 异常我们通过恢复 sys.stderr
# 绑定到原始 fd 来保留。
# ------------------------------------------------------------------
_original_stderr_fd = os.dup(2)
_devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull, 2)
os.close(_devnull)

# 恢复 Python 层的 sys.stderr，确保异常和 print(..., file=sys.stderr) 正常显示
sys.stderr = io.TextIOWrapper(
    os.fdopen(_original_stderr_fd, "wb"), line_buffering=True
)

# 同时屏蔽 Qt 自身的多媒体日志
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg=false"

from utils import config_manager as cfg
from utils.logger import get_logger

logger = get_logger(__name__)

# resources/model/ 的绝对路径（以本文件为基准）
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "model")
_ROOT = os.path.dirname(os.path.abspath(__file__))


def _has_model_files() -> bool:
    """检查 resources/model/ 下是否存在 .model.json 文件"""
    pattern = os.path.join(_MODEL_DIR, "**", "*.model.json")
    return len(glob.glob(pattern, recursive=True)) > 0


def _show_missing_model_dialog() -> None:
    """弹出模型缺失提示，点击确定后优雅退出"""
    # 延迟导入 Qt，确保 stderr 重定向等环境准备已就绪
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QIcon

    app = QApplication(sys.argv)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setWindowTitle("资源文件缺失")
    msg.setText(
        "未检测到 Live2D 模型文件，请按 README「配置 Live2D 模型」章节放置文件后重新启动。"
    )
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)

    # 设置应用图标
    icon_path = "resources/icons/app_icon.ico"
    if os.path.exists(icon_path):
        msg.setWindowIcon(QIcon(icon_path))

    msg.exec()


class _SplashChildProxy:
    """子进程启动画面的代理：对主进程暴露与 SplashScreen 相同的 request_close 接口"""

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc

    def request_close(self) -> None:
        try:
            self._proc.stdin.write(b"close\n")
            self._proc.stdin.flush()
        except Exception:
            pass  # 子进程已退出或管道断开时忽略

    def terminate(self) -> None:
        """退出兜底：通知关闭 → 等待 → 结束整个进程树 → 强杀 → 关闭 stdin 管道。

        必须显式关闭 stdin 管道写端：否则解释器退出阶段 GC 最终化这个
        BufferedWriter 时会因句柄半失效抛出 OSError(EINVAL)"""
        self.request_close()
        try:
            self._proc.wait(timeout=3)
        except Exception:
            pass
        # 结束进程树（兼容解释器重定向器派生的中间进程残留）
        if self._proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                    capture_output=True,
                )
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        except Exception:
            pass


def _launch_splash_child():
    """启动子进程启动画面（无需 Qt，可在主进程任何导入之前调用）。

    独立进程的动画运行在子进程自己的事件循环中，不被主进程
    的重型导入/窗口构建/模型加载阻塞，保证从显示到关闭全程流畅。
    启动失败返回 None，由调用方回退到进程内启动画面。
    """
    try:
        if getattr(sys, "frozen", False):
            # PyInstaller 打包模式：复用主程序 exe，带 --splash-child 参数
            cmd = [sys.executable, "--splash-child"]
        else:
            # 开发模式：直接用当前解释器（venv 内自带 PySide6），
            # CREATE_NO_WINDOW 避免控制台窗口闪现。
            # 不能换 pythonw（GUI 子系统会关闭 stdio，stdin 管道失效），
            # 也不能换 sys._base_executable（脱离 venv 后找不到 PySide6）
            cmd = [sys.executable, os.path.join(_ROOT, "splash_child.py")]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        logger.info("子进程启动画面已启动")
        return _SplashChildProxy(proc)
    except Exception as e:
        logger.warning(f"子进程启动画面启动失败，回退进程内启动画面: {e}")
        return None


def main() -> int:
    """应用入口"""
    # 打包模式下作为启动画面子进程运行（须在重型导入之前分流）
    if "--splash-child" in sys.argv:
        from splash_child import run_splash_child
        return run_splash_child()

    # 先加载用户配置（窗口位置、角色大小等）
    cfg.load()

    if not _has_model_files():
        _show_missing_model_dialog()
        return 0

    # 尽早启动子进程启动画面：不依赖 Qt，先于一切重型导入
    splash_proxy = _launch_splash_child()

    # 平台/GL 环境设置（须在 QApplication 创建前）
    from core.bootstrap import setup_platform_env, setup_surface_format
    setup_platform_env()
    setup_surface_format()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("葵之使魔")
    app.setApplicationDisplayName("AoiDaemon")

    # 子进程启动画面失败时的兜底：进程内启动画面
    splash = None
    if splash_proxy is None:
        from ui.splash_screen import SplashScreen
        splash = SplashScreen()
        splash.show()
        app.processEvents()

    try:
        # 重型导入放在启动画面显示之后
        from core.app import AoiDaemonApp
        return AoiDaemonApp(app, splash or splash_proxy).run()
    finally:
        if splash_proxy is not None:
            splash_proxy.terminate()


if __name__ == "__main__":
    sys.exit(main())
