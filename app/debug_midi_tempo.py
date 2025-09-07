#!/usr/bin/env python3
"""
MIDI文件tempo分析调试工具
用于分析特定MIDI文件的tempo信息，找出播放速度异常的原因
"""

import mido
import os
import sys

def analyze_midi_file(midi_path):
    """分析MIDI文件的tempo信息"""
    if not os.path.exists(midi_path):
        print(f"文件不存在: {midi_path}")
        return
    
    try:
        mid = mido.MidiFile(midi_path)
        print(f"=== MIDI文件分析: {os.path.basename(midi_path)} ===")
        print(f"Ticks per beat: {mid.ticks_per_beat}")
        print(f"时间基类型: {'PPQ' if mid.ticks_per_beat > 0 else 'SMPTE'}")
        print(f"文件长度: {mid.length:.2f}秒")
        print(f"轨道数: {len(mid.tracks)}")
        
        # 分析tempo变化
        tempo_changes = []
        all_messages = []
        
        # 收集所有消息
        for track_num, track in enumerate(mid.tracks):
            track_time = 0
            for msg in track:
                track_time += msg.time
                all_messages.append({
                    'msg': msg,
                    'track_time': track_time,
                    'track_num': track_num
                })
        
        # 按时间排序
        all_messages.sort(key=lambda x: x['track_time'])
        
        # 查找tempo变化
        default_tempo = 500000  # 120 BPM
        current_tempo = default_tempo
        
        print(f"\n=== Tempo变化分析 ===")
        print(f"默认tempo: {default_tempo}微秒/拍 ({60000000/default_tempo:.1f} BPM)")
        
        for msg_info in all_messages:
            msg = msg_info['msg']
            if msg.type == 'set_tempo':
                bpm = 60000000 / msg.tempo
                tempo_changes.append({
                    'tick': msg_info['track_time'],
                    'tempo': msg.tempo,
                    'bpm': bpm,
                    'track': msg_info['track_num']
                })
                print(f"Tick {msg_info['track_time']:6d}: {msg.tempo:6d}微秒/拍 ({bpm:6.1f} BPM) [轨道{msg_info['track_num']}]")
                current_tempo = msg.tempo
        
        if not tempo_changes:
            print("未找到tempo变化消息，使用默认120 BPM")
        
        # 计算实际播放时长（基于tempo变化）
        if mid.ticks_per_beat > 0:  # PPQ
            print(f"\n=== PPQ时间计算 ===")
            tempo_table = [{'tick': 0, 'tempo': default_tempo, 'acc_seconds': 0.0}]
            
            for change in tempo_changes:
                tempo_table.append({
                    'tick': change['tick'],
                    'tempo': change['tempo'],
                    'acc_seconds': 0.0
                })
            
            # 计算累积时间
            for i in range(1, len(tempo_table)):
                prev = tempo_table[i-1]
                cur = tempo_table[i]
                delta_ticks = cur['tick'] - prev['tick']
                seconds_per_tick = (prev['tempo'] / 1_000_000.0) / mid.ticks_per_beat
                cur['acc_seconds'] = prev['acc_seconds'] + delta_ticks * seconds_per_tick
            
            print("时间换算表:")
            for entry in tempo_table:
                print(f"  Tick {entry['tick']:6d}: {entry['acc_seconds']:8.3f}秒")
        
        # 分析note事件的时间分布
        print(f"\n=== Note事件分析 ===")
        note_events = []
        for msg_info in all_messages[:50]:  # 只看前50个事件
            msg = msg_info['msg']
            if msg.type in ['note_on', 'note_off']:
                # 计算实际时间
                if mid.ticks_per_beat > 0:
                    # PPQ时间计算
                    tick_pos = msg_info['track_time']
                    seconds = tick_to_seconds_ppq(tick_pos, tempo_table, mid.ticks_per_beat)
                else:
                    # SMPTE时间计算
                    seconds = msg_info['track_time'] * (1.0 / (30 * 80))  # 简化计算
                
                note_events.append({
                    'tick': msg_info['track_time'],
                    'seconds': seconds,
                    'type': msg.type,
                    'note': getattr(msg, 'note', None),
                    'track': msg_info['track_num']
                })
        
        print("前10个note事件:")
        for i, event in enumerate(note_events[:10]):
            print(f"  {i+1:2d}. Tick {event['tick']:6d} ({event['seconds']:6.3f}s): {event['type']} note={event['note']} [轨道{event['track']}]")
        
        return {
            'ticks_per_beat': mid.ticks_per_beat,
            'length': mid.length,
            'tempo_changes': tempo_changes,
            'note_events': note_events[:10]
        }
        
    except Exception as e:
        print(f"分析出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def tick_to_seconds_ppq(tick_pos, tempo_table, ticks_per_beat):
    """PPQ时间基下的tick到秒转换"""
    # 找到最后一个变化点
    idx = 0
    for i in range(len(tempo_table)):
        if tempo_table[i]['tick'] <= tick_pos:
            idx = i
        else:
            break
    
    base = tempo_table[idx]
    seconds_per_tick = (base['tempo'] / 1_000_000.0) / ticks_per_beat
    return base['acc_seconds'] + (tick_pos - base['tick']) * seconds_per_tick

if __name__ == "__main__":
    # 分析问题文件
    problem_file = "music/09483-倒数-有你别无所求.mid"
    
    print("=== 分析播放速度异常的MIDI文件 ===")
    analyze_midi_file(problem_file)
    
    # 如果有其他正常文件，可以对比
    print("\n" + "="*60)
    print("请提供一个播放速度正常的MIDI文件路径进行对比分析")
