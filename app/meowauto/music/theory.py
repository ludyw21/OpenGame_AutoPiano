"""
音乐理论处理模块
提供音乐理论分析、和弦识别、调性分析等功能
"""

from typing import List, Dict, Optional, Tuple
from meowauto.core import Event, Logger

class MusicTheoryProcessor:
    """音乐理论处理器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        
        # 定义基本和弦结构
        self.chord_patterns = {
            'major': [0, 4, 7],      # 大三和弦
            'minor': [0, 3, 7],      # 小三和弦
            'diminished': [0, 3, 6],  # 减三和弦
            'augmented': [0, 4, 8],   # 增三和弦
            'major7': [0, 4, 7, 11], # 大七和弦
            'minor7': [0, 3, 7, 10], # 小七和弦
            'dominant7': [0, 4, 7, 10], # 属七和弦
            'diminished7': [0, 3, 6, 9], # 减七和弦
        }
        
        # 定义调性
        self.scales = {
            'C': [0, 2, 4, 5, 7, 9, 11],
            'G': [7, 9, 11, 0, 2, 4, 6],
            'D': [2, 4, 6, 7, 9, 11, 1],
            'A': [9, 11, 1, 2, 4, 6, 8],
            'E': [4, 6, 8, 9, 11, 1, 3],
            'B': [11, 1, 3, 4, 6, 8, 10],
            'F#': [6, 8, 10, 11, 1, 3, 5],
            'C#': [1, 3, 5, 6, 8, 10, 0],
            'F': [5, 7, 9, 10, 0, 2, 4],
            'Bb': [10, 0, 2, 3, 5, 7, 9],
            'Eb': [3, 5, 7, 8, 10, 0, 2],
            'Ab': [8, 10, 0, 1, 3, 5, 7],
            'Db': [1, 3, 5, 6, 8, 10, 0],
            'Gb': [6, 8, 10, 11, 1, 3, 5],
            'Cb': [11, 1, 3, 4, 6, 8, 10],
        }
    
    def analyze_chord(self, notes: List[str]) -> Dict[str, any]:
        """分析和弦结构"""
        if not notes:
            return {'type': 'unknown', 'root': None, 'quality': 'unknown'}
        
        # 将LRCp音符转换为MIDI音高
        midi_notes = []
        for note in notes:
            if len(note) >= 2 and note[0] in 'LMH':
                octave = int(note[1])
                if note[0] == 'L':
                    base_pitch = (octave - 1) * 12
                elif note[0] == 'M':
                    base_pitch = (octave - 1) * 12 + 12
                else:  # H
                    base_pitch = (octave - 1) * 12 + 24
                midi_notes.append(base_pitch)
        
        if not midi_notes:
            return {'type': 'unknown', 'root': None, 'quality': 'unknown'}
        
        # 标准化到八度内
        normalized_notes = [note % 12 for note in midi_notes]
        normalized_notes = list(set(normalized_notes))  # 去重
        normalized_notes.sort()
        
        # 识别和弦类型
        chord_info = self._identify_chord_type(normalized_notes)
        
        return chord_info
    
    def _identify_chord_type(self, notes: List[int]) -> Dict[str, any]:
        """识别和弦类型"""
        if len(notes) < 2:
            return {'type': 'single_note', 'root': notes[0] if notes else None, 'quality': 'single'}
        
        # 计算音程关系
        intervals = []
        for i in range(len(notes) - 1):
            interval = (notes[i+1] - notes[i]) % 12
            if interval == 0:
                interval = 12
            intervals.append(interval)
        
        # 识别和弦类型
        if len(notes) == 2:
            if intervals[0] == 3:
                return {'type': 'dyad', 'root': notes[0], 'quality': 'minor_third'}
            elif intervals[0] == 4:
                return {'type': 'dyad', 'root': notes[0], 'quality': 'major_third'}
            elif intervals[0] == 5:
                return {'type': 'dyad', 'root': notes[0], 'quality': 'perfect_fourth'}
            elif intervals[0] == 7:
                return {'type': 'dyad', 'root': notes[0], 'quality': 'perfect_fifth'}
            else:
                return {'type': 'dyad', 'root': notes[0], 'quality': 'other'}
        
        elif len(notes) == 3:
            # 三和弦识别
            if intervals == [4, 3]:  # 大三度 + 小三度
                return {'type': 'triad', 'root': notes[0], 'quality': 'major'}
            elif intervals == [3, 4]:  # 小三度 + 大三度
                return {'type': 'triad', 'root': notes[0], 'quality': 'minor'}
            elif intervals == [3, 3]:  # 小三度 + 小三度
                return {'type': 'triad', 'root': notes[0], 'quality': 'diminished'}
            elif intervals == [4, 4]:  # 大三度 + 大三度
                return {'type': 'triad', 'root': notes[0], 'quality': 'augmented'}
            else:
                return {'type': 'triad', 'root': notes[0], 'quality': 'other'}
        
        elif len(notes) == 4:
            # 七和弦识别
            if intervals == [4, 3, 4]:  # 大三度 + 小三度 + 大三度
                return {'type': 'seventh', 'root': notes[0], 'quality': 'major7'}
            elif intervals == [3, 4, 3]:  # 小三度 + 大三度 + 小三度
                return {'type': 'seventh', 'root': notes[0], 'quality': 'minor7'}
            elif intervals == [4, 3, 3]:  # 大三度 + 小三度 + 小三度
                return {'type': 'seventh', 'root': notes[0], 'quality': 'dominant7'}
            elif intervals == [3, 3, 3]:  # 小三度 + 小三度 + 小三度
                return {'type': 'seventh', 'root': notes[0], 'quality': 'diminished7'}
            else:
                return {'type': 'seventh', 'root': notes[0], 'quality': 'other'}
        
        else:
            return {'type': 'complex', 'root': notes[0], 'quality': 'complex'}
    
    def detect_key(self, events: List[Event]) -> Dict[str, any]:
        """检测调性"""
        if not events:
            return {'key': 'unknown', 'confidence': 0.0, 'scale_notes': []}
        
        # 统计音符出现频率
        note_frequency = {}
        for event in events:
            for key in event.keys:
                if len(key) >= 2 and key[0] in 'LMH':
                    octave = int(key[1])
                    if key[0] == 'L':
                        base_pitch = (octave - 1) * 12
                    elif key[0] == 'M':
                        base_pitch = (octave - 1) * 12 + 12
                    else:  # H
                        base_pitch = (octave - 1) * 12 + 24
                    note_class = base_pitch % 12
                    note_frequency[note_class] = note_frequency.get(note_class, 0) + 1
        
        if not note_frequency:
            return {'key': 'unknown', 'confidence': 0.0, 'scale_notes': []}
        
        # 计算每个调性的匹配度
        key_scores = {}
        for key_name, scale_notes in self.scales.items():
            score = 0
            for note_class in scale_notes:
                if note_class in note_frequency:
                    score += note_frequency[note_class]
            
            # 考虑调性特征音的重要性
            if 0 in scale_notes and 0 in note_frequency:  # 主音
                score += note_frequency[0] * 0.5
            if 7 in scale_notes and 7 in note_frequency:  # 属音
                score += note_frequency[7] * 0.3
            if 4 in scale_notes and 4 in note_frequency:  # 中音
                score += note_frequency[4] * 0.2
            
            key_scores[key_name] = score
        
        # 找到最佳匹配的调性
        best_key = max(key_scores.items(), key=lambda x: x[1])
        total_notes = sum(note_frequency.values())
        confidence = best_key[1] / total_notes if total_notes > 0 else 0.0
        
        return {
            'key': best_key[0],
            'confidence': confidence,
            'scale_notes': self.scales[best_key[0]],
            'all_scores': key_scores
        }
    
    def analyze_rhythm(self, events: List[Event]) -> Dict[str, any]:
        """分析节奏模式"""
        if not events:
            return {'tempo': 0, 'time_signature': 'unknown', 'rhythm_pattern': []}
        
        # 计算事件间隔
        intervals = []
        for i in range(1, len(events)):
            interval = events[i].start - events[i-1].start
            if interval > 0:
                intervals.append(interval)
        
        if not intervals:
            return {'tempo': 0, 'time_signature': 'unknown', 'rhythm_pattern': []}
        
        # 估算速度
        avg_interval = sum(intervals) / len(intervals)
        estimated_tempo = 60.0 / avg_interval if avg_interval > 0 else 0
        
        # 识别常见速度范围
        tempo_category = 'unknown'
        if estimated_tempo < 60:
            tempo_category = 'largo'
        elif estimated_tempo < 76:
            tempo_category = 'adagio'
        elif estimated_tempo < 108:
            tempo_category = 'andante'
        elif estimated_tempo < 132:
            tempo_category = 'allegretto'
        elif estimated_tempo < 168:
            tempo_category = 'allegro'
        else:
            tempo_category = 'presto'
        
        # 分析节奏模式
        rhythm_pattern = self._analyze_rhythm_pattern(intervals)
        
        return {
            'tempo': round(estimated_tempo, 1),
            'tempo_category': tempo_category,
            'avg_interval': round(avg_interval, 3),
            'rhythm_pattern': rhythm_pattern
        }
    
    def _analyze_rhythm_pattern(self, intervals: List[float]) -> List[str]:
        """分析节奏模式"""
        if not intervals:
            return []
        
        # 将间隔分类为短、中、长
        short_threshold = 0.1  # 100ms
        long_threshold = 0.5   # 500ms
        
        pattern = []
        for interval in intervals:
            if interval < short_threshold:
                pattern.append('short')
            elif interval < long_threshold:
                pattern.append('medium')
            else:
                pattern.append('long')
        
        return pattern
    
    def get_musical_analysis(self, events: List[Event]) -> Dict[str, any]:
        """获取完整的音乐分析"""
        if not events:
            return {
                'chord_analysis': [],
                'key_analysis': {},
                'rhythm_analysis': {},
                'overall_stats': {}
            }
        
        # 和弦分析
        chord_analysis = []
        for event in events:
            if event.keys:
                chord_info = self.analyze_chord(event.keys)
                chord_analysis.append({
                    'time': event.start,
                    'chord': chord_info,
                    'notes': event.keys
                })
        
        # 调性分析
        key_analysis = self.detect_key(events)
        
        # 节奏分析
        rhythm_analysis = self.analyze_rhythm(events)
        
        # 总体统计
        total_events = len(events)
        total_notes = sum(len(event.keys) for event in events)
        total_time = events[-1].end if events else 0.0
        
        overall_stats = {
            'total_events': total_events,
            'total_notes': total_notes,
            'total_time': total_time,
            'avg_notes_per_event': total_notes / total_events if total_events > 0 else 0
        }
        
        return {
            'chord_analysis': chord_analysis,
            'key_analysis': key_analysis,
            'rhythm_analysis': rhythm_analysis,
            'overall_stats': overall_stats
        }
    
    def suggest_improvements(self, events: List[Event]) -> List[str]:
        """提供音乐改进建议"""
        suggestions = []
        
        if not events:
            suggestions.append("乐谱为空，无法提供建议")
            return suggestions
        
        # 分析音乐结构
        analysis = self.get_musical_analysis(events)
        
        # 基于调性的建议
        key_analysis = analysis['key_analysis']
        if key_analysis['confidence'] < 0.6:
            suggestions.append("调性不够明确，建议增加调性特征音")
        
        # 基于节奏的建议
        rhythm_analysis = analysis['rhythm_analysis']
        if rhythm_analysis['tempo'] > 200:
            suggestions.append("速度过快，可能影响演奏准确性")
        elif rhythm_analysis['tempo'] < 40:
            suggestions.append("速度过慢，可能影响音乐表现力")
        
        # 基于和弦的建议
        chord_analysis = analysis['chord_analysis']
        complex_chords = [c for c in chord_analysis if c['chord']['type'] == 'complex']
        if len(complex_chords) > len(chord_analysis) * 0.3:
            suggestions.append("复杂和弦较多，建议简化以提高可演奏性")
        
        # 基于音符密度的建议
        overall_stats = analysis['overall_stats']
        if overall_stats['avg_notes_per_event'] > 5:
            suggestions.append("单事件音符过多，建议分散到多个事件中")
        
        if not suggestions:
            suggestions.append("音乐结构良好，无需特别改进")
        
        return suggestions 