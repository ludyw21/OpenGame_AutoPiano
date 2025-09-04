# -*- coding: utf-8 -*-
"""
吉他（Guitar）键位映射。

与钢琴 21 键位一致，并预留和弦键的使用（和弦逻辑在上层 AutoPlayer/ChordEngine）。
"""
from __future__ import annotations

from typing import Dict

GUITAR_KEYMAP: Dict[str, str] = {
    'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
    'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
    'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7',
}

__all__ = ["GUITAR_KEYMAP"]
