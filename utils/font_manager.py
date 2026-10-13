# -*- coding: utf-8 -*-
"""
字体管理：加载应用内置字体（resources/fonts/），保证任何设备上显示一致
- ZCOOL KuaiLe（站酷快乐体）：圆头俏皮的萌系字体，SIL OFL 1.1 许可，
  可自由随应用分发（许可证见 resources/fonts/OFL-ZCOOLKuaiLe.txt）
- 字体文件缺失/加载失败时自动回退系统黑体，不影响功能
"""
import os
import sys

from PySide6.QtGui import QFont, QFontDatabase

from utils.logger import get_logger

logger = get_logger(__name__)

# 内置字体文件（按优先级顺序，取第一个加载成功的作为萌系字体）
_BUNDLED_FONT_FILES = ("ZCOOLKuaiLe-Regular.ttf",)

# 回退字体（各平台普遍可用的无衬线字体）
_FALLBACK_FAMILY = "Microsoft YaHei UI"

# 正文字体：装饰字体（ZCOOL KuaiLe）在小字号下笔画发虚，
# 正文/输入等长时间阅读场景使用系统优化过的高可读性字体
if sys.platform == "win32":
    _BODY_FAMILY = "Microsoft YaHei UI"
elif sys.platform == "darwin":
    _BODY_FAMILY = "PingFang SC"
else:
    _BODY_FAMILY = "Sans Serif"

_loaded_family: str | None = None
_load_attempted = False


def load_bundled_fonts() -> None:
    """把 resources/fonts/ 下的内置字体注册进 Qt 字体数据库（幂等）。
    须在 QApplication 创建后调用（cute_font 内部会惰性调用）。"""
    global _loaded_family, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True
    font_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "fonts"
    )
    for fname in _BUNDLED_FONT_FILES:
        path = os.path.join(font_dir, fname)
        if not os.path.exists(path):
            logger.warning(f"内置字体文件缺失: {path}")
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id == -1:
            logger.warning(f"内置字体加载失败: {path}")
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _loaded_family = families[0]
            logger.info(f"内置萌字体已加载: {_loaded_family} ({fname})")
            return
    logger.info("内置字体不可用，萌系字体回退为系统字体")


def cute_family() -> str:
    """当前萌系字体族名（内置字体不可用时为回退字体），供样式表使用"""
    load_bundled_fonts()
    return _loaded_family or _FALLBACK_FAMILY


def cute_font(point_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """萌系展示字体（内置 ZCOOL KuaiLe，缺失时回退系统黑体）。

    适合标题、菜单、启动画面等展示场景；小字号正文请用 body_font()。
    :param point_size: 字号（逻辑像素）
    :param weight: 字重（ZCOOL KuaiLe 仅 Regular，加粗由 Qt 合成）
    """
    return QFont(cute_family(), point_size, weight)


def body_family() -> str:
    """正文字体族名（系统高可读性字体），供样式表使用"""
    return _BODY_FAMILY


def body_font(point_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """正文阅读字体——系统为屏幕小字号优化过的无衬线字体，清晰易读"""
    return QFont(_BODY_FAMILY, point_size, weight)
