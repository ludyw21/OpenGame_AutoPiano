"""
LRCp转换模块
提供MIDI文件到LRCp格式的转换功能
"""

import os
import threading
from typing import List, Dict, Tuple, Optional, Callable
from meowauto.core import Event, Logger

class LrcpConverter:
    """LRCp格式转换器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.is_converting = False
        self.conversion_progress = 0.0
        
    def convert_midi_to_lrcp(self, midi_path: str, output_path: Optional[str] = None, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """将MIDI文件转换为LRCp格式"""
        if self.is_converting:
            self.logger.log("转换已在进行中", "WARNING")
            return False
            
        if not os.path.exists(midi_path):
            self.logger.log(f"MIDI文件不存在: {midi_path}", "ERROR")
            return False
            
        # 如果没有指定输出路径，使用默认路径
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(midi_path))[0]
            output_path = os.path.join(os.path.dirname(midi_path), f"{base_name}.lrcp")
            
        self.is_converting = True
        self.conversion_progress = 0.0
        
        try:
            # 在新线程中执行转换
            convert_thread = threading.Thread(
                target=self._convert_midi_thread, 
                args=(midi_path, output_path, progress_callback)
            )
            convert_thread.daemon = True
            convert_thread.start()
            return True
            
        except Exception as e:
            self.logger.log(f"启动转换失败: {str(e)}", "ERROR")
            self.is_converting = False
            return False
    
    def _convert_midi_thread(self, midi_path: str, output_path: str, 
                           progress_callback: Optional[Callable]):
        """在后台线程中转换MIDI"""
        try:
            self.logger.log("开始转换MIDI到LRCp格式...", "INFO")
            
            # 尝试使用pretty_midi库（如果可用）
            try:
                import pretty_midi
                success = self._convert_with_pretty_midi(midi_path, output_path, progress_callback)
            except ImportError:
                self.logger.log("pretty_midi库不可用，使用mido库", "INFO")
                success = self._convert_with_mido(midi_path, output_path, progress_callback)
            
            if success:
                self.logger.log(f"MIDI转换完成: {output_path}", "SUCCESS")
                if progress_callback:
                    progress_callback(1.0, "转换完成")
            else:
                self.logger.log("MIDI转换失败", "ERROR")
                if progress_callback:
                    progress_callback(0.0, "转换失败")
                    
        except Exception as e:
            error_msg = f"MIDI转换失败: {str(e)}"
            self.logger.log(error_msg, "ERROR")
            if progress_callback:
                progress_callback(0.0, error_msg)
        finally:
            self.is_converting = False
            self.conversion_progress = 0.0
    
    def _convert_with_pretty_midi(self, midi_path: str, output_path: str, 
                                progress_callback: Optional[Callable]) -> bool:
        """使用pretty_midi库转换"""
        try:
            import pretty_midi
            
            # 加载MIDI文件
            midi_data = pretty_midi.PrettyMIDI(midi_path)
            
            # 提取音符事件
            events = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    event = Event(
                        start=note.start,
                        end=note.end,
                        keys=[f"L{note.pitch % 12 + 1}"]  # 简化为LRCp格式
                    )
                    events.append(event)
            
            # 按时间排序
            events.sort(key=lambda e: e.start)
            
            # 生成LRCp内容
            lrcp_content = self._generate_lrcp_content(events, midi_path)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(lrcp_content)
            
            return True
            
        except Exception as e:
            self.logger.log(f"pretty_midi转换失败: {str(e)}", "ERROR")
            return False
    
    def _convert_with_mido(self, midi_path: str, output_path: str, 
                          progress_callback: Optional[Callable]) -> bool:
        """使用mido库转换"""
        try:
            import mido
            
            # 加载MIDI文件
            midi_file = mido.MidiFile(midi_path)
            
            # 提取音符事件
            events = []
            current_time = 0.0
            tempo = 500000  # 默认120 BPM
            
            for track in midi_file.tracks:
                for msg in track:
                    # 更新时间
                    current_time += mido.tick2second(msg.time, midi_file.ticks_per_beat, tempo)
                    
                    # 处理tempo变化
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    
                    # 处理音符事件
                    elif msg.type == 'note_on' and msg.velocity > 0:
                        # 记录音符开始
                        note_start = current_time
                        note_pitch = msg.note
                        
                        # 查找对应的note_off事件
                        note_end = self._find_note_end(track, msg.note, current_time, 
                                                     midi_file.ticks_per_beat, tempo)
                        
                        if note_end > note_start:
                            event = Event(
                                start=note_start,
                                end=note_end,
                                keys=[f"L{note_pitch % 12 + 1}"]  # 简化为LRCp格式
                            )
                            events.append(event)
            
            # 按时间排序
            events.sort(key=lambda e: e.start)
            
            # 生成LRCp内容
            lrcp_content = self._generate_lrcp_content(events, midi_path)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(lrcp_content)
            
            return True
            
        except Exception as e:
            self.logger.log(f"mido转换失败: {str(e)}", "ERROR")
            return False
    
    def _find_note_end(self, track, note_pitch: int, start_time: float, 
                       ticks_per_beat: int, tempo: int) -> float:
        """查找音符结束时间"""
        current_time = start_time
        
        for msg in track:
            if msg.type == 'note_off' and msg.note == note_pitch:
                current_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
                return current_time
            elif msg.type == 'note_on' and msg.note == note_pitch and msg.velocity == 0:
                current_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
                return current_time
            else:
                current_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
        
        # 如果没有找到结束事件，使用默认持续时间
        return start_time + 0.5
    
    def _generate_lrcp_content(self, events: List[Event], midi_path: str) -> str:
        """生成LRCp内容"""
        if not events:
            return f"# 从 {os.path.basename(midi_path)} 转换\n# 未找到音符事件\n"
        
        # 按时间分组
        blocks = []
        for event in events:
            for key in event.keys:
                blocks.append((event.start, event.end, key))
        
        # 分组并生成LRCp
        lrcp_content = self._group_blocks_to_lrcp(blocks)
        
        # 添加头部信息
        header = f"# 从 {os.path.basename(midi_path)} 转换\n"
        header += f"# 总事件数: {len(events)}\n"
        header += f"# 总时长: {events[-1].end:.2f}秒\n\n"
        
        return header + lrcp_content
    
    def _group_blocks_to_lrcp(self, blocks: List[Tuple[float, float, str]], 
                             epsilon: float = 0.03) -> str:
        """将(start,end,token)列表按时间量化并分组，返回LRCp文本"""
        groups: Dict[Tuple[float, float], List[str]] = {}
        
        for start, end, token in blocks:
            qs = self._quantize_time(start)
            qe = self._quantize_time(end)
            key = (qs, qe)
            groups.setdefault(key, []).append(token)
        
        lines: List[str] = []
        
        # 和弦识别：基于度数集合
        def _detect_chord_label(tokens: List[str]) -> Optional[str]:
            digits = {t[1] for t in tokens if isinstance(t, str) and len(t) == 2 
                     and t[0] in ('L','M','H') and t[1].isdigit()}
            if not digits:
                return None
            if digits == {'1','3','5'}:
                return 'C'
            if digits == {'2','4','6'}:
                return 'Dm'
            if digits == {'3','5','7'}:
                return 'Em'
            if digits == {'4','6','1'}:
                return 'F'
            if digits == {'5','7','2'}:
                return 'G'
            if digits == {'6','1','3'}:
                return 'Am'
            if digits == {'5','7','2','4'}:
                return 'G7'
            return None
        
        epsilon_chord = 0.08
        
        for (qs, qe), tokens in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
            start_str = self._seconds_to_timestamp(qs)
            end_str = self._seconds_to_timestamp(qe)
            tokens.sort()
            label = _detect_chord_label(tokens)
            
            # 和弦不阻断单音：输出 和弦名 + 单音tokens
            payload = (label + ' ' if label else '') + ' '.join(tokens)
            thr = epsilon_chord if label else epsilon
            
            # 和弦时间轻微延长
            chord_lead = 0.03
            chord_tail = 0.07
            
            if label:
                qs_ext = max(0.0, qs - chord_lead)
                qe_ext = qe + chord_tail
                start_str_ext = self._seconds_to_timestamp(qs_ext)
                end_str_ext = self._seconds_to_timestamp(qe_ext)
                
                if abs(qe_ext - qs_ext) <= thr:
                    lines.append(f"[{start_str_ext}] {payload}\n")
                else:
                    lines.append(f"[{start_str_ext}][{end_str_ext}] {payload}\n")
            else:
                if abs(qe - qs) <= thr:
                    lines.append(f"[{start_str}] {payload}\n")
                else:
                    lines.append(f"[{start_str}][{end_str}] {payload}\n")
        
        return ''.join(lines)
    
    def _quantize_time(self, t: float, step: float = 0.03) -> float:
        """时间量化，默认30ms栅格（更利于聚合和弦）"""
        return round(t / step) * step
    
    def _seconds_to_timestamp(self, seconds: float) -> str:
        """将秒数转换为时间戳格式 [mm:ss.xxx]"""
        minutes = int(seconds // 60)
        seconds_remainder = seconds % 60
        return f"{minutes:02d}:{seconds_remainder:06.3f}"
    
    def stop_conversion(self):
        """停止转换"""
        self.is_converting = False
        self.logger.log("转换已停止", "INFO")
    
    def get_conversion_status(self) -> dict:
        """获取转换状态"""
        return {
            'is_converting': self.is_converting,
            'progress': self.conversion_progress
        } 