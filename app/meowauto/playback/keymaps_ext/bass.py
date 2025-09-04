# -*- coding: utf-8 -*-
"""
贝斯（Bass）键位映射。

约定：3x7（与钢琴键位的上三行一致）。
此处直接复用默认 21 键的三排布局（数字行 + QWERTY 上排 + ASDFGHJ 行），
对外作为 BASS_KEYMAP 常量提供。
"""
from __future__ import annotations

from typing import Dict

# 直接与钢琴默认 21 键映射保持一致
BASS_KEYMAP: Dict[str, str] = {
    'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
    'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
    'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7',
}

__all__ = ["BASS_KEYMAP"]
