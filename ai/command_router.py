# -*- coding: utf-8 -*-
"""
斜杠指令本地路由
- 识别 /keyword args 格式的指令
- 本地硬编码处理，不经过 LLM
- 当前支持：/成绩 <歌曲名>
"""
import re
from collections import defaultdict
from difflib import SequenceMatcher

from core.file_manager import FileManager
from utils.logger import get_logger

logger = get_logger(__name__)

# 评价等级映射
_RANK_NAMES = {
    1: "无",
    2: "白粋",
    3: "铜粋",
    4: "银粋",
    5: "金雅",
    6: "粉雅",
    7: "紫雅",
    8: "极",
}


def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度（0~1）"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class CommandRouter:
    """
    斜杠指令路由器
    所有指令本地处理，不调用 LLM
    """

    def __init__(self, file_manager: FileManager):
        self._file_mgr = file_manager

    def handle(self, text: str) -> str | None:
        """
        处理斜杠指令
        :param text: 用户输入文本
        :return: 回复文本；返回 None 表示不是指令，应走普通聊天流程
        """
        text = text.strip()
        if not text.startswith("/"):
            return None

        match = re.match(r"/(\w+)\s*(.*)", text)
        if not match:
            return None

        keyword, args = match.groups()
        args = args.strip()

        if keyword == "成绩":
            return self._handle_score(args)

        return f"葵酱：未知指令 /{keyword}，暂时还不认识呢~\n可用指令：/成绩 <歌曲名>"

    # ---- 指令实现 ----

    def _handle_score(self, song_query: str) -> str:
        """查询太鼓达人成绩"""
        if not song_query:
            return "葵酱：请输入歌曲名哦~\n用法：/成绩 <歌曲名>"

        if not self._file_mgr.has_taiko_file:
            return (
                "葵酱：还没有上传成绩文件呢~\n"
                "请先点击输入框右侧的 📎 按钮上传 taiko_scores_*.json 文件！"
            )

        data = self._file_mgr.get_current_taiko_data()
        if not data:
            return "葵酱：成绩文件读取失败，请检查文件格式是否正确。"

        song_query_lower = song_query.lower()
        matched_items = []

        for item in data:
            detail = item.get("song_detail")
            if not detail:
                continue
            names = [
                detail.get("song_name", ""),
                detail.get("song_name_jp", ""),
                detail.get("subtitle", ""),
            ]
            for name in names:
                if not name:
                    continue
                sim = _similarity(song_query_lower, name)
                if sim >= 0.5 or song_query_lower in name.lower():
                    matched_items.append((sim, item))
                    break

        if not matched_items:
            return f"葵酱：没有找到歌曲「{song_query}」的成绩呢~\n再检查一下歌名？"

        # 按 song_name_jp 分组（同一首歌的不同难度记录）
        songs = defaultdict(list)
        for sim, item in matched_items:
            detail = item.get("song_detail", {})
            key = detail.get("song_name_jp", detail.get("song_name", ""))
            songs[key].append((sim, item))

        # 取相似度最高的歌曲
        best_song = max(songs.items(), key=lambda kv: max(s[0] for s in kv[1]))
        song_name_jp, song_items = best_song

        # 收集该歌曲 level 4/5 的所有记录
        records = {}
        for sim, item in song_items:
            level = item.get("level")
            if level not in (4, 5):
                continue
            # 同一难度保留最高分记录
            if level not in records or item["high_score"] > records[level]["high_score"]:
                records[level] = item

        detail = song_items[0][1].get("song_detail", {})

        if not records:
            # 没有 level 4/5，退而显示匹配到的第一条
            item = song_items[0][1]
            return self._format_single_score(item, detail)

        if len(records) == 1:
            item = next(iter(records.values()))
            return self._format_single_score(item, detail)

        return self._format_multi_score(records, detail)

    def _format_song_header(self, detail: dict) -> list[str]:
        """格式化歌曲头部信息（歌名 + 分类）"""
        song_jp = detail.get("song_name_jp", "")
        song_name = detail.get("song_name", "")

        lines = [f"🎵 {song_jp}"]
        lines.append(f"🎵 （{song_name}）")

        genre = detail.get("type", "未知")
        lines.append(f"📂 分类：{genre}")
        return lines

    def _format_score_block(self, item: dict, detail: dict, has_both: bool = False) -> list[str]:
        """格式化单个难度的成绩块"""
        level = item.get("level", 4)
        level_value = detail.get(f"level_{level}", "-")

        if level == 4:
            level_name = "魔王(表)" if has_both else "魔王"
        else:
            level_name = "魔王(裏)"

        rank_num = item.get("best_score_rank", 1)
        rank_name = _RANK_NAMES.get(rank_num, f"段位{rank_num}")

        # history 解析：[游玩, 通关, 全连, 全良]
        history = item.get("history", [])
        if len(history) >= 4:
            play_count, clear_count, fc_count, ap_count = history[0], history[1], history[2], history[3]
        elif len(history) >= 2:
            # 旧格式兼容，只有全连和全良
            play_count, clear_count = 0, 0
            fc_count, ap_count = history[0], history[1]
        else:
            play_count = clear_count = fc_count = ap_count = 0

        lines = [
            f"🎚️  难度：{level_name}({level_value}星)",
            f"🏆 得分：{item['high_score']}",
            f"🥇 评价：{rank_name}",
        ]

        if play_count > 0:
            lines.append(f"🎮 游玩次数：{play_count}次")
        if clear_count > 0:
            lines.append(f"🚩 通关次数：{clear_count}次")
        if fc_count > 0:
            lines.append(f"🆒 全连次数：{fc_count}次")
        if ap_count > 0:
            lines.append(f"🔥  全良次数：{ap_count}次")

        date = item.get("highscore_datetime", "未知")[:10]
        lines.append(f"📅 最佳记录：{date}")

        return lines

    def _format_single_score(self, item: dict, detail: dict) -> str:
        """单难度成绩格式化"""
        lines = [
            "🥁 太鼓达人成绩查询",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        lines.extend(self._format_song_header(detail))
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.extend(self._format_score_block(item, detail))
        return "\n".join(lines)

    def _format_multi_score(self, records: dict, detail: dict) -> str:
        """多难度（表+裏）成绩格式化"""
        lines = [
            "🥁 太鼓达人成绩查询",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        lines.extend(self._format_song_header(detail))

        # 按难度顺序显示：表(4) 在前，裏(5) 在后
        for level in (4, 5):
            if level not in records:
                continue
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.extend(self._format_score_block(records[level], detail, has_both=True))

        return "\n".join(lines)
