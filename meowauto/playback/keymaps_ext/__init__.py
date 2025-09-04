# -*- coding: utf-8 -*-
"""
扩展键位映射集合：鼓/贝斯/吉他。

仅提供常量，不引入运行时依赖，供上层策略自由组合。
"""
from .drums import DRUMS_KEYMAP
from .bass import BASS_KEYMAP
from .guitar import GUITAR_KEYMAP

__all__ = [
    "DRUMS_KEYMAP",
    "BASS_KEYMAP",
    "GUITAR_KEYMAP",
]
