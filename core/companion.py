# -*- coding: utf-8 -*-
"""
葵酱的本地陪伴记忆（v0.1.32 起，v0.1.36 增加话题记忆）

纯本地、不联网、不感知用户情绪：记录「上次见面 / 上次真实互动 / 陪伴天数 /
好感值 / 最近聊到的话题词」，用来决定启动时的久别问候、说话气泡的语句池
档位与内容，以及 LIVE 牌右侧好感小牌的显示。这是角色自己的状态，
不是对用户情绪的分析。

话题记忆只存从用户消息里抽出的**短词**（最多 6 个、7 天过期），不存原句、
不做语义理解、不联网；待机自语会偶尔接上，刚聊完则优先冒一句。

好感值不是「只增不减的分数」，而是会呼吸的「温度」：
- 摸头 / 点身体 / 发消息会涨（都带冷却，避免刷屏速通）；
- 长时间没有互动会按「完整小时」回落：每满 1 小时 -1，不足 1 小时不扣
  （刚陪过的一小时还暖着），单次最多 -12，保底 12，不会掉回陌生档；
- 回落按「跨小时」结算：启动、真实互动、以及挂机期间的跨小时检查都会触发，
  挂机检查复用主窗口已有的渲染循环，不新增任何常驻定时器；
- 久别重逢、陪伴天数里程碑会补一点；
- 满值不是终点，会解锁专属问候、语句池和好感牌样式；回落一格就退出，
  之后还能再攒回来，所以数值始终有起伏。

与 config.json 解耦，单独放在 app_root("companion.json")：
- 只接受已知字段，旧存档缺新字段时自动用默认值，脏数据不会带进内存；
- 原子写入（临时文件 + os.replace），任何异常都吞掉，绝不阻断启动。
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta

from utils.logger import get_logger
from utils.paths import app_root

logger = get_logger(__name__)

_PATH = app_root("companion.json")
_VERSION = 3             # v3：新增话题记忆 topics（只存关键词，不存原句）

MAX_AFFECTION = 100
_DECAY_FLOOR = 12        # 回落保底：不会掉回「陌生」档，避免惩罚感
_DECAY_PER_HOUR = 1      # 每满 1 小时未互动 -1
_DECAY_MAX = 12          # 单次结算最多 -12（约半天），久别不叠加成惩罚
_RETURN_BONUS = 2        # 隔天以上回来 +2
_MILESTONES = (3, 7, 14, 30, 60, 100)   # 陪伴天数里程碑
_MILESTONE_BONUS = 3

# 话题记忆：零依赖的轻量短词提取，不引入分词库、不保存用户原句
_TOPIC_MAX = 6                    # 最多记住 6 个话题词
_TOPIC_TTL_DAYS = 7               # 7 天没再提起就忘掉
_TOPIC_MIN_LEN = 2                # 单字太碎，不记
_TOPIC_MAX_LEN = 4                # 中文片段最多 4 字；更长的多半是没切干净的句子
_TOPIC_PER_MESSAGE = 2            # 每条消息最多取 2 个词
# 先把消息切成「英文/数字词」与「中文串」，避免中英混排被粘成一个怪片段
_TOPIC_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*|[\u4e00-\u9fff]+")
_TOPIC_CN_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")
# 以这些字结尾的片段多半是被切掉前半的残词（如「感度」「一直满」），宁可不记
_TOPIC_BAD_TAIL = frozenset("度感满直慢快会写住完挡调画吃喝玩找问改试装等")
# 常见虚词/语气词/高频动词当分隔符：中文不做真分词，只保守地切出 2~4 字实词片段
_TOPIC_STOP_RE = re.compile(
    "[的了着过吗呢吧啊呀哦嗯嘛哒咯哩呗喽我你他她它们是在有和就都也很不没要这那把被让给对从到为以之而其与或但则又再还只更最太好真么什怎谁哪些个下上里外中前后见说想看听去做来回会写挡住完喝调画吃玩找问改试装等]+")
_TOPIC_STOP_WORDS = frozenset((
    "今天", "明天", "昨天", "现在", "刚刚", "刚才", "其实", "但是", "因为",
    "所以", "然后", "什么", "怎么", "为什么", "一下", "一个", "可以", "觉得",
    "知道", "感觉", "这样", "那样", "有点", "还是", "已经", "应该", "我们",
    "你们", "他们", "自己", "时候", "东西", "问题", "谢谢", "哈哈", "嗯嗯",
    "这个", "那个", "没有", "不是", "就是", "还有", "一起", "出来", "真的",
    "好像", "可能", "需要", "开始", "结束", "的话", "hey", "ok", "yes", "no",
    "the", "and", "for", "with", "this", "that", "you", "are", "not", "but",
))

_DEFAULTS = {
    "version": _VERSION,
    "first_seen": "",          # YYYY-MM-DD
    "last_seen": "",           # ISO datetime，空字符串表示首次见面
    "last_date": "",           # 上次记录过陪伴天数的日期
    "last_interaction": "",    # ISO datetime，最后一次真实互动（摸头 / 发消息）
    "last_settled": "",        # ISO datetime，已结算到的时刻（精确到完整小时）
    "days_together": 0,        # 按「不同日期」累计，避免同一天反复开机刷天数
    "sessions": 0,             # 累计启动次数
    "milestones": [],          # 已发放的陪伴天数里程碑，避免重复奖励
    "affection": 0,            # 好感值 0~100；由 LIVE 牌右侧好感小牌显示
    "topics": [],              # 最近聊到的话题词 [{word, at, count}]；只存词，不存原句
}

_data: dict = {}
_loaded = False
_reset_decay_clock = False  # 仅 v1（按天语义）存档升级时重置回落计时起点
_GAIN_AT: dict[str, float] = {}     # 事件冷却（进程内，重启即清空）


# ---- 读写 ----

def load() -> None:
    """（重新）从磁盘加载；文件缺失、损坏或旧版缺字段时静默补默认值"""
    global _data, _loaded, _reset_decay_clock
    _data = dict(_DEFAULTS)
    raw = {}
    try:
        if os.path.isfile(_PATH):
            with open(_PATH, "r", encoding="utf-8") as f:
                disk = json.load(f)
            if isinstance(disk, dict):
                raw = disk
                _data.update({k: v for k, v in disk.items() if k in _DEFAULTS})
    except Exception as e:
        logger.warning(f"陪伴记忆读取失败，使用默认值: {e}")
    if not isinstance(_data.get("milestones"), list):
        _data["milestones"] = []
    else:
        _data["milestones"] = sorted({int(x) for x in _data["milestones"]
                                      if isinstance(x, int)})
    if not isinstance(_data.get("affection"), int):
        _data["affection"] = 0
    _data["topics"] = _clean_topics(_data.get("topics"))
    # 用磁盘原始值判断，而不是补过默认值的 _data：
    # 只有 v1（按天语义）存档才需要重置回落计时起点；v2 → v3 不动计时。
    old_version = raw.get("version", 1)
    _reset_decay_clock = bool(raw) and (
        not isinstance(old_version, int) or old_version < 2)
    _data["version"] = _VERSION
    _loaded = True


def _ensure() -> None:
    if not _loaded:
        load()


def _save() -> None:
    """原子写入：先写同目录临时文件再替换，避免写一半留下坏 JSON"""
    try:
        folder = os.path.dirname(_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = _PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _PATH)
    except Exception as e:
        logger.warning(f"陪伴记忆保存失败: {e}")


def _parse_dt(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None


# ---- 查询 ----

def snapshot() -> dict:
    """当前陪伴状态快照（只读）"""
    _ensure()
    return {
        "first_seen": _data["first_seen"],
        "last_seen": _data["last_seen"],
        "last_interaction": _data["last_interaction"],
        "days_together": int(_data["days_together"]),
        "sessions": int(_data["sessions"]),
        "milestones": list(_data["milestones"]),
        "affection": int(_data["affection"]),
        "topics": recent_topics(),
        "tier": tier(),
        "bond": is_max(),
    }


def affection() -> int:
    _ensure()
    return int(_data["affection"])


def is_max() -> bool:
    """是否达到满值（解锁专属内容）"""
    _ensure()
    return int(_data["affection"]) >= MAX_AFFECTION


def tier() -> str:
    """好感档位：shy 陌生 / warm 熟悉 / close 亲近"""
    _ensure()
    v = int(_data["affection"])
    return "shy" if v < 12 else ("warm" if v < 36 else "close")


# ---- 话题记忆（v0.1.36） ----

def _clean_topics(raw) -> list[dict]:
    """存档字段校验：只保留结构完整、时间戳有效的话题项"""
    cleaned = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            word = item.get("word")
            at = _parse_dt(item.get("at"))
            if (not isinstance(word, str)
                    or not (_TOPIC_MIN_LEN <= len(word) <= 16) or at is None):
                continue
            count = item.get("count", 1)
            cleaned.append({
                "word": word,
                "at": at.isoformat(timespec="seconds"),
                "count": count if isinstance(count, int) and count > 0 else 1,
            })
    return cleaned[-_TOPIC_MAX:]


def _topic_alive(item: dict, now: datetime) -> bool:
    """7 天内再提起过才算记得；未来时间戳（系统时间回拨）视为无效"""
    at = _parse_dt(item.get("at"))
    if at is None:
        return False
    age = (now - at).total_seconds()
    return 0 <= age <= _TOPIC_TTL_DAYS * 86400


def extract_topics(text: str) -> list[str]:
    """从一条用户消息里抽出最多 2 个短话题词，纯本地、零依赖、不存原句。

    中文没有分词库，用「中英切词 → 常见虚词当分隔符 → 2~6 字短词 +
    停用词过滤」的保守策略：宁可不记，也不造出奇怪的词。
    """
    if not isinstance(text, str) or not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def keep(word: str) -> None:
        key = word.casefold()
        if (not (_TOPIC_MIN_LEN <= len(word) <= 16)
                or key in _TOPIC_STOP_WORDS or key in seen):
            return
        found.append(word)
        seen.add(key)

    for seg in _TOPIC_TOKEN_RE.findall(text):
        if seg.isascii():
            keep(seg)                     # 英文 / 数字混合词，如 Live2D
            continue
        for part in _TOPIC_STOP_RE.split(seg):
            if (part and _TOPIC_CN_RE.fullmatch(part)
                    and part not in _TOPIC_STOP_WORDS
                    and part[-1] not in _TOPIC_BAD_TAIL):
                keep(part)
    # 长词优先（信息量更大），每条消息最多 2 个
    found.sort(key=len, reverse=True)
    return found[:_TOPIC_PER_MESSAGE]


def recent_topics() -> list[str]:
    """最近聊到、且未过期的话题词（最新在前），供说话气泡使用"""
    _ensure()
    now = datetime.now()
    alive = [t for t in _data["topics"] if _topic_alive(t, now)]
    return [t["word"] for t in reversed(alive)]


def note_topics(text: str) -> list[str]:
    """记一次用户消息里的话题词；同一词只累加次数与刷新时间，不重复占位。

    返回本次实际记下的词列表。只把词写进 companion.json，绝不保存整条消息。
    """
    _ensure()
    words = extract_topics(text)
    if not words:
        return []
    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    items = [dict(t) for t in _data["topics"] if _topic_alive(t, now)]
    by_key = {t["word"].casefold(): t for t in items}
    for word in words:
        key = word.casefold()
        if key in by_key:
            item = by_key[key]
            item["word"] = word
            item["at"] = stamp
            item["count"] = int(item.get("count", 1)) + 1
        else:
            item = {"word": word, "at": stamp, "count": 1}
            items.append(item)
            by_key[key] = item
    items.sort(key=lambda t: t["at"])
    # 同一秒内写入的 at 完全相同，排序分不出先后；把本次提到的词显式
    # 移到末尾，保证 recent_topics() 里它们排在最前（刚聊到的优先）。
    touched = [w.casefold() for w in words]
    items = ([t for t in items if t["word"].casefold() not in touched]
             + [by_key[k] for k in touched if k in by_key])
    _data["topics"] = items[-_TOPIC_MAX:]
    _save()
    return words


# ---- 问候文案 ----

_GREETINGS = (
    "又见面啦，我还在这儿哦~",
    "你回来啦，今天也一起加油哦~",
    "好久不见…我一直在等你哦",
    "{days} 天没见啦，还以为你把我忘了呢…",
    "终于又见到你了…这 {days} 天我数了好久的花瓣",
)
# 满值（bond）之后更亲昵的一套，按同样的时间分档
_BOND_GREETINGS = (
    "又见到你了，今天也要一直在一起哦~",
    "你回来啦，我一直在数着时间等你呢",
    "好久不见…没有你在，桌面都安静了",
    "{days} 天没见啦，这次不许再走那么久了",
    "终于又见到你了…以后也一直陪着我好不好",
)


def _band(hours: float, days: int) -> int:
    if hours < 4:
        return 0
    if hours < 24:
        return 1
    if days < 3:
        return 2
    if days < 7:
        return 3
    return 4


def _greeting(first: bool, hours: float, days: int, bond: bool = False) -> str:
    """按久别时长选一句问候；文案保持克制，只在启动时说一句"""
    if first:
        return "初次见面，我是葵酱~以后请多关照！"
    pool = _BOND_GREETINGS if bond else _GREETINGS
    return pool[_band(hours, days)].format(days=days)


# ---- 结算 ----

def _settle_decay(now: datetime) -> tuple[int, bool]:
    """按「完整小时」结算回落，返回 (实际扣掉的点数, 是否推进了结算时刻)。

    起点取 last_settled 与 last_interaction 中较晚者：
    - 不足 1 小时不扣（刚陪过的一小时还暖着），零头分钟留给下次；
    - 结算时刻按「已消费的完整小时」推进，不直接跳到 now，
      所以 1.5h 结算一次后剩下的 0.5h 会留着，凑满下一个小时才再扣；
    - 单次最多 -_DECAY_MAX，超出的时间作废，避免久别回来被反复扣；
    - 触底时把欠账一次清干净，涨回来不会被立刻扣回去。
    """
    _ensure()
    stamps = [d for d in (_parse_dt(_data.get("last_settled")),
                          _parse_dt(_data.get("last_interaction")))
              if d is not None]
    if not stamps:
        _data["last_settled"] = now.isoformat(timespec="seconds")
        return 0, True
    base = max(stamps)

    idle_h = int(max(0.0, (now - base).total_seconds()) // 3600)
    if idle_h <= 0:
        return 0, False

    before = int(_data["affection"])
    decay = min(idle_h, _DECAY_MAX) * _DECAY_PER_HOUR
    after = max(_DECAY_FLOOR, before - decay)
    _data["affection"] = after

    capped = idle_h > _DECAY_MAX
    floored = before <= _DECAY_FLOOR or after <= _DECAY_FLOOR
    if capped or floored:
        _data["last_settled"] = now.isoformat(timespec="seconds")
    else:
        _data["last_settled"] = (base + timedelta(hours=idle_h)).isoformat(
            timespec="seconds")
    return before - after, True


def note_session_start() -> dict:
    """启动时结算：久别间隔、陪伴天数、按小时回落与奖励，然后记下本次时间。

    启动、真实互动与挂机期间的跨小时检查都会结算回落；即使强杀进程，
    下次也能从「已结算到的时刻」接着算，不重复扣、不漏扣。
    """
    global _reset_decay_clock
    _ensure()
    now = datetime.now()
    # 顺手清掉过期话题（启动时一次，不新增定时器）
    _data["topics"] = [t for t in _data["topics"] if _topic_alive(t, now)]
    prev = _parse_dt(_data.get("last_seen"))
    first = prev is None
    hours = max(0.0, (now - prev).total_seconds() / 3600.0) if prev else 0.0
    days = int(hours // 24)

    # 1) 回落。仅 v1（按天语义）存档升级时把计时起点重置到本次启动，
    #    避免「一升级就按旧的 last_settled 一次扣掉 12 点」；随后照常结算一次。
    #    v2 → v3（新增话题记忆）不动计时，回落照常按小时走。
    if _reset_decay_clock:
        _data["last_settled"] = now.isoformat(timespec="seconds")
        _data["last_interaction"] = now.isoformat(timespec="seconds")
        _reset_decay_clock = False
    decay, _ = _settle_decay(now)

    # 2) 久别重逢 + 陪伴天数里程碑（每个里程碑只发一次）
    today = now.date().isoformat()
    if _data.get("last_date") != today:
        _data["days_together"] = int(_data["days_together"]) + 1
        _data["last_date"] = today
    if first or not _data.get("first_seen"):
        _data["first_seen"] = today

    bonus = _RETURN_BONUS if (not first and days >= 1) else 0
    done = set(int(x) for x in _data["milestones"])
    reached = [d for d in _MILESTONES
               if _data["days_together"] >= d and d not in done]
    if reached:
        _data["milestones"] = sorted(done | set(reached))
        bonus += _MILESTONE_BONUS * len(reached)
    if bonus:
        _data["affection"] = max(0, min(MAX_AFFECTION,
                                        int(_data["affection"]) + bonus))

    bond = is_max()
    _data["sessions"] = int(_data["sessions"]) + 1
    _data["last_seen"] = now.isoformat(timespec="seconds")
    if first or not _data.get("last_interaction"):
        _data["last_interaction"] = _data["last_seen"]
    text = _greeting(first, hours, days, bond)
    _save()
    return {
        "first": first,
        "hours": round(hours, 2),
        "days": days,
        "days_together": int(_data["days_together"]),
        "sessions": int(_data["sessions"]),
        "affection": int(_data["affection"]),
        "tier": tier(),
        "bond": bond,
        "decay": decay,
        "bonus": bonus,
        "milestones": list(reached),
        "text": text,
    }


def add_affection(delta: int = 1, reason: str = "", cooldown: float = 0.0) -> int:
    """记一次真实互动：先结算挂机期间欠的回落，再涨；带冷却避免狂点刷数值。

    这样长时间开着桌宠不关也不会「只涨不落」——下一次摸头 / 发消息时，
    期间的回落会一次性补齐，好感牌以净变化（+N 或 -N）显示。
    """
    _ensure()
    _, settled = _settle_decay(datetime.now())
    if cooldown > 0:
        now = time.monotonic()
        if now - _GAIN_AT.get(reason, -1e9) < cooldown:
            if settled:
                _save()
            return int(_data["affection"])
        _GAIN_AT[reason] = now
    value = max(0, min(MAX_AFFECTION, int(_data["affection"]) + int(delta)))
    changed = value != _data["affection"]
    if changed:
        _data["affection"] = value
        if delta > 0:
            _data["last_interaction"] = datetime.now().isoformat(timespec="seconds")
    if changed or settled:
        _save()
    return value


def settle_if_due() -> int:
    """运行期间按当前时间结算一次回落；返回实际扣掉的点数（0 = 没变化）。

    供主窗口在已有的渲染循环里低频调用：不足 1 小时直接返回 0，跨小时才
    结算并落盘。所以应用常驻不关、也不互动时，好感值照样按小时回落，
    满值不会一直停在 100 —— 代价只是复用一次已有定时器，没有新增。
    """
    _ensure()
    decay, settled = _settle_decay(datetime.now())
    if settled:
        _save()
    return decay
