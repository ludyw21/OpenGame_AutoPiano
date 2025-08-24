"""
Piano pitch groups and helper utilities.
Groups are defined in MIDI note numbers.
"""
from typing import Dict, Tuple, List

# MIDI note numbers: A0=21, C4=60, C8=108
# We define groups to cover the full 88-key range (21..108)
GROUPS: Dict[str, Tuple[int, int]] = {
    "大字二组 (A0-B0)": (21, 23),
    "大字组 (C1-B1)": (24, 35),
    "小字组 (C2-B2)": (36, 47),
    "小字一组 (C3-B3)": (48, 59),
    "小字二组 (C4-B4)": (60, 71),
    "小字三组 (C5-B5)": (72, 83),
    "小字四组 (C6-B6)": (84, 95),
    "小字五组 (C7-C8)": (96, 108),
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
