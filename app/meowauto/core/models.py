#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core data models for MeowField AutoPiano.

This module contains the fundamental data structures used throughout the application.
"""

import keyboard
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Event:
    """乐谱事件"""
    start: float          # 按下时间（秒）
    end: float            # 释放时间（秒），若与 start 相同表示立刻松开（tap）
    keys: List[str]       # 同步触发的一组按键（和弦/多音）


class KeySender:
    """按键发送器，管理按键状态"""
    
    def __init__(self):
        self.active_count: Dict[str, int] = {}
    
    def press(self, keys: List[str]):
        """按下按键"""
        for k in keys:
            if not k:  # 跳过空键
                continue
            cnt = self.active_count.get(k, 0) + 1
            self.active_count[k] = cnt
            if cnt == 1:  # 首次按下
                try:
                    keyboard.press(k)
                except Exception:
                    pass
    
    def release(self, keys: List[str]):
        """释放按键"""
        for k in keys:
            if not k:  # 跳过空键
                continue
            cnt = self.active_count.get(k, 0)
            if cnt <= 0:
                continue
            cnt -= 1
            self.active_count[k] = cnt
            if cnt == 0:
                try:
                    keyboard.release(k)
                except Exception:
                    pass
    
    def release_all(self):
        """释放所有按键"""
        for k in list(self.active_count.keys()):
            while self.active_count.get(k, 0) > 0:
                self.release([k]) 