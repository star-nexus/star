"""
战况记录组件
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import time
from framework import SingletonComponent


@dataclass
class BattleLogEntry:
    """战况记录条目"""

    timestamp: float = field(default_factory=time.time)
    message: str = ""
    log_type: str = "info"  # "info", "combat", "movement", "death", "turn"
    faction: str = ""
    color: tuple = (255, 255, 255)  # 文本颜色


@dataclass
class BattleLog(SingletonComponent):
    """战况记录单例组件"""

    entries: List[BattleLogEntry] = field(default_factory=list)
    max_entries: int = 100  # 最大记录数
    show_log: bool = True  # 是否显示战况栏
    scroll_offset: int = 0  # 滚动偏移量
    visible_lines: int = 8  # 可见行数

    def add_entry(
        self,
        message: str,
        log_type: str = "info",
        faction: str = "",
        color: tuple = (255, 255, 255),
    ):
        """添加战况记录"""
        entry = BattleLogEntry(
            message=message, log_type=log_type, faction=faction, color=color
        )

        self.entries.append(entry)

        # 限制最大记录数
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        # 自动滚动到最新记录
        self.scroll_to_bottom()

    def scroll_up(self):
        """向上滚动"""
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        """向下滚动"""
        max_scroll = max(0, len(self.entries) - self.visible_lines)
        if self.scroll_offset < max_scroll:
            self.scroll_offset += 1

    def scroll_to_bottom(self):
        """滚动到底部"""
        self.scroll_offset = max(0, len(self.entries) - self.visible_lines)

    def get_visible_entries(self) -> List[BattleLogEntry]:
        """获取当前可见的记录"""
        if not self.entries:
            return []

        start_idx = self.scroll_offset
        end_idx = min(start_idx + self.visible_lines, len(self.entries))
        return self.entries[start_idx:end_idx]

    def get_recent_entries(self, count: int = 10) -> List[BattleLogEntry]:
        """获取最近的记录"""
        return self.entries[-count:] if self.entries else []

    def clear(self):
        """清空记录"""
        self.entries.clear()
        self.scroll_offset = 0
        self.entries.clear()
