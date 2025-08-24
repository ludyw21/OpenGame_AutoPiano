"""
MIDI播放模块
提供MIDI文件的播放、暂停、停止等控制功能
"""

import os
import time
import threading
from typing import Optional, Callable, Dict, Any
from meowauto.core import Logger

class MidiPlayer:
    """MIDI播放器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.playback_thread = None
        self.current_volume = 0.7
        self.current_tempo = 1.0
        
        # 播放回调
        self.playback_callbacks = {
            'on_start': None,
            'on_stop': None,
            'on_pause': None,
            'on_resume': None,
            'on_progress': None,
            'on_complete': None,
            'on_error': None
        }
        
        # 初始化pygame音频
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(self.current_volume)
            self.pygame_available = True
            self.logger.log("MIDI播放器初始化成功", "SUCCESS")
        except Exception as e:
            self.pygame_available = False
            self.logger.log(f"MIDI播放器初始化失败: {str(e)}", "WARNING")
    
    def set_callbacks(self, **callbacks):
        """设置回调函数"""
        for key, callback in callbacks.items():
            if key in self.playback_callbacks:
                self.playback_callbacks[key] = callback
    
    def play_midi(self, midi_file: str, progress_callback: Optional[Callable] = None) -> bool:
        """播放MIDI文件"""
        if not self.pygame_available:
            self.logger.log("pygame不可用，无法播放MIDI", "ERROR")
            return False
        
        if not os.path.exists(midi_file):
            self.logger.log(f"MIDI文件不存在: {midi_file}", "ERROR")
            return False
        
        if self.is_playing:
            self.stop_midi()
        
        try:
            import pygame
            
            # 加载MIDI文件
            pygame.mixer.music.load(midi_file)
            pygame.mixer.music.play()
            
            self.current_file = midi_file
            self.is_playing = True
            self.is_paused = False
            
            # 启动播放监控线程
            self.playback_thread = threading.Thread(
                target=self._playback_monitor_thread,
                args=(progress_callback,)
            )
            self.playback_thread.daemon = True
            self.playback_thread.start()
            
            # 调用开始回调
            if self.playback_callbacks['on_start']:
                self.playback_callbacks['on_start']()
            
            self.logger.log(f"开始播放MIDI文件: {os.path.basename(midi_file)}", "INFO")
            return True
            
        except Exception as e:
            error_msg = f"播放MIDI文件失败: {str(e)}"
            self.logger.log(error_msg, "ERROR")
            if self.playback_callbacks['on_error']:
                self.playback_callbacks['on_error'](error_msg)
            return False
    
    def pause_midi(self):
        """暂停播放"""
        if not self.is_playing or not self.pygame_available:
            return
        
        try:
            import pygame
            
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                self.is_paused = True
                
                # 调用暂停回调
                if self.playback_callbacks['on_pause']:
                    self.playback_callbacks['on_pause']()
                
                self.logger.log("MIDI播放已暂停", "INFO")
            
        except Exception as e:
            self.logger.log(f"暂停播放失败: {str(e)}", "ERROR")
    
    def resume_midi(self):
        """恢复播放"""
        if not self.is_playing or not self.is_paused or not self.pygame_available:
            return
        
        try:
            import pygame
            
            pygame.mixer.music.unpause()
            self.is_paused = False
            
            # 调用恢复回调
            if self.playback_callbacks['on_resume']:
                self.playback_callbacks['on_resume']()
            
            self.logger.log("MIDI播放已恢复", "INFO")
            
        except Exception as e:
            self.logger.log(f"恢复播放失败: {str(e)}", "ERROR")
    
    def stop_midi(self):
        """停止播放"""
        if not self.is_playing or not self.pygame_available:
            return
        
        try:
            import pygame
            
            pygame.mixer.music.stop()
            self.is_playing = False
            self.is_paused = False
            
            # 等待监控线程结束
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)
            
            # 调用停止回调
            if self.playback_callbacks['on_stop']:
                self.playback_callbacks['on_stop']()
            
            self.logger.log("MIDI播放已停止", "INFO")
            
        except Exception as e:
            self.logger.log(f"停止播放失败: {str(e)}", "ERROR")
    
    def set_volume(self, volume: float):
        """设置音量 (0.0 - 1.0)"""
        if not self.pygame_available:
            return
        
        try:
            import pygame
            
            volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(volume)
            self.current_volume = volume
            
            self.logger.log(f"音量已设置为: {volume:.2f}", "INFO")
            
        except Exception as e:
            self.logger.log(f"设置音量失败: {str(e)}", "ERROR")
    
    def set_tempo(self, tempo: float):
        """设置播放速度 (0.5 - 2.0)"""
        if not self.pygame_available:
            return
        
        try:
            import pygame
            
            tempo = max(0.5, min(2.0, tempo))
            # pygame.mixer.music不支持直接设置速度，这里只是记录
            self.current_tempo = tempo
            
            self.logger.log(f"播放速度已设置为: {tempo:.2f}x", "INFO")
            
        except Exception as e:
            self.logger.log(f"设置播放速度失败: {str(e)}", "ERROR")
    
    def _playback_monitor_thread(self, progress_callback: Optional[Callable] = None):
        """播放监控线程"""
        try:
            import pygame
            
            start_time = time.time()
            
            # 获取MIDI文件信息
            try:
                import mido
                midi = mido.MidiFile(self.current_file)
                total_time = midi.length
            except:
                total_time = 60.0  # 默认1分钟
            
            # 播放循环
            while self.is_playing and pygame.mixer.music.get_busy():
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # 计算播放进度
                current_time = time.time() - start_time
                progress = min(100, (current_time / total_time) * 100)
                
                # 调用进度回调
                if progress_callback:
                    try:
                        current_str = time.strftime("%M:%S", time.gmtime(current_time))
                        total_str = time.strftime("%M:%S", time.gmtime(total_time))
                        progress_callback(progress, current_str, total_str)
                    except Exception:
                        pass
                
                if self.playback_callbacks['on_progress']:
                    try:
                        self.playback_callbacks['on_progress'](progress)
                    except Exception:
                        pass
                
                time.sleep(0.1)  # 更新频率
            
            # 播放完成
            if self.is_playing:  # 只有在正常完成时才调用完成回调
                if self.playback_callbacks['on_complete']:
                    self.playback_callbacks['on_complete']()
                self.logger.log("MIDI播放完成", "SUCCESS")
            
        except Exception as e:
            error_msg = f"播放监控失败: {str(e)}"
            self.logger.log(error_msg, "ERROR")
            if self.playback_callbacks['on_error']:
                self.playback_callbacks['on_error'](error_msg)
        finally:
            self.is_playing = False
    
    def get_playback_status(self) -> Dict[str, Any]:
        """获取播放状态"""
        if not self.pygame_available:
            return {
                'is_playing': False,
                'is_paused': False,
                'current_file': None,
                'volume': 0.0,
                'tempo': 1.0,
                'pygame_available': False
            }
        
        try:
            import pygame
            
            return {
                'is_playing': self.is_playing,
                'is_paused': self.is_paused,
                'current_file': self.current_file,
                'volume': self.current_volume,
                'tempo': self.current_tempo,
                'pygame_available': True,
                'is_busy': pygame.mixer.music.get_busy() if self.is_playing else False
            }
        except Exception:
            return {
                'is_playing': False,
                'is_paused': False,
                'current_file': None,
                'volume': 0.0,
                'tempo': 1.0,
                'pygame_available': False
            }
    
    def get_midi_info(self, midi_file: str) -> Dict[str, Any]:
        """获取MIDI文件信息"""
        if not os.path.exists(midi_file):
            return {'error': '文件不存在'}
        
        try:
            import mido
            
            midi = mido.MidiFile(midi_file)
            
            # 分析音符
            note_count = 0
            for track in midi.tracks:
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        note_count += 1
            
            return {
                'tracks': len(midi.tracks),
                'length': midi.length,
                'ticks_per_beat': midi.ticks_per_beat,
                'note_count': note_count,
                'file_size': os.path.getsize(midi_file)
            }
            
        except Exception as e:
            return {'error': f'解析失败: {str(e)}'}
    
    def seek_to(self, position: float):
        """跳转到指定位置（秒）"""
        if not self.is_playing or not self.pygame_available:
            return
        
        try:
            import pygame
            
            # pygame.mixer.music不支持直接跳转，需要重新加载
            if self.current_file:
                self.stop_midi()
                time.sleep(0.1)  # 短暂等待
                self.play_midi(self.current_file)
                
                self.logger.log(f"跳转到位置: {position:.2f}秒", "INFO")
            
        except Exception as e:
            self.logger.log(f"跳转失败: {str(e)}", "ERROR") 