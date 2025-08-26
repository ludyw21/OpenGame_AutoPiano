"""
键位映射表与获取函数。

提供默认21键映射与原神21键映射：
- 默认(开放空间)：
  L1-L7 -> a s d f g h j
  M1-M7 -> q w e r t y u
  H1-H7 -> 1 2 3 4 5 6 7

- 原神：
  L1-L7 -> z x c v b n m
  M1-M7 -> a s d f g h j
  H1-L7 -> q w e r t y u
"""

from __future__ import annotations

from typing import Dict


def get_default_mapping() -> Dict[str, str]:
    return {
        'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
        'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
        'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7',
    }


def get_genshin_mapping() -> Dict[str, str]:
    return {
        'L1': 'z', 'L2': 'x', 'L3': 'c', 'L4': 'v', 'L5': 'b', 'L6': 'n', 'L7': 'm',
        'M1': 'a', 'M2': 's', 'M3': 'd', 'M4': 'f', 'M5': 'g', 'M6': 'h', 'M7': 'j',
        'H1': 'q', 'H2': 'w', 'H3': 'e', 'H4': 'r', 'H5': 't', 'H6': 'y', 'H7': 'u',
    }


def get_game_key_mapping(game_name: str | None) -> Dict[str, str]:
    """根据游戏名称返回对应21键位映射。

    参数中的 `game_name` 允许 None；默认返回开放空间映射。
    识别：'原神' -> 原神映射；其它 -> 默认映射。
    """
    try:
        name = (game_name or '').strip()
        if name == '原神':
            return get_genshin_mapping()
        return get_default_mapping()
    except Exception:
        return get_default_mapping()


