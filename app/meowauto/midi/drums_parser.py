#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DrumsMidiParser: 专用架子鼓 MIDI 解析器
- 适配两类MIDI：多轨（鼓在通道10/channel=9）与仅鼓单轨
- 不读取力度；必须读取并应用曲速，精确到秒
- 输出统一音符事件：{start_time, end_time, channel, note, drum_id, role='drums'}
- drum_id 为逻辑鼓位：KICK/SNARE/HIHAT_OPEN/HIHAT_CLOSE/TOM1/TOM2/FLOOR_TOM/CRASH_HIGH/CRASH_MID/RIDE
"""
from __future__ import annotations
from typing import Dict, List, Any

# GM 打击乐音色 -> drum_id 映射（常见）
GM_PERC_TO_DRUM: Dict[int, str] = {
    35: "KICK", 36: "KICK",
    38: "SNARE", 40: "SNARE",
    42: "HIHAT_CLOSE", 44: "HIHAT_CLOSE", 46: "HIHAT_OPEN",
    41: "FLOOR_TOM", 43: "FLOOR_TOM", 45: "TOM2", 47: "TOM2",
    48: "TOM1", 50: "TOM1",
    49: "CRASH_HIGH", 57: "CRASH_HIGH",
    51: "RIDE", 53: "RIDE", 59: "RIDE",
    52: "CRASH_MID", 55: "CRASH_MID",
}

class DrumsMidiParser:
    def __init__(self) -> None:
        pass

    def parse(self, midi_file: str) -> List[Dict[str, Any]]:
        try:
            import mido
        except Exception:
            return []
        try:
            mid = mido.MidiFile(midi_file)
        except Exception:
            return []

        default_tempo = 500000  # 120 BPM
        ticks_per_beat = mid.ticks_per_beat
        # 收集所有消息（绝对tick）
        msgs = []
        for ti, track in enumerate(mid.tracks):
            t = 0
            for msg in track:
                t += msg.time
                msgs.append({"msg": msg, "tick": t, "track": ti})
        msgs.sort(key=lambda x: x["tick"])  # 绝对时间排序

        # tempo map（仅PPQ下生效；SMPTE时直接用常量换算）
        is_smpte = bool(ticks_per_beat < 0)
        tempo_changes: List[Dict[str, Any]] = []
        smpte_seconds_per_tick = 0.0
        if not is_smpte:
            tempo_changes.append({"tick": 0, "tempo": default_tempo, "acc_seconds": 0.0})
            last_tempo = default_tempo
            for it in msgs:
                m = it["msg"]
                if m.type == "set_tempo":
                    tk = it["tick"]
                    if not tempo_changes or tk != tempo_changes[-1]["tick"] or m.tempo != last_tempo:
                        tempo_changes.append({"tick": tk, "tempo": m.tempo, "acc_seconds": 0.0})
                        last_tempo = m.tempo
            for i in range(1, len(tempo_changes)):
                prv = tempo_changes[i-1]
                cur = tempo_changes[i]
                dt = max(0, cur["tick"] - prv["tick"])
                spt = (prv["tempo"] / 1_000_000.0) / max(1, ticks_per_beat)
                cur["acc_seconds"] = prv["acc_seconds"] + dt * spt
            def tick_to_seconds(tp: int) -> float:
                idx = 0
                for j in range(len(tempo_changes)):
                    if tempo_changes[j]["tick"] <= tp:
                        idx = j
                    else:
                        break
                base = tempo_changes[idx]
                spt = (base["tempo"] / 1_000_000.0) / max(1, ticks_per_beat)
                return base["acc_seconds"] + (tp - base["tick"]) * spt
        else:
            div = int(ticks_per_beat)
            hi = (div >> 8) & 0xFF
            lo = div & 0xFF
            if hi >= 128:
                hi -= 256
            fps = abs(hi) if hi != 0 else 30
            ticks_per_frame = lo if lo > 0 else 80
            smpte_seconds_per_tick = 1.0 / (float(fps) * float(ticks_per_frame))
            def tick_to_seconds(tp: int) -> float:
                return float(tp) * smpte_seconds_per_tick

        # 提取鼓音符
        active: Dict[tuple, List[Dict[str, Any]]] = {}
        notes: List[Dict[str, Any]] = []
        for it in msgs:
            msg = it["msg"]
            if msg.type not in ("note_on", "note_off", "set_tempo"):
                continue
            if msg.type == "set_tempo":
                continue  # tempo 已经在 tempo_map 中体现
            ch = getattr(msg, "channel", 0)
            is_drum_ch = (ch == 9)
            n = getattr(msg, "note", None)
            if n is None:
                continue
            # 兜底：若非通道10，但处于打击乐典型音高，也认为可能是鼓
            likely_drum = is_drum_ch or (35 <= int(n) <= 81)
            if not likely_drum:
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                stack = active.setdefault((ch, n), [])
                stack.append({"tick": it["tick"]})
            else:
                key = (ch, n)
                if key in active and active[key]:
                    st = active[key].pop()
                    if not active[key]:
                        del active[key]
                    st_s = tick_to_seconds(int(st["tick"]))
                    ed_s = tick_to_seconds(int(it["tick"]))
                    drum_id = GM_PERC_TO_DRUM.get(int(n))
                    # 未映射的鼓音映射到就近的合理鼓位（简单兜底）
                    if drum_id is None:
                        if int(n) <= 37:
                            drum_id = "KICK"
                        elif 38 <= int(n) <= 41:
                            drum_id = "SNARE"
                        elif 42 <= int(n) <= 46:
                            drum_id = "HIHAT_CLOSE"
                        elif 47 <= int(n) <= 50:
                            drum_id = "TOM1"
                        else:
                            drum_id = "CRASH_MID"
                    notes.append({
                        "start_time": float(st_s),
                        "end_time": float(ed_s),
                        "duration": max(0.0, float(ed_s) - float(st_s)),
                        "channel": int(ch),
                        "note": int(n),
                        "drum_id": drum_id,
                        "role": "drums",
                    })
        # 对未结束音符给固定时长（鼓通常极短）
        for (ch, n), stack in list(active.items()):
            while stack:
                st = stack.pop()
                st_s = tick_to_seconds(int(st["tick"]))
                notes.append({
                    "start_time": float(st_s),
                    "end_time": float(st_s) + 0.12,
                    "duration": 0.12,
                    "channel": int(ch),
                    "note": int(n),
                    "drum_id": GM_PERC_TO_DRUM.get(int(n), "SNARE"),
                    "role": "drums",
                })
        # 排序
        notes.sort(key=lambda x: x["start_time"])
        return notes

__all__ = ["DrumsMidiParser", "GM_PERC_TO_DRUM"]
