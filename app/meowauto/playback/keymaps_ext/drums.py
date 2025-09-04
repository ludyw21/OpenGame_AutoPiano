# -*- coding: utf-8 -*-
"""
鼓类（Drums）键位映射。

来源：项目内图片 5155917564454292.png
- 1：踩镲闭
- Q：踩镲开
- 2：高音吊镲
- 3：一嗵鼓
- 4：二嗵鼓
- 5：叮叮镲（Ride）
- T：中音吊镲
- W：军鼓
- E：底鼓
- R：落地嗵鼓

说明：
- 使用英文枚举键，提供中文别名映射，避免在代码层面出现环境依赖字符。
- 仅定义按键映射，不做策略逻辑；策略在 midi/partitioner 或 playback/strategies 中实现。
"""
from __future__ import annotations

from typing import Dict

# 主映射（英文键名）
DRUMS_KEYMAP: Dict[str, str] = {
    # cymbals
    "HIHAT_CLOSE": "1",       # 踩镲闭
    "HIHAT_OPEN": "q",        # 踩镲开
    "CRASH_HIGH": "2",        # 高音吊镲
    "RIDE": "5",              # 叮叮镲
    "CRASH_MID": "t",         # 中音吊镲
    # toms & snare & kick
    "TOM1": "3",              # 一嗵鼓
    "TOM2": "4",              # 二嗵鼓
    "FLOOR_TOM": "r",         # 落地嗵鼓
    "SNARE": "w",             # 军鼓
    "KICK": "e",              # 底鼓
}

# 中文别名到英文键名的映射（可选）
ALIASES_ZH: Dict[str, str] = {
    "踩镲闭": "HIHAT_CLOSE",
    "踩镲开": "HIHAT_OPEN",
    "高音吊镲": "CRASH_HIGH",
    "叮叮镲": "RIDE",
    "中音吊镲": "CRASH_MID",
    "一嗵鼓": "TOM1",
    "二嗵鼓": "TOM2",
    "落地嗵鼓": "FLOOR_TOM",
    "军鼓": "SNARE",
    "底鼓": "KICK",
}

__all__ = ["DRUMS_KEYMAP", "ALIASES_ZH"]
