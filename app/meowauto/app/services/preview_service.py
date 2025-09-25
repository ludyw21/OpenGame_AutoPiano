# -*- coding: utf-8 -*-
"""
PreviewService: 处理试听服务
- 专门用于实现处理解析后的MIDI数据并播放音频，但不触发按键模拟的功能
- 为电子琴的"处理试听"按钮提供支持
"""
from typing import Any, Callable, Optional, Dict, List
import os
import tempfile
from meowauto.core import Logger
from meowauto.midi import analyzer
from meowauto.audio import midi_processor

class PreviewService:
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self.midi_processor = None
        self.analysis_settings: Dict[str, Any] = {
            'auto_transpose': False,       # 不自动移调以保留原始音乐特性
            'manual_semitones': 0,         # 当 auto_transpose=False 时使用
            'min_note_duration_ms': 0,    # 短音阈值（仅对非鼓），默认25ms
        }
        # 最近一次分析统计
        self.last_analysis_stats: Dict[str, Any] = {'k': 0, 'white_rate': None}
        # 播放状态
        self.is_previewing = False
        self.current_midi_path = None

    def init_processor(self) -> None:
        """初始化MIDI处理器"""
        try:
            if self.midi_processor is None:
                self.midi_processor = midi_processor.MidiProcessor(self.logger)
        except Exception as e:
            self.logger.error(f"初始化MIDI处理器失败: {e}")
            self.midi_processor = None

    def process_and_preview_midi(self, 
                                midi_path: str, 
                                tempo: float = 1.0, 
                                volume: float = 0.7, 
                                use_analyzed: bool = False, 
                                analyzed_notes: Optional[List[Dict]] = None, 
                                on_progress: Optional[Callable[[float], None]] = None, 
                                on_complete: Optional[Callable] = None, 
                                on_error: Optional[Callable[[str], None]] = None) -> bool:
        """
        处理MIDI数据并播放预览音频，但不触发按键模拟
        
        参数:
            midi_path: MIDI文件路径
            tempo: 播放速度
            volume: 播放音量
            use_analyzed: 是否使用已解析的音符数据
            analyzed_notes: 已解析的音符数据（当use_analyzed=True时有效）
            on_progress: 进度回调函数
            on_complete: 完成回调函数
            on_error: 错误回调函数
            
        返回:
            bool: 操作是否成功
        """
        # 检查文件是否存在
        if not os.path.exists(midi_path):
            error_msg = f"MIDI文件不存在: {midi_path}"
            self.logger.error(error_msg)
            if on_error:
                on_error(error_msg)
            return False

        self.init_processor()
        if not self.midi_processor:
            error_msg = "MIDI处理器初始化失败"
            self.logger.error(error_msg)
            if on_error:
                on_error(error_msg)
            return False

        try:
            # 如果有已解析的音符数据，直接使用原始数据生成临时MIDI
            if use_analyzed and analyzed_notes:
                # 使用分析参数设置处理音符数据
                self.logger.info(f"开始处理音符数据，原始数量: {len(analyzed_notes)}")
                # 应用过滤和移调处理
                processed_notes = self._apply_pre_filters_and_transpose(analyzed_notes)
                analyzed_notes = processed_notes
                
                # 检查是否包含解析结果元数据
                if isinstance(analyzed_notes, dict) and 'notes' in analyzed_notes:
                    # 如果是完整的解析结果对象
                    notes = analyzed_notes['notes']
                    # 复制元数据到音符中以便在导出时使用
                    for note in notes:
                        if 'initial_tempo' in analyzed_notes:
                            note['initial_tempo'] = analyzed_notes['initial_tempo']
                        if 'resolution' in analyzed_notes:
                            note['resolution'] = analyzed_notes['resolution']
                    analyzed_notes = notes
                
                # 将原始音符数据转换为临时MIDI文件进行播放
                temp_midi_path = self._export_notes_to_temp_midi(analyzed_notes)
                if temp_midi_path:
                    midi_path = temp_midi_path

            # 更新播放状态
            self.is_previewing = True
            self.current_midi_path = midi_path

            # 设置进度回调增强版，集成完成和错误处理
            def enhanced_progress_callback(progress, current_time=None, total_time=None):
                if on_progress:
                    # 兼容原有的进度回调格式
                    if callable(on_progress) and len(on_progress.__code__.co_varnames) == 1:
                        on_progress(progress)
                    else:
                        # 提供更详细的进度信息
                        progress_info = {
                            'progress': progress,
                            'current_time': current_time,
                            'total_time': total_time
                        }
                        on_progress(progress_info)
                
                # 播放完成检查
                if progress >= 100 and on_complete:
                    # 保存需要删除的临时文件路径
                    temp_path_to_delete = self.current_midi_path if temp_midi_path else None
                    
                    self.is_previewing = False
                    self.current_midi_path = None
                    
                    # 删除临时文件
                    if temp_path_to_delete and temp_path_to_delete != midi_path:
                        self._cleanup_temp_file(temp_path_to_delete)
                    
                    on_complete()

            # 播放MIDI文件
            success = self.midi_processor.play_midi(midi_path, progress_callback=enhanced_progress_callback)
            
            if success:
                self.logger.info(f"开始处理试听: {os.path.basename(midi_path)}, 速度: {tempo}, 音量: {volume}")
                # 设置速度和音量
                try:
                    if hasattr(self.midi_processor, 'set_tempo'):
                        self.midi_processor.set_tempo(tempo)
                    if hasattr(self.midi_processor, 'set_volume'):
                        self.midi_processor.set_volume(volume)
                except Exception as e:
                    self.logger.warning(f"设置速度或音量时出错: {e}")
            else:
                self.is_previewing = False
                self.current_midi_path = None
                error_msg = "MIDI播放失败"
                self.logger.error(error_msg)
                if on_error:
                    on_error(error_msg)
            
            return success
            
        except Exception as e:
            self.is_previewing = False
            self.current_midi_path = None
            error_msg = f"处理试听时发生错误: {str(e)}"
            self.logger.error(error_msg)
            if on_error:
                on_error(error_msg)
            return False

    def _apply_pre_filters_and_transpose(self, notes: List[Dict]) -> List[Dict]:
        """应用前置过滤器和移调处理"""
        try:
            # 提取设置
            auto_transpose = self.analysis_settings.get('auto_transpose', True)
            manual_k = self.analysis_settings.get('manual_semitones', 0)
            min_ms = self.analysis_settings.get('min_note_duration_ms', 25)
            
            # 复制原始数据以避免修改
            processed_notes = []
            
            # 短音过滤
            if min_ms > 0:
                for note in notes:
                    # 尝试获取duration_ms（毫秒）或duration（秒）
                    duration_ms = note.get('duration_ms', 0)
                    if duration_ms == 0:
                        # 如果没有duration_ms，尝试使用duration（秒）并转换为毫秒
                        duration_seconds = note.get('duration', 0)
                        duration_ms = duration_seconds * 1000
                    
                    if duration_ms >= min_ms:
                        processed_notes.append(note.copy())
            else:
                processed_notes = [note.copy() for note in notes]
            
            # 移调处理
            if auto_transpose:
                # 自动移调逻辑 - 寻找最佳的移调量以最大化白键率
                if processed_notes:
                    k, white_rate = self._find_best_transpose(processed_notes)
                    self.last_analysis_stats = {'k': k, 'white_rate': white_rate}
                    
                    # 应用移调
                    for note in processed_notes:
                        note['note'] = note.get('note', 0) + k
            elif manual_k != 0:
                # 手动移调
                for note in processed_notes:
                    note['note'] = note.get('note', 0) + manual_k
                self.last_analysis_stats = {'k': manual_k, 'white_rate': None}
            
            self.logger.info(f"[Preview] 音符处理完成: 原始={len(notes)}, 过滤/移调后={len(processed_notes)}, "
                           f"k={self.last_analysis_stats.get('k')}, white_rate={self.last_analysis_stats.get('white_rate')}")
            
            return processed_notes
        except Exception as e:
            self.logger.error(f"应用前置过滤器和移调处理失败: {e}")
            return notes  # 失败时返回原始数据

    def _find_best_transpose(self, notes: List[Dict]) -> tuple[int, float]:
        """寻找最佳移调量以最大化白键率"""
        try:
            # 收集所有音符值
            all_notes = [note.get('note', 0) for note in notes]
            
            # 尝试不同的移调量(-6到+6)并计算白键率
            best_k = 0
            best_white_rate = 0
            
            for k in range(-6, 7):
                white_count = 0
                total_count = 0
                
                for note in all_notes:
                    transposed_note = note + k
                    # C(0), D(2), E(4), F(5), G(7), A(9), B(11) 是白键
                    if transposed_note % 12 in (0, 2, 4, 5, 7, 9, 11):
                        white_count += 1
                    total_count += 1
                
                if total_count > 0:
                    white_rate = white_count / total_count
                    if white_rate > best_white_rate:
                        best_white_rate = white_rate
                        best_k = k
            
            return best_k, best_white_rate
        except Exception as e:
            self.logger.error(f"寻找最佳移调量失败: {e}")
            return 0, 0

    def _export_notes_to_temp_midi(self, notes: List[Dict]) -> Optional[str]:
        """将音符数据导出为临时MIDI文件"""
        try:
            # 尝试导入mido库
            import mido
            import tempfile
            import time
            from datetime import datetime
            
            # 创建临时文件路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_dir = tempfile.gettempdir()
            temp_midi_path = os.path.join(temp_dir, f"preview_temp_{timestamp}.mid")
            
            # 创建MIDI文件
            # 使用与原始MIDI相同的时间分辨率，如果能从音符数据中获取
            ticks_per_beat = 480  # 默认值
            # 尝试从音符数据或解析结果中获取分辨率
            if notes and any('resolution' in note for note in notes):
                for note in notes:
                    if 'resolution' in note:
                        ticks_per_beat = note['resolution']
                        break
            
            # 获取tempo信息，优先使用全局tempo
            global_tempo = None
            # 检查音符数据中是否有单独的tempo信息
            if notes and 'initial_tempo' in notes[0]:
                # 尝试从第一个音符获取原始tempo
                bpm = notes[0]['initial_tempo']
                global_tempo = mido.bpm2tempo(bpm) if bpm else mido.bpm2tempo(120)
            # 如果没有全局tempo，尝试从每个音符获取
            elif notes and any('tempo' in note for note in notes):
                # 找到第一个有tempo的音符
                for note in notes:
                    if 'tempo' in note:
                        global_tempo = note['tempo']
                        break
            # 默认tempo
            if global_tempo is None:
                global_tempo = mido.bpm2tempo(120)  # 默认120 BPM
            
            self.logger.info(f"使用ticks_per_beat={ticks_per_beat}, tempo={mido.tempo2bpm(global_tempo):.2f} BPM")
            
            midi_file = mido.MidiFile(ticks_per_beat=ticks_per_beat)
            track = mido.MidiTrack()
            midi_file.tracks.append(track)
            
            # 添加tempo消息
            track.append(mido.MetaMessage('set_tempo', tempo=global_tempo, time=0))
            
            # 处理音符数据
            if not notes:
                self.logger.warning("没有音符数据可导出为MIDI文件")
                return None
            
            # 分离所有note_on和note_off事件，并按时间排序
            events = []
            for note_info in notes:
                start_time = note_info.get('start_time', 0)
                end_time = note_info.get('end_time', start_time + 0.5)
                note = note_info.get('note', 60)
                velocity = min(127, max(0, note_info.get('velocity', 64)))
                channel = min(15, max(0, note_info.get('channel', 0)))
                
                # 转换时间为ticks
                start_tick = int(mido.second2tick(start_time, ticks_per_beat, global_tempo))
                end_tick = int(mido.second2tick(end_time, ticks_per_beat, global_tempo))
                
                # 添加note_on事件
                events.append({
                    'tick': start_tick,
                    'type': 'note_on',
                    'note': note,
                    'velocity': velocity,
                    'channel': channel
                })
                
                # 添加note_off事件
                events.append({
                    'tick': end_tick,
                    'type': 'note_off',
                    'note': note,
                    'velocity': 0,
                    'channel': channel
                })
            
            # 按tick排序所有事件，如果tick相同，note_off事件优先于note_on事件
            events.sort(key=lambda x: (x['tick'], 1 if x['type'] == 'note_on' else 0))
            
            # 跟踪上一个事件的tick
            last_tick = 0
            
            # 生成MIDI消息
            for event in events:
                delta_time = max(0, event['tick'] - last_tick)
                if event['type'] == 'note_on':
                    track.append(mido.Message('note_on', 
                                            note=event['note'], 
                                            velocity=event['velocity'], 
                                            channel=event['channel'], 
                                            time=delta_time))
                else:  # note_off
                    track.append(mido.Message('note_off', 
                                            note=event['note'], 
                                            velocity=event['velocity'], 
                                            channel=event['channel'], 
                                            time=delta_time))
                last_tick = event['tick']
            
            # 添加end_of_track消息
            track.append(mido.MetaMessage('end_of_track', time=0))
            
            # 保存MIDI文件
            midi_file.save(temp_midi_path)
            
            self.logger.info(f"成功导出临时MIDI文件: {os.path.basename(temp_midi_path)}, 包含 {len(notes)} 个音符, 生成 {len(events)} 个MIDI事件")
            return temp_midi_path
            
            # 添加end_of_track消息
            track.append(mido.MetaMessage('end_of_track', time=0))
            
            # 保存MIDI文件
            midi_file.save(temp_midi_path)
            
            self.logger.info(f"成功导出临时MIDI文件: {os.path.basename(temp_midi_path)}, 包含 {len(notes)} 个音符")
            return temp_midi_path
        except ImportError:
            self.logger.error("无法导入mido库，无法导出MIDI文件")
            return None
        except Exception as e:
            self.logger.error(f"导出音符数据为临时MIDI文件失败: {e}")
            return None

    def stop_preview(self) -> None:
        """停止当前的试听播放"""
        try:
            if self.midi_processor and self.is_previewing:
                # 保存需要删除的临时文件路径
                temp_path_to_delete = self.current_midi_path
                
                self.midi_processor.stop_midi()
                self.is_previewing = False
                self.current_midi_path = None
                
                # 删除临时文件
                if temp_path_to_delete and temp_path_to_delete.startswith(tempfile.gettempdir()):
                    self._cleanup_temp_file(temp_path_to_delete)
                
                self.logger.info("试听播放已停止")
        except Exception as e:
            self.logger.error(f"停止试听播放时出错: {e}")

    def is_preview_active(self) -> bool:
        """检查是否正在试听"""
        return self.is_previewing
    
    def _cleanup_temp_file(self, file_path: str) -> None:
        """清理临时文件"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"已删除临时MIDI文件: {os.path.basename(file_path)}")
        except Exception as e:
            self.logger.warning(f"删除临时MIDI文件时出错: {e}")

    def get_preview_status(self) -> Dict[str, Any]:
        """获取试听状态"""
        return {
            'is_previewing': self.is_previewing,
            'current_midi_path': self.current_midi_path,
            'analysis_settings': self.analysis_settings,
            'last_analysis_stats': self.last_analysis_stats
        }

    def configure_analysis_settings(self, **kwargs) -> None:
        """配置分析设置"""
        for key, value in kwargs.items():
            if key in self.analysis_settings:
                self.analysis_settings[key] = value
        self.logger.info(f"已更新分析设置: {self.analysis_settings}")

    def get_last_analysis_stats(self) -> Dict[str, Any]:
        """获取最后一次分析的统计信息"""
        return self.last_analysis_stats.copy()

# 单例模式支持
_preview_service_instance = None

def get_preview_service(logger: Optional[Logger] = None) -> PreviewService:
    """获取PreviewService的单例实例"""
    global _preview_service_instance
    if _preview_service_instance is None:
        _preview_service_instance = PreviewService(logger)
    return _preview_service_instance
