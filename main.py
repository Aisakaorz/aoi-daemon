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

from core.app import AoiDaemonApp


# resources/model/ 的绝对路径（以本文件为基准）
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "model")


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


def main() -> int:
    """应用入口"""
    if not _has_model_files():
        _show_missing_model_dialog()
        return 0

    app = AoiDaemonApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
