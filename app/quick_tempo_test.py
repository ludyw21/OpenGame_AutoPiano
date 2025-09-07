#!/usr/bin/env python3
"""
快速播放速度测试工具
直接测试特定MIDI文件的播放速度问题
"""

import sys
import os
import time
import threading
sys.path.insert(0, '.')

def test_midi_parsing_speed():
    """测试MIDI文件解析的时间计算"""
    try:
        # 导入必要模块
        from meowauto.playback.auto_player import AutoPlayer
        from meowauto.app.services.playback_service import PlaybackService
        from meowauto.config.key_mapping_manager import DEFAULT_MAPPING
        from meowauto.midi.analyzer import parse_midi
        
        # 测试文件
        midi_files = []
        
        # 查找MIDI文件
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.mid') and ('倒数' in file or 'test' in file.lower()):
                    midi_files.append(os.path.join(root, file))
        
        if not midi_files:
            print("未找到测试MIDI文件")
            return
        
        midi_file = midi_files[0]
        print(f"测试文件: {midi_file}")
        
        # 1. 测试MidiAnalyzer解析
        print("\n=== 测试MidiAnalyzer解析 ===")
        analyzer_result = parse_midi(midi_file)
        if analyzer_result.get('ok'):
            notes = analyzer_result.get('notes', [])
            print(f"解析得到 {len(notes)} 个音符")
            if notes:
                first_note = notes[0]
                last_note = notes[-1]
                print(f"第一个音符: {first_note['start_time']:.3f}s")
                print(f"最后一个音符: {last_note['start_time']:.3f}s")
                print(f"总时长: {last_note['start_time']:.3f}s")
        else:
            print(f"解析失败: {analyzer_result.get('error')}")
        
        # 2. 测试AutoPlayer解析
        print("\n=== 测试AutoPlayer解析 ===")
        playback_service = PlaybackService()
        auto_player = AutoPlayer(playback_service, debug=True)
        
        events = auto_player._parse_midi_file(midi_file, key_mapping=DEFAULT_MAPPING)
        if events:
            print(f"AutoPlayer解析得到 {len(events)} 个事件")
            first_event = events[0]
            last_event = events[-1]
            print(f"第一个事件: {first_event['start_time']:.3f}s")
            print(f"最后一个事件: {last_event['start_time']:.3f}s")
            print(f"总时长: {last_event['start_time']:.3f}s")
            
            # 3. 对比时间差异
            print("\n=== 对比解析结果 ===")
            if analyzer_result.get('ok') and notes:
                analyzer_duration = notes[-1]['start_time']
                autoplayer_duration = events[-1]['start_time']
                time_diff = abs(analyzer_duration - autoplayer_duration)
                print(f"MidiAnalyzer总时长: {analyzer_duration:.3f}s")
                print(f"AutoPlayer总时长: {autoplayer_duration:.3f}s")
                print(f"时间差异: {time_diff:.3f}s ({time_diff/analyzer_duration*100:.1f}%)")
                
                if time_diff > 0.1:
                    print("⚠️ 时间差异较大，可能存在解析不一致问题")
                else:
                    print("✅ 时间解析基本一致")
        
        # 4. 测试实际播放速度（模拟前5秒）
        print("\n=== 测试播放速度（前5秒模拟） ===")
        test_events = [e for e in events if e['start_time'] <= 5.0][:10]  # 前5秒内的前10个事件
        
        if test_events:
            print(f"测试前 {len(test_events)} 个事件")
            
            # 模拟播放时间计算
            tempo_multiplier = 1.0
            start_time = time.time()
            
            for i, event in enumerate(test_events):
                # 计算应该等待的时间（使用AutoPlayer的逻辑）
                target_time = event['start_time'] / tempo_multiplier
                elapsed = time.time() - start_time
                wait_time = target_time - elapsed
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                actual_elapsed = time.time() - start_time
                expected_time = event['start_time'] / tempo_multiplier
                time_diff = actual_elapsed - expected_time
                
                print(f"事件 {i+1}: 预期 {expected_time:.3f}s, 实际 {actual_elapsed:.3f}s, 差异 {time_diff:+.3f}s")
                
                if abs(time_diff) > 0.05:  # 50ms误差
                    print(f"⚠️ 时间差异过大")
                    break
        
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_midi_parsing_speed()
