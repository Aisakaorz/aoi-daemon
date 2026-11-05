# -*- coding: utf-8 -*-
"""
路径统一：区分"只读内置资源"与"可写运行数据"，兼容 PyInstaller 打包

- bundled(*parts): 打包时随 exe 分发的只读资源（fonts/icons）。
  单文件打包后位于临时解压目录 sys._MEIPASS，开发时位于项目根
- app_root(*parts): 应用运行根目录（可写：config.json、logs/、temp/、
  用户放置的 Live2D 模型、应用内下载的语音模型）。
  打包后为 exe 所在目录，开发时为项目根
"""
import os
import sys


def bundled(*parts: str) -> str:
    """只读内置资源路径（优先 PyInstaller 解压目录）"""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def find_resource(*parts: str) -> str | None:
    """查找资源文件，返回可用的绝对路径；找不到返回 None。

    查找顺序：内置资源目录（开发时为项目根，打包时为 exe 解压目录）→
    应用运行根目录（打包后为 exe 同级，允许用户自行放置/替换资源）。
    全程不抛异常：图标、字体这类可降级资源不应因为路径问题阻断启动。
    """
    for path in (bundled(*parts), app_root(*parts)):
        try:
            if os.path.isfile(path):
                return path
        except (OSError, TypeError, ValueError):
            continue
    return None


def app_icon_path(tray: bool = False) -> str | None:
    """应用图标路径：按优先级返回第一个可用的文件，全部缺失返回 None。

    tray=True 时优先专用托盘图标；否则优先主图标（.ico 在 Windows/macOS
    的 Qt 下都能解析，.icns / 托盘 png 作为兜底）。
    """
    names = (
        ("tray_icon.png", "tray.ico", "app_icon.ico")
        if tray
        else ("app_icon.ico", "app_icon.icns", "tray_icon.png")
    )
    for name in names:
        path = find_resource("resources", "icons", name)
        if path:
            return path
    return None


def app_root(*parts: str) -> str:
    """应用运行根目录（可写数据）"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
