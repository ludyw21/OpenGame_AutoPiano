"""
MIDI工具类
提供MIDI处理和转换的工具函数
"""

import os
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

class MidiUtils:
    """MIDI工具类"""
    
    def __init__(self):
        pass
    
    def token_from_midi_note(self, midi_note: int) -> Optional[str]:
        """将任意MIDI音符映射为L/M/H的1-7标记（21键），含半音折叠到邻近度数）。
        - 折叠到C3~B5（48~83）
        - 48-59→L，60-71→M，72-83→H
        - 半音分组：C/C#→1, D/D#→2, E→3, F/F#→4, G/G#→5, A/A#→6, B→7
        """
        if midi_note is None:
            return None
        n = int(midi_note)
        # 折叠到C3~B5
        while n < 48:
            n += 12
        while n > 83:
            n -= 12
        # 前缀
        if 48 <= n <= 59:
            prefix = 'L'
        elif 60 <= n <= 71:
            prefix = 'M'
        elif 72 <= n <= 83:
            prefix = 'H'
        else:
            return None
        pc = n % 12
        if pc in (0, 1):
            digit = '1'
        elif pc in (2, 3):
            digit = '2'
        elif pc == 4:
            digit = '3'
        elif pc in (5, 6):
            digit = '4'
        elif pc in (7, 8):
            digit = '5'
        elif pc in (9, 10):
            digit = '6'
        else:
            digit = '7'
        return prefix + digit
    
    def quantize_time(self, t: float, step: float = 0.03) -> float:
        """时间量化，默认30ms栅格（更利于聚合和弦）"""
        return round(t / step) * step
    
    def seconds_to_timestamp(self, seconds: float) -> str:
        """将秒数转换为时间戳格式 [分:秒.毫秒]"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"
    
    def group_blocks_to_lrcp(self, blocks: List[Tuple[float, float, str]], epsilon: float = 0.03) -> str:
        """将(start,end,token)列表按时间量化并分组，返回LRCp文本"""
        groups: Dict[Tuple[float, float], List[str]] = {}
        for start, end, token in blocks:
            qs = self.quantize_time(start)
            qe = self.quantize_time(end)
            key = (qs, qe)
            groups.setdefault(key, []).append(token)
        
        lines: List[str] = []
        epsilon_chord = 0.08
        
        for (qs, qe), tokens in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
            start_str = self.seconds_to_timestamp(qs)
            end_str = self.seconds_to_timestamp(qe)
            tokens.sort()
            
            # 和弦识别：基于度数集合
            label = self._detect_chord_label(tokens)
            
            # 和弦不阻断单音：输出 和弦名 + 单音tokens
            payload = (label + ' ' if label else '') + ' '.join(tokens)
            thr = epsilon_chord if label else epsilon
            
            # 和弦时间轻微延长
            chord_lead = 0.03
            chord_tail = 0.07
            
            if label:
                qs_ext = max(0.0, qs - chord_lead)
                qe_ext = qe + chord_tail
                start_str_ext = self.seconds_to_timestamp(qs_ext)
                end_str_ext = self.seconds_to_timestamp(qe_ext)
                
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
    
    def _detect_chord_label(self, tokens: List[str]) -> Optional[str]:
        """根据度数组合识别 C/Dm/Em/F/G/Am/G7 和弦名。"""
        digits = {t[1] for t in tokens if isinstance(t, str) and len(t) == 2 and t[0] in ('L','M','H') and t[1].isdigit()}
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
    
    def generate_lrcp_header(self, midi_path: str) -> str:
        """生成LRCp文件头部信息"""
        return (f"# 从MIDI文件转换: {os.path.basename(midi_path)}\n"
                f"# 转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"# 格式: [开始时间][结束时间] 音符\n\n")

# 保持向后兼容的函数
def _token_from_midi_note(midi_note: int) -> Optional[str]:
    """将任意MIDI音符映射为L/M/H的1-7标记（向后兼容）"""
    utils = MidiUtils()
    return utils.token_from_midi_note(midi_note)

def _quantize_time(t: float, step: float = 0.03) -> float:
    """时间量化，默认30ms栅格（向后兼容）"""
    utils = MidiUtils()
    return utils.quantize_time(t, step)

def _group_blocks_to_lrcp(blocks, epsilon: float = 0.03):
    """将(start,end,token)列表按时间量化并分组，返回LRCp文本（向后兼容）"""
    utils = MidiUtils()
    return utils.group_blocks_to_lrcp(blocks, epsilon)

def _detect_chord_label(tokens: List[str]) -> Optional[str]:
    """根据度数组合识别 C/Dm/Em/F/G/Am/G7 和弦名（向后兼容）"""
    utils = MidiUtils()
    return utils._detect_chord_label(tokens)

def _seconds_to_timestamp(seconds: float) -> str:
    """将秒数转换为时间戳格式（向后兼容）"""
    utils = MidiUtils()
    return utils.seconds_to_timestamp(seconds) 