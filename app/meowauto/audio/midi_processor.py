#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIDI processing module for MeowField AutoPiano.

This module handles MIDI file analysis, playback, and processing functionality.
"""

import os
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
import pygame
import mido

from ..core import Logger


class MidiProcessor:
    """MIDI处理器，负责MIDI文件的分析和播放"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.is_playing = False
        self.is_paused = False
        self.current_volume = 0.7
        self.current_tempo = 120
        self.playback_thread = None
        
        # 初始化pygame音频
        self._init_audio()
    
    def _init_audio(self):
        """初始化音频系统"""
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(self.current_volume)
            self.logger.log("MIDI音频系统初始化成功", "SUCCESS")
        except Exception as e:
            self.logger.log(f"MIDI音频系统初始化失败: {e}", "WARNING")
    
    def analyze_midi_file(self, midi_path: str) -> Dict[str, Any]:
        """分析MIDI文件，返回文件信息"""
        if not os.path.exists(midi_path):
            self.logger.error(f"MIDI文件不存在: {midi_path}")
            return {}
        
        try:
            midi = mido.MidiFile(midi_path)
            
            # 基本信息
            info = {
                "tracks": len(midi.tracks),
                "length": midi.length,
                "ticks_per_beat": midi.ticks_per_beat,
                "note_count": 0,
                "tempo": 120,
                "instruments": [],
                "time_signatures": []
            }
            
            # 分析音符和事件
            note_count = 0
            tempo = 500000  # 默认120 BPM
            instruments = set()
            time_signatures = []
            
            for track in midi.tracks:
                track_time = 0
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        note_count += 1
                    elif msg.type == 'set_tempo':
                        tempo = msg.tempo
                    elif msg.type == 'program_change':
                        instruments.add(msg.program)
                    elif msg.type == 'time_signature':
                        time_signatures.append({
                            'numerator': msg.numerator,
                            'denominator': msg.denominator,
                            'time': track_time
                        })
                    
                    track_time += msg.time
            
            info["note_count"] = note_count
            info["tempo"] = int(60000000 / tempo) if tempo > 0 else 120
            info["instruments"] = list(instruments)
            info["time_signatures"] = time_signatures
            
            # 记录分析结果
            self.logger.log(f"MIDI文件分析完成:", "INFO")
            self.logger.log(f"  轨道数: {info['tracks']}")
            self.logger.log(f"  总时长: {info['length']:.2f}秒")
            self.logger.log(f"  时间分辨率: {info['ticks_per_beat']}")
            self.logger.log(f"  音符总数: {info['note_count']}")
            self.logger.log(f"  速度: {info['tempo']} BPM")
            
            return info
            
        except Exception as e:
            self.logger.error(f"MIDI文件分析失败: {str(e)}")
            return {}
    
    def play_midi(self, midi_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """播放MIDI文件"""
        if not os.path.exists(midi_path):
            self.logger.error(f"MIDI文件不存在: {midi_path}")
            return False
        
        if self.is_playing:
            self.logger.warning("MIDI正在播放中")
            return False
        
        self.is_playing = True
        self.is_paused = False
        
        # 在新线程中播放
        self.playback_thread = threading.Thread(
            target=self._play_midi_thread, 
            args=(midi_path, progress_callback)
        )
        self.playback_thread.daemon = True
        self.playback_thread.start()
        
        return True
    
    def _play_midi_thread(self, midi_path: str, progress_callback: Optional[Callable] = None):
        """在后台线程中播放MIDI"""
        try:
            # 使用pygame播放MIDI文件
            pygame.mixer.music.load(midi_path)
            pygame.mixer.music.play()
            
            start_time = time.time()
            
            # 获取MIDI文件信息用于进度显示
            try:
                midi = mido.MidiFile(midi_path)
                total_time = midi.length
            except:
                total_time = 60.0  # 默认1分钟
            
            # 播放循环
            while self.is_playing and pygame.mixer.music.get_busy():
                # 更新进度条和时间显示
                current_time = time.time() - start_time
                progress = min(100, (current_time / total_time) * 100)
                
                current_str = time.strftime("%M:%S", time.gmtime(current_time))
                total_str = time.strftime("%M:%S", time.gmtime(total_time))
                
                if progress_callback:
                    progress_callback(progress, current_str, total_str)
                
                time.sleep(0.1)  # 更新频率
            
            # 播放完成
            if progress_callback:
                progress_callback(100, total_str, total_str)
            
        except Exception as e:
            self.logger.error(f"MIDI播放失败: {str(e)}")
        finally:
            self.is_playing = False
    
    def pause_midi(self):
        """暂停播放"""
        if not self.is_playing:
            return
        
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.is_paused = True
            self.logger.log("MIDI播放已暂停", "INFO")
        else:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.logger.log("MIDI播放已继续", "INFO")
    
    def stop_midi(self):
        """停止播放"""
        self.is_playing = False
        self.is_paused = False
        pygame.mixer.music.stop()
        self.logger.log("MIDI播放已停止", "INFO")
    
    def set_volume(self, volume: float):
        """设置音量 (0.0 - 1.0)"""
        self.current_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.current_volume)
    
    def set_tempo(self, tempo: float):
        """设置播放速度倍数"""
        self.current_tempo = max(0.1, min(5.0, tempo))
        # 注意：pygame.mixer.music不支持实时改变速度
        # 这里只是记录设置，实际播放时需要考虑速度调整
    
    def get_playback_status(self) -> Dict[str, Any]:
        """获取播放状态"""
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "volume": self.current_volume,
            "tempo": self.current_tempo,
            "busy": pygame.mixer.music.get_busy() if self.is_playing else False
        }
    
    def extract_notes_from_midi(self, midi_path: str) -> List[Dict[str, Any]]:
        """从MIDI文件中提取音符信息"""
        if not os.path.exists(midi_path):
            self.logger.error(f"MIDI文件不存在: {midi_path}")
            return []
        
        try:
            midi = mido.MidiFile(midi_path)
            notes = []
            tempo = 500000  # 默认120 BPM
            
            for track in midi.tracks:
                track_time = 0
                active_notes = {}
                
                for msg in track:
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    
                    track_time += msg.time
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        active_notes[msg.note] = {
                            'start_time': track_time,
                            'velocity': msg.velocity,
                            'channel': msg.channel
                        }
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        note = msg.note
                        if note in active_notes:
                            start_info = active_notes[note]
                            start_seconds = mido.tick2second(start_info['start_time'], midi.ticks_per_beat, tempo)
                            end_seconds = mido.tick2second(track_time, midi.ticks_per_beat, tempo)
                            
                            notes.append({
                                'note': note,
                                'start_time': start_seconds,
                                'end_time': end_seconds,
                                'duration': end_seconds - start_seconds,
                                'velocity': start_info['velocity'],
                                'channel': start_info['channel']
                            })
                            del active_notes[note]
                
                # 处理未结束的音符
                for note, info in active_notes.items():
                    start_seconds = mido.tick2second(info['start_time'], midi.ticks_per_beat, tempo)
                    notes.append({
                        'note': note,
                        'start_time': start_seconds,
                        'end_time': start_seconds + 0.5,
                        'duration': 0.5,
                        'velocity': info['velocity'],
                        'channel': info['channel']
                    })
            
            # 按开始时间排序
            notes.sort(key=lambda x: x['start_time'])
            
            self.logger.log(f"从MIDI文件中提取了 {len(notes)} 个音符", "INFO")
            return notes
            
        except Exception as e:
            self.logger.error(f"提取MIDI音符失败: {str(e)}")
            return []
    
    def convert_midi_to_events(self, midi_path: str, key_mapping: Dict[int, str]) -> List[Tuple[float, float, List[str]]]:
        """将MIDI文件转换为事件列表 (start_time, end_time, keys)"""
        notes = self.extract_notes_from_midi(midi_path)
        events = []
        
        for note_info in notes:
            midi_note = note_info['note']
            start_time = note_info['start_time']
            end_time = note_info['end_time']
            
            # 映射到键位
            if midi_note in key_mapping:
                key = key_mapping[midi_note]
                events.append((start_time, end_time, [key]))
        
        # 按开始时间排序
        events.sort(key=lambda x: x[0])
        
        self.logger.log(f"MIDI转换为 {len(events)} 个事件", "INFO")
        return events
    
    def cleanup(self):
        """清理资源"""
        if self.is_playing:
            self.stop_midi()
        try:
            pygame.mixer.quit()
        except:
            pass 