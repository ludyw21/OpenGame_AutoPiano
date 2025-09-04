# -*- coding: utf-8 -*-
"""
按键谱导出工具
- 从 (start_time, midi_note) 的行数据与和弦时间索引生成按键谱文本
- 规则与 app.py 中原实现保持一致，集中到此工具模块，便于复用与维护
"""
from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

# 键位映射
_LOW = {'1': 'a', '2': 's', '3': 'd', '4': 'f', '5': 'g', '6': 'h', '7': 'j'}
_MID = {'1': 'q', '2': 'w', '3': 'e', '4': 'r', '5': 't', '6': 'y', '7': 'u'}
_HIGH = {'1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7'}

_CHORD_KEYS_ORDER = ['C', 'Dm', 'Em', 'F', 'G', 'Am', 'G7']
_CHORD_MAP = {'C': 'z', 'Dm': 'x', 'Em': 'c', 'F': 'v', 'G': 'b', 'Am': 'n', 'G7': 'm'}


def _midi_to_reg_deg(n: int) -> Tuple[str, str]:
    """将 MIDI 音高映射为 (区间 L/M/H, 度数 '1'..'7')，按 C 大调白键就近规则。
    - < C4: L（低音区）
    - C4..B4: M（中音区）
    - >= C5: H（高音区）
    黑键就近映射到最近白键度数。
    """
    pc = n % 12
    white_map = {0: '1', 2: '2', 4: '3', 5: '4', 7: '5', 9: '6', 11: '7'}
    if pc not in white_map:
        for d in (1, -1, 2, -2):
            cand = (pc + d) % 12
            if cand in white_map:
                pc = cand
                break
    deg = white_map.get(pc, '1')
    if n < 60:
        reg = 'L'
    elif n <= 71:
        reg = 'M'
    else:
        reg = 'H'
    return reg, deg


def _to_key(reg: str, deg: str) -> str:
    if reg == 'L':
        return _LOW.get(deg, 'a')
    if reg == 'M':
        return _MID.get(deg, 'q')
    return _HIGH.get(deg, '1')


def build_key_notation(
    rows: Iterable[Tuple[float, int]],
    chords_by_time: Dict[float, Set[str]] | Dict[float, Iterable[str]],
    unit: float = 0.3,
) -> str:
    """从行数据生成按键谱文本。

    参数:
    - rows: 形如 (start_time_seconds, midi_note) 的可迭代序列，仅 note_on 事件
    - chords_by_time: {rounded_time: set(['C','Dm',...])}
    - unit: 空格粒度（秒）。两个相邻时间点的间隔会按 round(delta/unit) 生成空格，至少 1 个空格

    返回:
    - 文本内容（不包含换行）
    """
    # 归桶并排序（按同一时间聚合）
    bucket: Dict[float, List[int]] = defaultdict(list)
    for st, n in rows:
        bucket[round(float(st), 6)].append(int(n))
    times = sorted(bucket.keys())

    parts: List[str] = []
    last_t = None
    for t in times:
        if last_t is not None:
            delta = max(0.0, float(t) - float(last_t))
            spaces = int(round(delta / max(1e-6, unit)))
            parts.append(' ' * max(1, spaces))
        # 本刻键位：先和弦键，再音符键
        keys: List[str] = []
        present_chords = [c for c in _CHORD_KEYS_ORDER if c in set(chords_by_time.get(t, set()))]
        for cname in present_chords:
            k = _CHORD_MAP.get(cname)
            if k:
                keys.append(k)
        chord_notes = sorted(bucket[t])
        for n in chord_notes:
            reg, deg = _midi_to_reg_deg(n)
            keys.append(_to_key(reg, deg))
        token = ''.join(keys)
        if len(keys) > 1:
            parts.append(f"[{token}")
            parts.append("]")
        else:
            parts.append(token)
        last_t = t

    return ''.join(parts)
