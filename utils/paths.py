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


def app_root(*parts: str) -> str:
    """应用运行根目录（可写数据）"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
