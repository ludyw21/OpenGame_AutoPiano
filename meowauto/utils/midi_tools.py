"""
MIDI preprocessing utilities: time quantization and black-key transposition.
"""
from typing import List, Dict, Any, Optional

BLACK_PCS = {1, 3, 6, 8, 10}
WHITE_PCS = [0, 2, 4, 5, 7, 9, 11]


def _nearest_white_pc(pc: int, mode: str = "nearest") -> int:
    """Map a pitch class to nearest white key.
    mode: 'down' (prefer lower), 'nearest' (min abs distance), 'scale' (to C major by nearest)
    """
    pc = pc % 12
    if pc in WHITE_PCS:
        return pc
    if mode == "down":
        # step downward until a white key is found
        for d in range(1, 7):
            cand = (pc - d) % 12
            if cand in WHITE_PCS:
                return cand
    # nearest by absolute distance (ties: prefer lower)
    best = None
    best_dist = 99
    for w in WHITE_PCS:
        dist = min((pc - w) % 12, (w - pc) % 12)
        if dist < best_dist or (dist == best_dist and ((w - pc) % 12) > ((pc - (best or 0)) % 12)):
            best = w
            best_dist = dist
    return best if best is not None else pc


def transpose_black_keys(events: List[Dict[str, Any]], strategy: str = "nearest") -> List[Dict[str, Any]]:
    """Transpose black-key notes to white keys consistently across note_on/off pairs.
    strategy: 'down' | 'nearest' | 'scale'
    Mutates a shallow-copied list of events.
    """
    if not events:
        return []
    # Build note on/off pairs by (channel,note) stacks
    result: List[Dict[str, Any]] = []
    for ev in events:
        ev = dict(ev)
        note = ev.get('note')
        if note is not None:
            pc = note % 12
            if pc in BLACK_PCS:
                new_pc = _nearest_white_pc(pc, 'down' if strategy == 'down' else 'nearest')
                # keep octave
                ev['note'] = (note - pc) + new_pc
        result.append(ev)
    return result


def quantize_events(events: List[Dict[str, Any]], grid_ms: int = 30) -> List[Dict[str, Any]]:
    """Quantize start_time of events to a regular grid in seconds.
    Maintains relative ordering; snaps both note_on and corresponding note_off.
    """
    if not events:
        return []
    grid = max(1, int(grid_ms)) / 1000.0
    # Snap times
    snapped = []
    for ev in events:
        ev = dict(ev)
        t = float(ev.get('start_time', 0.0))
        ev['start_time'] = round(t / grid) * grid
        snapped.append(ev)
    # Stable sort by time then by type (release before press to avoid overlaps)
    type_rank = {'note_off': 0, 'note_on': 1}
    snapped.sort(key=lambda x: (x.get('start_time', 0.0), type_rank.get(x.get('type'), 2)))
    return snapped


def group_window(events: List[Dict[str, Any]], window_ms: int = 30) -> List[Dict[str, Any]]:
    """Group events by a window that starts at the first event of a group.
    All events whose start_time fall within [t0, t0 + window] are snapped to t0,
    then the next group's t0 is the first event after that window.
    This matches: "当第一个音摁下时，后续window内的按键输入作为同时按下触发，然后进入下一个窗口检测".
    """
    if not events:
        return []
    win = max(1, int(window_ms)) / 1000.0
    arr = [dict(ev) for ev in events]
    arr.sort(key=lambda x: float(x.get('start_time', 0.0)))
    out: List[Dict[str, Any]] = []
    i = 0
    n = len(arr)
    while i < n:
        t0 = float(arr[i].get('start_time', 0.0))
        j = i
        while j < n and float(arr[j].get('start_time', 0.0)) - t0 <= win:
            ev = dict(arr[j])
            ev['start_time'] = t0
            out.append(ev)
            j += 1
        i = j
    # keep release-before-press ordering within same time
    type_rank = {'note_off': 0, 'note_on': 1}
    out.sort(key=lambda x: (x.get('start_time', 0.0), type_rank.get(x.get('type'), 2)))
    return out
