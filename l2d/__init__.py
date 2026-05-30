# -*- coding: utf-8 -*-
"""
live2d 包：Live2D 模型封装与渲染辅助

注意：由于第三方库 live2d-py 的包名也是 live2d，为避免命名冲突，
本项目将本地 Live2D 相关业务代码放在 l2d/ 目录下。

live2d-py v2 是纯 Python 实现，不需要额外放置 Core 动态库（Core.dll / libCore.dylib）。
"""
import sys
import os

# 临时移除项目根目录，以便正确导入第三方 live2d-py 库
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_paths_to_remove = [_project_root, os.path.abspath(_project_root), '', '.']
_original_path = sys.path.copy()
sys.path = [p for p in sys.path if p not in _paths_to_remove and os.path.abspath(p) != _project_root]

# live2d-py v2 是纯 Python 实现，不需要 Core 动态库。
# 如果 v2 导入失败，尝试 fallback 到 v2cpp（C++ 扩展，需要 Core.dll/libCore.dylib）。
live2d_v2 = None
LAppModel = None
MotionPriority = None
MotionGroup = None
HitArea = None

try:
    import live2d.v2 as live2d_v2
    from live2d.v2 import LAppModel, MotionPriority, MotionGroup, HitArea

    # Monkey-patch：修复 v2 alive2d_model.py 中 MeshContext 未导入的 bug
    # 该 bug 导致 hitTestSimple / getTransformedPoints 抛出 NameError
    import live2d.v2.core.alive2d_model as _am
    from live2d.v2.core.draw.mesh_context import MeshContext as _MeshContext
    _am.MeshContext = _MeshContext
except Exception as _e:
    try:
        import live2d.v2cpp as live2d_v2
        from live2d.v2cpp import LAppModel, MotionPriority, MotionGroup, HitArea
    except Exception as _e2:
        sys.path = _original_path
        raise ImportError(f"无法导入第三方 live2d.v2 或 live2d.v2cpp 模块: v2={_e}, v2cpp={_e2}")

# 恢复 sys.path
sys.path = _original_path

__all__ = [
    "live2d_v2",
    "LAppModel",
    "MotionPriority",
    "MotionGroup",
    "HitArea",
]
