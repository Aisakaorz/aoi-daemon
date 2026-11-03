# -*- coding: utf-8 -*-
"""
使魔角色档案：为多位 Live2D 使魔（葵酱、未来的菌酱等）预留的注册表
新增使魔 = 在 CHARACTERS 里加一条记录 + 放置模型文件，
界面文案（菜单/气泡/启动画面）与渲染参数（模型路径/hit 区域/底部比例）
全部从档案读取，切换角色只改 config.json 的 character_id
"""
import os

from utils import config_manager as cfg

# 档案字段说明：
#   name          使魔名字（菜单/气泡/启动画面文案使用）
#   model_json    Live2D 模型入口文件（相对应用根目录）
#   snd_dir       点击音效目录（可选，空字符串表示无音效）
#   bottom_ratio  角色视觉底部占窗口高度比例（吸附/聊天面板定位基准，经视觉微调）
#   head_rect     头部 hit 区域 (x0, x1, y0, y1)，占窗口宽/高比例
#   body_rect     身体 hit 区域 (x0, x1, y0, y1)，占窗口宽/高比例
CHARACTERS: dict[str, dict] = {
    "aoi": {
        "name": "葵酱",
        "model_json": os.path.join(
            "resources", "model", "live2d-widget-model-haru", "haru02.model.json"
        ),
        "snd_dir": os.path.join("resources", "model", "live2d-widget-model-haru", "snd"),
        "bottom_ratio": 0.955,
        "head_rect": (0.25, 0.75, 0.05, 0.45),
        "body_rect": (0.20, 0.80, 0.40, 0.90),
    },
    # 预留示例（ uncomment 并放置模型后即可用）：
    # "kin": {
    #     "name": "菌酱",
    #     "model_json": os.path.join("resources", "characters", "kin", "model", "kin.model.json"),
    #     "snd_dir": "",
    #     "bottom_ratio": 0.96,
    #     "head_rect": (0.25, 0.75, 0.05, 0.45),
    #     "body_rect": (0.20, 0.80, 0.40, 0.90),
    # },
}

_DEFAULT_ID = "aoi"


def get_character(character_id: str | None = None) -> dict:
    """按 id 取档案（未知 id 回退默认使魔）"""
    cid = character_id or _DEFAULT_ID
    if cid not in CHARACTERS:
        cid = _DEFAULT_ID
    profile = dict(CHARACTERS[cid])
    profile["id"] = cid
    return profile


def current_character() -> dict:
    """当前使魔档案（config.json 的 character_id，默认葵酱）"""
    return get_character(cfg.get("character_id", _DEFAULT_ID))


def character_model_json() -> str:
    """当前使魔的模型入口文件绝对路径"""
    return os.path.join(_app_root(), current_character()["model_json"])


def _app_root() -> str:
    from utils.paths import app_root
    return app_root()
