import os
import sys
import math
import json

# Ensure consistent cwd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MIDI_REL_PATH = os.path.join('music', '勾指起誓.mid')
MIDI_PATH = os.path.join(ROOT, MIDI_REL_PATH)


def parse_duration_mido(midi_path: str) -> float:
    try:
        import mido
    except Exception as e:
        print(json.dumps({"error": f"mido import failed: {e}"}, ensure_ascii=False))
        return -1.0
    if not os.path.exists(midi_path):
        print(json.dumps({"error": f"MIDI not found: {midi_path}"}, ensure_ascii=False))
        return -1.0

    midi = mido.MidiFile(midi_path)
    default_tempo = 500000  # 120 BPM, microseconds per beat
    ticks_per_beat = max(1, int(midi.ticks_per_beat))

    # Collect all messages with absolute tick time
    all_messages = []
    for track_num, track in enumerate(midi.tracks):
        track_time = 0
        for msg in track:
            track_time += msg.time  # msg.time is delta ticks in mido
            all_messages.append({
                'msg': msg,
                'track_time': track_time,
                'track_num': track_num,
            })
    all_messages.sort(key=lambda x: x['track_time'])

    # Build tempo changes table
    tempo_changes = [{'tick': 0, 'tempo': default_tempo, 'acc_seconds': 0.0}]
    last_tempo = default_tempo
    for mi in all_messages:
        msg = mi['msg']
        if msg.type == 'set_tempo':
            t = mi['track_time']
            if (not tempo_changes) or (t != tempo_changes[-1]['tick']) or (msg.tempo != last_tempo):
                tempo_changes.append({'tick': t, 'tempo': msg.tempo, 'acc_seconds': 0.0})
                last_tempo = msg.tempo

    # Compute accumulated seconds at each change
    for i in range(1, len(tempo_changes)):
        prev = tempo_changes[i-1]
        cur = tempo_changes[i]
        delta_ticks = max(0, cur['tick'] - prev['tick'])
        seconds_per_tick = (prev['tempo'] / 1_000_000.0) / ticks_per_beat
        cur['acc_seconds'] = prev['acc_seconds'] + delta_ticks * seconds_per_tick

    def tick_to_seconds(tick_pos: int) -> float:
        # find last tempo change with tick <= tick_pos
        idx = 0
        for i in range(len(tempo_changes)):
            if tempo_changes[i]['tick'] <= tick_pos:
                idx = i
            else:
                break
        base = tempo_changes[idx]
        seconds_per_tick = (base['tempo'] / 1_000_000.0) / ticks_per_beat
        return base['acc_seconds'] + (tick_pos - base['tick']) * seconds_per_tick

    # Track active notes for note_on->note_off pairs
    active_notes = {}
    events = []
    for mi in all_messages:
        msg = mi['msg']
        t = mi['track_time']
        ch = getattr(msg, 'channel', 0)
        if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
            key = (ch, msg.note)
            active_notes.setdefault(key, []).append({'start_tick': t, 'velocity': msg.velocity, 'channel': ch, 'note': msg.note})
        elif msg.type == 'note_off' or (msg.type == 'note_on' and getattr(msg, 'velocity', 0) == 0):
            note = getattr(msg, 'note', None)
            if note is None:
                continue
            key = (ch, note)
            stk = active_notes.get(key)
            if stk:
                start_info = stk.pop()
                if not stk:
                    active_notes.pop(key, None)
                st = tick_to_seconds(start_info['start_tick'])
                et = tick_to_seconds(t)
                # Create logical pressed/released events (key not needed to compute duration)
                events.append({'start_time': st, 'type': 'note_on'})
                events.append({'start_time': et, 'type': 'note_off'})

    # Handle dangling notes with a default duration
    for key, stk in list(active_notes.items()):
        while stk:
            start_info = stk.pop()
            st = tick_to_seconds(start_info['start_tick'])
            et = st + 0.5
            events.append({'start_time': st, 'type': 'note_on'})
            events.append({'start_time': et, 'type': 'note_off'})

    if not events:
        return 0.0
    events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
    total_time = events[-1]['start_time']
    return float(total_time)


def parse_duration_pretty_midi(midi_path: str) -> float:
    try:
        import pretty_midi
    except Exception as e:
        print(json.dumps({"warn": f"pretty_midi import failed: {e}"}, ensure_ascii=False))
        return -1.0
    if not os.path.exists(midi_path):
        print(json.dumps({"error": f"MIDI not found: {midi_path}"}, ensure_ascii=False))
        return -1.0
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        print(json.dumps({"error": f"pretty_midi parse error: {e}"}, ensure_ascii=False))
        return -1.0
    events = []
    for inst in pm.instruments:
        for n in inst.notes:
            st = float(n.start)
            et = float(n.end)
            events.append({'start_time': st, 'type': 'note_on'})
            events.append({'start_time': et, 'type': 'note_off'})
    if not events:
        return 0.0
    events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
    total_time = events[-1]['start_time']
    return float(total_time)


def main():
    print(json.dumps({"file": MIDI_PATH}, ensure_ascii=False))
    old_sec = parse_duration_mido(MIDI_PATH)
    new_sec = parse_duration_pretty_midi(MIDI_PATH)

    result = {"midi": MIDI_REL_PATH}
    if old_sec >= 0:
        result["old_version_seconds"] = round(old_sec, 6)
    else:
        result["old_version_seconds"] = None
    if new_sec >= 0:
        result["new_version_seconds"] = round(new_sec, 6)
    else:
        result["new_version_seconds"] = None

    if old_sec >= 0 and new_sec >= 0:
        diff = new_sec - old_sec
        result["diff_seconds"] = round(diff, 6)
        if max(old_sec, 1e-9) > 0:
            result["diff_percent_vs_old"] = round((diff / old_sec) * 100.0, 6)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
