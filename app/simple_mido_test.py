#!/usr/bin/env python3
"""
简单的mido库测试工具
直接使用mido的原生时间信息
"""

import mido
import os
import time

def test_mido_native_timing():
    """测试mido库的原生时间信息"""
    
    # 查找MIDI文件
    midi_file = None
    test_files = [
        'music/09483-倒数-有你别无所求.mid',
        'music/卡农.mid',
        'music/大鱼.mid'
    ]
    
    for test_path in test_files:
        if os.path.exists(test_path):
            midi_file = test_path
            break
    
    if not midi_file:
        # 回退搜索
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.mid'):
                    midi_file = os.path.join(root, file)
                    break
            if midi_file:
                break
    
    if not midi_file:
        print("未找到测试MIDI文件")
        return
    
    print(f"测试文件: {midi_file}")
    
    try:
        # 加载MIDI文件
        mid = mido.MidiFile(midi_file)
        print(f"Ticks per beat: {mid.ticks_per_beat}")
        print(f"mido计算的文件长度: {mid.length:.3f}秒")
        print(f"轨道数: {len(mid.tracks)}")
        
        # 使用mido的原生时间转换
        print("\n=== 使用mido原生时间转换 ===")
        
        # 收集所有note事件及其绝对时间
        note_events = []
        for track_idx, track in enumerate(mid.tracks):
            absolute_time = 0
            for msg in track:
                absolute_time += msg.time  # mido自动处理tick到秒的转换
                if msg.type in ['note_on', 'note_off']:
                    note_events.append({
                        'time': absolute_time,
                        'type': msg.type,
                        'note': msg.note,
                        'velocity': msg.velocity,
                        'track': track_idx
                    })
        
        # 按时间排序
        note_events.sort(key=lambda x: x['time'])
        
        print(f"找到 {len(note_events)} 个音符事件")
        if note_events:
            print(f"第一个事件: {note_events[0]['time']:.3f}s")
            print(f"最后一个事件: {note_events[-1]['time']:.3f}s")
            print(f"实际音乐长度: {note_events[-1]['time']:.3f}s")
            
            # 显示前10个事件
            print("\n前10个音符事件:")
            for i, event in enumerate(note_events[:10]):
                print(f"{i+1:2d}. {event['time']:8.3f}s - {event['type']:8s} - note {event['note']:3d} - track {event['track']}")
        
        # 测试播放速度（模拟前5秒）
        print("\n=== 模拟播放测试（前5秒） ===")
        test_events = [e for e in note_events if e['time'] <= 5.0][:10]
        
        if test_events:
            print(f"测试前 {len(test_events)} 个事件")
            start_time = time.time()
            
            for i, event in enumerate(test_events):
                # 等待到事件时间
                target_time = event['time']
                elapsed = time.time() - start_time
                wait_time = target_time - elapsed
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                actual_elapsed = time.time() - start_time
                time_diff = actual_elapsed - target_time
                
                print(f"事件 {i+1}: 预期 {target_time:.3f}s, 实际 {actual_elapsed:.3f}s, 差异 {time_diff:+.3f}s")
                
                if abs(time_diff) > 0.05:
                    print("⚠️ 时间差异过大")
                    break
            
            total_time = time.time() - start_time
            expected_time = test_events[-1]['time']
            print(f"\n总测试时间: {total_time:.3f}s")
            print(f"预期时间: {expected_time:.3f}s")
            print(f"时间差异: {total_time - expected_time:+.3f}s")
        
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mido_native_timing()
