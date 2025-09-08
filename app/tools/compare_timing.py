#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare MIDI timing between pretty_midi and mido for a given file.
Outputs a CSV with per-note timing and prints summary stats.

Usage:
  python app/tools/compare_timing.py "app/music/勾指起誓.mid" --limit 50 --out output/timing_compare.csv

Requires:
  - pretty_midi
  - mido
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
from typing import List, Dict, Tuple


def gather_pretty(file_path: str) -> List[Dict]:
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(file_path)
    out: List[Dict] = []
    for ti, inst in enumerate(pm.instruments):
        is_drum = bool(inst.is_drum)
        ch = 9 if is_drum else ti
        for n in inst.notes:
            out.append({
                'track': ti,
                'channel': ch,
                'note': int(n.pitch),
                'velocity': int(n.velocity),
                'start': float(n.start),
                'end': float(n.end),
                'is_drum': is_drum,
                'src': 'pretty',
            })
    out.sort(key=lambda x: (x['start'], x['end'], x['note']))
    return out


essential_types = {"note_on", "note_off", "set_tempo"}

def _ticks_to_seconds_builder(ticks_per_beat: int, tempo_changes: List[Tuple[int, int]]):
    """Build a converter from absolute ticks to seconds using tempo change map.
    tempo_changes: list of (abs_tick, tempo_us_per_beat) sorted by abs_tick.
    """
    # Precompute cumulative seconds at each tempo change
    tempo_changes = sorted(tempo_changes, key=lambda x: x[0])
    if not tempo_changes or tempo_changes[0][0] != 0:
        # default 120bpm at 0 if not present
        tempo_changes = [(0, 500000)] + tempo_changes
    cum = []  # (abs_tick, tempo, cum_sec_at_this_tick)
    last_tick = tempo_changes[0][0]
    last_tempo = tempo_changes[0][1]
    cum_sec = 0.0
    cum.append((last_tick, last_tempo, cum_sec))
    for (t, tmp) in tempo_changes[1:]:
        dt = t - last_tick
        if dt < 0:
            dt = 0
        sec = (dt * last_tempo) / (ticks_per_beat * 1_000_000.0)
        cum_sec += sec
        cum.append((t, tmp, cum_sec))
        last_tick = t
        last_tempo = tmp

    def conv(abs_tick: int) -> float:
        # find last change <= abs_tick
        lo, hi = 0, len(cum) - 1
        idx = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if cum[mid][0] <= abs_tick:
                idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        base_tick, tempo_us, base_sec = cum[idx]
        dt = abs_tick - base_tick
        if dt < 0:
            dt = 0
        sec = base_sec + (dt * tempo_us) / (ticks_per_beat * 1_000_000.0)
        return float(sec)

    return conv


def gather_mido(file_path: str) -> Tuple[List[Dict], int]:
    import mido
    mid = mido.MidiFile(file_path)
    tpb = getattr(mid, 'ticks_per_beat', 480)
    # Build absolute tick, collect tempo changes and notes
    tempo_changes: List[Tuple[int, int]] = [(0, 500000)]  # (abs_tick, tempo)
    events: List[Dict] = []
    for ti, track in enumerate(mid.tracks):
        abs_tick = 0
        on_stack: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        cur_tempo = 500000
        for msg in track:
            abs_tick += int(getattr(msg, 'time', 0) or 0)
            if msg.type == 'set_tempo':
                cur_tempo = int(msg.tempo)
                tempo_changes.append((abs_tick, cur_tempo))
            if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                ch = int(getattr(msg, 'channel', 0) or 0)
                note = int(getattr(msg, 'note', 0) or 0)
                vel = int(getattr(msg, 'velocity', 0) or 0)
                on_stack.setdefault((ch, note), []).append((abs_tick, vel))
            elif msg.type in ('note_off', 'note_on'):
                # note_on with velocity 0 -> note_off
                if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                    continue
                ch = int(getattr(msg, 'channel', 0) or 0)
                note = int(getattr(msg, 'note', 0) or 0)
                key = (ch, note)
                if key in on_stack and on_stack[key]:
                    start_tick, vel = on_stack[key].pop(0)
                    events.append({
                        'track': ti,
                        'channel': ch,
                        'note': note,
                        'velocity': vel,
                        'start_tick': start_tick,
                        'end_tick': abs_tick,
                        'src': 'mido',
                    })
    # Build converter and convert
    conv = _ticks_to_seconds_builder(tpb, tempo_changes)
    for e in events:
        e['start'] = conv(int(e['start_tick']))
        e['end'] = conv(int(e['end_tick']))
    events.sort(key=lambda x: (x['start'], x['end'], x['note']))
    return events, tpb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='MIDI file path')
    ap.add_argument('--limit', type=int, default=50, help='Rows to compare output')
    ap.add_argument('--out', type=str, default='output/timing_compare.csv')
    args = ap.parse_args()

    path = args.path
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    # Gather via pretty_midi
    try:
        pretty_notes = gather_pretty(path)
    except Exception as e:
        print(f"[ERROR] pretty_midi failed: {e}")
        pretty_notes = []

    # Gather via mido
    try:
        mido_notes, tpb = gather_mido(path)
    except Exception as e:
        print(f"[ERROR] mido failed: {e}")
        mido_notes, tpb = [], 0

    # Align by index (simplified). For robust matching, could use (start,note,channel) matching if needed.
    lim = args.limit if args.limit and args.limit > 0 else min(len(pretty_notes), len(mido_notes))
    lim = min(lim, len(pretty_notes), len(mido_notes))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['idx','note','channel','velocity','pretty_start','pretty_end','mido_start','mido_end','diff_start','diff_end'])
        for i in range(lim):
            pn = pretty_notes[i]
            mn = mido_notes[i]
            ds = float(pn['start']) - float(mn['start'])
            de = float(pn['end']) - float(mn['end'])
            w.writerow([i, pn['note'], pn['channel'], pn['velocity'], f"{pn['start']:.6f}", f"{pn['end']:.6f}", f"{mn['start']:.6f}", f"{mn['end']:.6f}", f"{ds:.6f}", f"{de:.6f}"])

    # Summary
    def _max_abs_diff(A: List[Dict], B: List[Dict], key: str, n: int) -> float:
        m = min(n, len(A), len(B))
        if m <= 0:
            return 0.0
        diffs = [abs(float(A[i][key]) - float(B[i][key])) for i in range(m)]
        return max(diffs) if diffs else 0.0

    max_ds = _max_abs_diff(pretty_notes, mido_notes, 'start', lim)
    max_de = _max_abs_diff(pretty_notes, mido_notes, 'end', lim)

    print(f"[INFO] Compared {lim} notes. CSV saved to: {args.out}")
    print(f"[INFO] Max |pretty-start - mido-start| = {max_ds:.6f}s; Max |pretty-end - mido-end| = {max_de:.6f}s")
    if max_ds > 0.02 or max_de > 0.02:
        print("[WARN] Significant timing differences detected (>20ms). Check the CSV for details.")


if __name__ == '__main__':
    main()
