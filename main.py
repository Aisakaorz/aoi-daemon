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
# 打包后的窗口程序（console=False）没有 fd 2，此时跳过重定向。
# ------------------------------------------------------------------
# 保留终端原本的编码：中文 Windows 控制台多为 cp936，IDE / Windows Terminal 多为 UTF-8。
# 若让 TextIOWrapper 自行猜测，Python 层的中文 traceback 会按错误编码输出成乱码。
_stderr_encoding = getattr(sys.stderr, "encoding", None) or "utf-8"
_stderr_errors = getattr(sys.stderr, "errors", None) or "replace"
_original_stderr_fd = None
try:
    _original_stderr_fd = os.dup(2)
    # 恢复 Python 层的 sys.stderr，确保异常和 print(..., file=sys.stderr) 正常显示
    sys.stderr = io.TextIOWrapper(
        os.fdopen(_original_stderr_fd, "wb"),
        encoding=_stderr_encoding,
        errors=_stderr_errors,
        line_buffering=True,
    )
    _original_stderr_fd = None  # 所有权已移交给 sys.stderr
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 2)
    os.close(_devnull)
except OSError:
    # 任何一步失败（如无控制台的打包窗口程序）都安全跳过
    pass

# 同时屏蔽 Qt 自身的多媒体日志
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg=false"

from utils import config_manager as cfg
from utils.logger import get_logger
from utils.paths import app_root, app_icon_path, bundled

logger = get_logger(__name__)

# 模型目录：内置资源（打包后位于 _MEIPASS）优先，应用运行根目录兜底
_MODEL_DIRS = (bundled("resources", "model"), app_root("resources", "model"))
_ROOT = os.path.dirname(os.path.abspath(__file__))


def _has_model_files() -> bool:
    """检查当前使魔档案指定的模型入口是否存在（兼容旧布局：任一模型目录下有 *.model.json）"""
    from core.character import character_model_json
    if os.path.exists(character_model_json()):
        return True
    for base in _MODEL_DIRS:
        try:
            if os.path.isdir(base) and glob.glob(
                os.path.join(base, "**", "*.model.json"), recursive=True
            ):
                return True
        except OSError:
            continue
    return False


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
    icon_path = app_icon_path()
    if icon_path:
        icon = QIcon(icon_path)
        if not icon.isNull():
            msg.setWindowIcon(icon)

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

    def exited(self) -> bool:
        """子进程是否已退出（用于判断启动画面是否真的在显示）"""
        return self._proc.poll() is not None

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


def _open_splash_child_log():
    """打开启动画面子进程的日志文件（失败返回 None，不影响启动）"""
    import datetime

    try:
        log_dir = app_root("logs")
        os.makedirs(log_dir, exist_ok=True)
        f = open(
            os.path.join(log_dir, "splash_child.log"),
            "w",
            encoding="utf-8",
            buffering=1,
        )
        f.write(f"--- 启动画面子进程 {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        return f
    except Exception:
        return None


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
        # 子进程的 stdout/stderr 必须落盘：启动画面是独立进程，
        # 它一旦在导入/绘制阶段崩溃，界面就是"什么都不出现"，
        # 而丢掉 stderr 会让这类故障完全不可见（无任何线索可查）。
        child_log = _open_splash_child_log()
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=child_log or subprocess.DEVNULL,
                stderr=child_log or subprocess.DEVNULL,
                creationflags=creationflags,
            )
        finally:
            # 父进程不再持有句柄（子进程已继承），避免句柄泄漏
            if child_log is not None:
                child_log.close()
        logger.info(
            f"子进程启动画面已启动（子进程日志: {app_root('logs', 'splash_child.log')}）"
        )
        return _SplashChildProxy(proc)
    except Exception as e:
        logger.warning(f"子进程启动画面启动失败，回退进程内启动画面: {e}")
        return None


def main() -> int:
    """应用入口（带崩溃落盘：打包后无控制台，异常与硬崩溃写入 exe 同级 crash.log）"""
    # 打包模式下作为启动画面子进程运行（须在重型导入之前分流）
    if "--splash-child" in sys.argv:
        from splash_child import run_splash_child
        return run_splash_child()

    try:
        return _main_impl()
    except Exception:
        _write_crash_log()
        raise


def _write_crash_log() -> None:
    """把当前异常 traceback 追加写入 crash.log（静默失败不影响退出）"""
    import traceback
    try:
        with open(app_root("crash.log"), "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass


def _main_impl() -> int:
    # faulthandler：硬崩溃（段错误等）也落盘，便于排查打包/环境问题
    import faulthandler
    try:
        _fh = open(app_root("crash.log"), "a", encoding="utf-8", buffering=1)
        faulthandler.enable(_fh)
    except Exception:
        pass

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
        from core.character import current_character
        splash = SplashScreen(character_name=current_character()["name"])
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
