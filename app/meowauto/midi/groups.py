"""
Piano pitch groups and helper utilities.
Groups are defined in MIDI note numbers.
"""
from typing import Dict, Tuple, List

# MIDI note numbers: A₂=21, c¹=60 (中央C), c⁵=108
# 按照标准钢琴音域定义音组 (21..108)
GROUPS: Dict[str, Tuple[int, int]] = {
    "大字二组 (A₂-B₂)": (21, 23),
    "大字一组 (C₁-B₁)": (24, 35),
    "大字组 (C-B)": (36, 47),
    "小字组 (c-b)": (48, 59),
    "小字一组 (c¹-b¹)": (60, 71),
    "小字二组 (c²-b²)": (72, 83),
    "小字三组 (c³-b³)": (84, 95),
    "小字四组 (c⁴-b⁴)": (96, 107),
    "小字五组 (c⁵)": (108, 108),
}

ORDERED_GROUP_NAMES: List[str] = list(GROUPS.keys())


def group_for_note(note: int) -> str:
    for name, (lo, hi) in GROUPS.items():
        if lo <= note <= hi:
            return name
    return "未知"


def filter_notes_by_groups(notes: List[dict], selected_groups: List[str]) -> List[dict]:
    if not selected_groups:
        return notes
    ranges = [GROUPS[name] for name in selected_groups if name in GROUPS]
    if not ranges:
        return notes
    out = []
    for ev in notes:
        n = ev.get('note')
        if n is None:
            out.append(ev)
            continue
        for lo, hi in ranges:
            if lo <= n <= hi:
                out.append(ev)
                break
    return out
