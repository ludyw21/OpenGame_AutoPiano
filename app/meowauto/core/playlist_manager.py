# -*- coding: utf-8 -*-
"""
PlaylistManager: 统一管理播放列表与播放顺序/随机/循环策略。

支持的播放顺序：
- 顺序: 到末尾停止
- 随机: 避免连续重复（若可行）
- 单曲循环: 始终返回当前索引
- 列表循环: 到末尾回到0

条目结构: dict(path: str, type: str)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import os
import random


@dataclass
class PlaylistItem:
    path: str
    type: str  # 如: "MIDI文件"


class PlaylistManager:
    def __init__(self) -> None:
        self.items: List[PlaylistItem] = []
        self.current_index: Optional[int] = None
        self.order_mode: str = "顺序"
        self._last_random_index: Optional[int] = None

    # 基础操作
    def clear(self) -> None:
        self.items.clear()
        self.current_index = None
        self._last_random_index = None

    def add_files(self, paths: List[str], ftype: str = "MIDI文件") -> int:
        added = 0
        for p in paths:
            if not p:
                continue
            # 仅加入存在的文件
            try:
                if os.path.isfile(p):
                    self.items.append(PlaylistItem(path=p, type=ftype))
                    added += 1
            except Exception:
                continue
        if self.current_index is None and self.items:
            self.current_index = 0
        return added

    def remove_by_indices(self, indices: List[int]) -> None:
        if not indices:
            return
        indices = sorted(set(i for i in indices if 0 <= i < len(self.items)), reverse=True)
        for i in indices:
            del self.items[i]
        # 调整 current_index
        if not self.items:
            self.current_index = None
        else:
            if self.current_index is None:
                self.current_index = 0
            else:
                if indices and self.current_index is not None:
                    # 若删除位置在当前之前，当前索引左移
                    shift = sum(1 for i in indices if i < self.current_index)
                    self.current_index = max(0, self.current_index - shift)
                # 若当前索引越界，钳制
                if self.current_index >= len(self.items):
                    self.current_index = len(self.items) - 1

    def remove_by_paths(self, paths: List[str]) -> None:
        if not paths:
            return
        to_remove = set(os.path.abspath(p) for p in paths)
        keep: List[PlaylistItem] = []
        old_items = self.items
        self.items = []
        for it in old_items:
            if os.path.abspath(it.path) not in to_remove:
                self.items.append(it)
        # 调整 current_index
        if not self.items:
            self.current_index = None
        else:
            self.current_index = min(self.current_index or 0, len(self.items) - 1)

    def set_order_mode(self, mode: str) -> None:
        if mode in ("顺序", "随机", "单曲循环", "列表循环"):
            self.order_mode = mode

    def select_index(self, index: int) -> bool:
        if 0 <= index < len(self.items):
            self.current_index = index
            return True
        return False

    def has_items(self) -> bool:
        return len(self.items) > 0

    # 取下一首/上一首
    def next_index(self) -> Optional[int]:
        if not self.items:
            return None
        if self.current_index is None:
            self.current_index = 0
        mode = self.order_mode
        n = len(self.items)

        if mode == "单曲循环":
            return self.current_index
        if mode == "随机":
            if n == 1:
                return 0
            # 避免与当前相同，如不可行则放宽到任意
            candidates = list(range(n))
            if self.current_index in candidates:
                candidates.remove(self.current_index)
            idx = random.choice(candidates) if candidates else random.randrange(n)
            self._last_random_index = idx
            return idx
        if mode == "列表循环":
            return (self.current_index + 1) % n
        # 顺序
        nxt = self.current_index + 1
        return nxt if nxt < n else None

    def prev_index(self) -> Optional[int]:
        if not self.items:
            return None
        if self.current_index is None:
            self.current_index = 0
        mode = self.order_mode
        n = len(self.items)
        if mode == "随机":
            # 简单策略：返回上一次随机，若无则 0
            return self._last_random_index if self._last_random_index is not None else 0
        if mode == "列表循环":
            return (self.current_index - 1) % n
        # 顺序/单曲循环
        prv = self.current_index - 1
        return prv if prv >= 0 else (self.current_index if mode == "单曲循环" else None)

    # 读取当前项
    def current_item(self) -> Optional[PlaylistItem]:
        if self.current_index is None:
            return None
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None
