"""
Key mapping strategies for different game layouts.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List


class KeyMappingStrategy:
    """Strategy interface for mapping MIDI note to keyboard key."""
    name: str = "base"

    def map_note(self, midi_note: int, mapping: Dict[str, str], options: Dict[str, Any]) -> Optional[str]:
        raise NotImplementedError

    # 兼容层：AutoPlayer 期望的批量键映射接口
    # note_event: { 'note': int, 'start_time': float, 'end_time': float, 'duration': float, ... }
    # 返回：键位字符串列表；默认策略仅返回单个键（若可映射）。
    def map_note_to_keys(self, note_event: Dict[str, Any], mapping: Dict[str, str], options: Optional[Dict[str, Any]] = None) -> List[str]:
        try:
            midi_note = int(note_event.get('note'))
        except Exception:
            return []
        opt = options or {}
        key = self.map_note(midi_note, mapping, opt)
        return [key] if key else []


class Strategy21Key(KeyMappingStrategy):
    name = "strategy_21key"

    def __init__(self):
        # Precompute degree names for 21-key: L1..L7, M1..M7, H1..H7
        self.layers = ["L", "M", "H"]
        self.degrees = ["1", "2", "3", "4", "5", "6", "7"]

    def map_note(self, midi_note: int, mapping: Dict[str, str], options: Dict[str, Any]) -> Optional[str]:
        # Heuristic similar to previous implementation: map into L/M/H and nearest degree
        # Assume C major-like white-key degrees, with fallback if exact not present.
        enable_fallback = bool(options.get('enable_key_fallback', True))
        # Use middle C (60) as M1 reference; 12 semitone per octave
        # Build candidate degree by pitch class distance to white keys
        # Simple mapping window: L: [48..59], M: [60..71], H: [72..83]
        if midi_note < 48:
            region = "L"
            note_in_region = max(48, midi_note)
        elif midi_note < 60:
            region = "L"
            note_in_region = midi_note
        elif midi_note < 72:
            region = "M"
            note_in_region = midi_note
        else:
            region = "H"
            note_in_region = min(83, midi_note)
        # Map to degree 1..7 via nearest white-key step in C
        white_pc_order = [0, 2, 4, 5, 7, 9, 11]  # C D E F G A B
        pc = note_in_region % 12
        # Choose nearest white key
        nearest = min(white_pc_order, key=lambda w: min((pc - w) % 12, (w - pc) % 12))
        idx = white_pc_order.index(nearest)  # 0..6
        key_name = f"{region}{self.degrees[idx]}"
        key = mapping.get(key_name)
        if key:
            return key
        if not enable_fallback:
            return None
        # Fallback: try neighbors within same region, then other regions
        for d in range(1, 4):
            for sign in (-1, 1):
                j = idx + sign * d
                if 0 <= j < 7:
                    k = mapping.get(f"{region}{self.degrees[j]}")
                    if k:
                        return k
        # Cross-region fallbacks
        for reg in ("M", "L", "H"):
            for j in range(7):
                k = mapping.get(f"{reg}{self.degrees[j]}")
                if k:
                    return k
        return None


class Strategy3x5(KeyMappingStrategy):
    name = "strategy_3x5"

    def __init__(self):
        # Index 0..14 corresponding to K1..K15: top row left-to-right, then middle, then bottom
        self.key_ids: List[str] = [
            "K1","K2","K3","K4","K5",
            "K6","K7","K8","K9","K10",
            "K11","K12","K13","K14","K15",
        ]
        # Define preferred MIDI window for 15 notes. Use G3(55) to B5(83) as a practical range.
        self.low = 55
        self.high = 83
        self.span = max(1, self.high - self.low)  # 28

    def map_note(self, midi_note: int, mapping: Dict[str, str], options: Dict[str, Any]) -> Optional[str]:
        # Clamp into window, then linear map to 0..14. Prefer clamp not random fallback.
        n = midi_note
        if n < self.low:
            n = self.low
        elif n > self.high:
            n = self.high
        # Linear scale
        pos = (n - self.low) / self.span  # 0..1
        idx = int(round(pos * 14))  # 0..14
        idx = max(0, min(14, idx))
        key_id = self.key_ids[idx]
        key = mapping.get(key_id)
        if key:
            return key
        # If mapping incomplete, try nearest indices
        for d in range(1, 4):
            for sign in (-1, 1):
                j = idx + sign * d
                if 0 <= j < 15:
                    key = mapping.get(self.key_ids[j])
                    if key:
                        return key
        return None


def get_strategy(name: str) -> KeyMappingStrategy:
    if name == Strategy3x5.name:
        return Strategy3x5()
    # default
    return Strategy21Key()
