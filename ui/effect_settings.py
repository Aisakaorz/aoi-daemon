# -*- coding: utf-8 -*-
"""
特效开关的统一入口（v0.1.31 / C 版）

所有装饰组件只读这里、设置窗口只写这里，避免 cfg.get 默认值散落各处。
配置经 utils/config_manager.py 持久化到 config.json，切换即时生效。

归属原则（按审核反馈调整）：
- 只有「一项独立、可单独关掉的效果」才单列开关。
- 属于某个特效自身的显示细节，不单列：在线呼吸是 LIVE 牌的一部分，
  时段换色是飘落花瓣的一部分，两者都常驻自动生效。
- 消息星点是每条新消息自带的常驻小装饰，不需要开关。
- 空闲时的自言自语与交互触发的短句反馈都只是「葵酱冒一句说话气泡」，
  合并为同一个开关（不再单列「状态表情」，避免被误认成面部表情变化）。
- 悬停柔光按「不好看、没起到美化作用」的审核反馈整体移除，不再保留。
- 萌系光标是「应用内自定义指针样式 + 小拖尾」：一颗珊瑚粉小爱心直接作为
  指针本体（热点在中心）+ 小花瓣拖尾，与柔光那种模糊光晕不是同一类东西。
- 打字指示点属于功能性状态提示，启动画面 / 设置 / 关于卡片的背景花纹
  属于弹窗自身装饰，均不列入开关。
"""
from utils import config_manager as cfg

FX_PETALS = "fx_petals"                        # 飘落花瓣（含自动时段换色）
FX_HEART_BURST = "fx_heart_burst"              # 点击角色冒爱心
FX_LIVE_BADGE = "fx_live_badge"                # LIVE 牌（含在线点呼吸）
FX_BUBBLE_AVATAR = "fx_bubble_avatar"          # 聊天气泡内小头像
FX_IDLE_CHATTER = "fx_idle_chatter"            # 说话气泡（待机自语 + 交互短句反馈）
FX_GREETING = "fx_greeting"                    # 模型就绪时的登场特效
FX_CUTE_CURSOR = "fx_cute_cursor"              # 应用内萌系鼠标指针 + 小拖尾

# (配置键, 设置界面短标签, 默认值)
EFFECTS = (
    (FX_PETALS, "飘落花瓣", True),
    (FX_HEART_BURST, "点击爱心", True),
    (FX_LIVE_BADGE, "LIVE 牌", True),
    (FX_BUBBLE_AVATAR, "气泡头像", True),
    (FX_IDLE_CHATTER, "说话气泡", True),
    (FX_GREETING, "登场特效", True),
    (FX_CUTE_CURSOR, "萌系光标", True),
)

_DEFAULTS = {key: default for key, _label, default in EFFECTS}
# 兼容 v0.1.31 第一批用过的旧键（若用户已手工关闭过）
_LEGACY = {FX_PETALS: "ambient_decor"}
# 语义合并后不再使用的旧配置键（留着无害，但不读取）
DEPRECATED = (
    "ambient_decor", "fx_tray_online", "fx_live_pulse", "fx_time_palette",
    "fx_message_sparkle", "fx_hover_glow", "fx_status_emote",
)


def is_enabled(key: str) -> bool:
    """读取特效开关；未写入过时返回默认值，兼容旧键"""
    default = _DEFAULTS.get(key, True)
    value = cfg.get(key, None)
    if value is None and key in _LEGACY:
        value = cfg.get(_LEGACY[key], None)
    return default if value is None else bool(value)


def set_enabled(key: str, enabled: bool) -> None:
    """写入并持久化特效开关"""
    cfg.set(key, bool(enabled))
