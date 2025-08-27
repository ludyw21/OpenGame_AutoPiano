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


# ====== 方案A：游戏配置注册表与统一查询 ======

class GameProfile:
    """游戏配置：布局/策略/映射等元信息。"""
    def __init__(self, name: str, layout: str, strategy: str, mapping: Dict[str, str]):
        self.name = name
        self.layout = layout           # e.g. "21-key" / "3x5"
        self.strategy = strategy       # e.g. "strategy_21key" / "strategy_3x5"
        self.mapping = mapping         # 键位映射表


# 预置注册表：集中管理各游戏映射与策略
GAME_REGISTRY: Dict[str, GameProfile] = {
    '开放空间': GameProfile(
        name='开放空间', layout='21-key', strategy='strategy_21key', mapping=get_default_mapping()
    ),
    '原神': GameProfile(
        name='原神', layout='21-key', strategy='strategy_21key', mapping=get_genshin_mapping()
    ),
    # 占位：3x5 布局（后续完善具体映射与策略细节）
    '光遇': GameProfile(
        name='光遇', layout='3x5', strategy='strategy_3x5', mapping={
            # 3x5 共15键：使用三排 qwert/asdfg/zxcvb 占位（从左到右，从上到下）
            'K1': 'q', 'K2': 'w', 'K3': 'e', 'K4': 'r', 'K5': 't',
            'K6': 'a', 'K7': 's', 'K8': 'd', 'K9': 'f', 'K10': 'g',
            'K11': 'z', 'K12': 'x', 'K13': 'c', 'K14': 'v', 'K15': 'b',
        }
    ),
}


def get_game_profile(game_name: str | None) -> GameProfile:
    """按名称获取游戏配置，失败回退到“开放空间”。"""
    try:
        name = (game_name or '').strip()
        if name in GAME_REGISTRY:
            return GAME_REGISTRY[name]
    except Exception:
        pass
    return GAME_REGISTRY['开放空间']


def get_mapping_for_game(game_name: str | None) -> Dict[str, str]:
    return get_game_profile(game_name).mapping


def get_strategy_for_game(game_name: str | None) -> str:
    return get_game_profile(game_name).strategy


