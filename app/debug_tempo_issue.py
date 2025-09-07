#!/usr/bin/env python3
"""
调试播放速度问题的完整测试工具
"""

import sys
import os
import time

# 添加项目路径
sys.path.insert(0, '.')

def debug_tempo_issue():
    """调试播放速度问题"""
    
    print("=== 调试播放速度问题 ===")
    
    # 1. 测试mido库是否可用
    try:
        import mido
        print("✅ mido库可用")
    except ImportError as e:
        print(f"❌ mido库不可用: {e}")
        return
    
    # 2. 查找测试MIDI文件
    test_files = [
        'music/09483-倒数-有你别无所求.mid',
        'music/卡农.mid'
    ]
    
    midi_file = None
    for test_path in test_files:
        if os.path.exists(test_path):
            midi_file = test_path
            break
    
    if not midi_file:
        print("❌ 未找到测试MIDI文件")
        return
    
    print(f"📁 使用测试文件: {midi_file}")
    
    # 3. 测试mido原生解析
    try:
        mid = mido.MidiFile(midi_file)
        print(f"📊 MIDI文件信息:")
        print(f"   - Ticks per beat: {mid.ticks_per_beat}")
        print(f"   - 文件长度: {mid.length:.3f}秒")
        print(f"   - 轨道数: {len(mid.tracks)}")
        
        # 收集前10个音符事件
        note_events = []
        for track_idx, track in enumerate(mid.tracks):
            absolute_time = 0
            for msg in track:
                absolute_time += msg.time
                if msg.type in ['note_on', 'note_off'] and len(note_events) < 10:
                    note_events.append({
                        'time': absolute_time,
                        'type': msg.type,
                        'note': msg.note,
                        'velocity': getattr(msg, 'velocity', 0),
                        'track': track_idx
                    })
        
        print(f"\n🎵 前10个音符事件:")
        for i, event in enumerate(note_events):
            print(f"   {i+1:2d}. {event['time']:8.3f}s - {event['type']:8s} - note {event['note']:3d}")
        
    except Exception as e:
        print(f"❌ mido解析失败: {e}")
        return
    
    # 4. 测试AutoPlayer解析
    print(f"\n🤖 测试AutoPlayer解析:")
    try:
        from meowauto.playback.auto_player import AutoPlayer
        from meowauto.core import Logger
        
        logger = Logger()
        auto_player = AutoPlayer(logger, debug=True)
        
        # 解析MIDI文件
        events = auto_player._parse_midi_file(midi_file)
        
        if events:
            print(f"   - 解析得到 {len(events)} 个事件")
            print(f"   - 第一个事件: {events[0]['start_time']:.3f}s")
            print(f"   - 最后一个事件: {events[-1]['start_time']:.3f}s")
            
            # 对比时间差异
            mido_duration = mid.length
            autoplayer_duration = events[-1]['start_time']
            time_diff = abs(mido_duration - autoplayer_duration)
            
            print(f"\n⏱️  时间对比:")
            print(f"   - mido文件长度: {mido_duration:.3f}s")
            print(f"   - AutoPlayer最后事件: {autoplayer_duration:.3f}s")
            print(f"   - 时间差异: {time_diff:.3f}s ({time_diff/mido_duration*100:.1f}%)")
            
            if time_diff < 0.1:
                print("   ✅ 时间解析一致")
            else:
                print("   ⚠️  时间差异较大")
                
        else:
            print("   ❌ AutoPlayer解析失败")
            
    except Exception as e:
        print(f"   ❌ AutoPlayer测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试MidiAnalyzer解析
    print(f"\n🔍 测试MidiAnalyzer解析:")
    try:
        from meowauto.midi.analyzer import parse_midi
        
        result = parse_midi(midi_file)
        if result.get('ok'):
            notes = result.get('notes', [])
            print(f"   - 解析得到 {len(notes)} 个音符")
            if notes:
                print(f"   - 第一个音符: {notes[0]['start_time']:.3f}s")
                print(f"   - 最后一个音符: {notes[-1]['start_time']:.3f}s")
                
                # 对比时间差异
                analyzer_duration = notes[-1]['start_time']
                time_diff = abs(mido_duration - analyzer_duration)
                
                print(f"   - 与mido差异: {time_diff:.3f}s ({time_diff/mido_duration*100:.1f}%)")
                
                if time_diff < 0.1:
                    print("   ✅ MidiAnalyzer时间一致")
                else:
                    print("   ⚠️  MidiAnalyzer时间差异较大")
        else:
            print(f"   ❌ MidiAnalyzer解析失败: {result.get('error')}")
            
    except Exception as e:
        print(f"   ❌ MidiAnalyzer测试失败: {e}")
    
    # 6. 测试播放服务
    print(f"\n🎮 测试PlaybackService:")
    try:
        from meowauto.app.services.playback_service import PlaybackService
        from meowauto.core import Logger
        
        logger = Logger()
        service = PlaybackService(logger)
        
        # 配置AutoPlayer
        service.configure_auto_player(debug=True)
        
        print("   ✅ PlaybackService初始化成功")
        
        # 测试启动播放（不实际播放，只测试解析）
        print("   📝 播放服务配置完成")
        
    except Exception as e:
        print(f"   ❌ PlaybackService测试失败: {e}")
    
    print(f"\n🏁 调试完成")

if __name__ == "__main__":
    debug_tempo_issue()
