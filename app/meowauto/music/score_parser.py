"""
乐谱解析模块
提供LRCp格式乐谱的解析功能
"""

import re
from typing import List, Optional
from meowauto.core import Event

# 时间戳正则表达式：形如 [mm:ss.xxx]，毫秒 .xxx 可省略
TS_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")

# 允许的音符 token 正则表达式
TOKEN_RE = re.compile(r'^[LMH]\d+$')

class ScoreParser:
    """乐谱解析器类"""
    
    def __init__(self):
        pass
    
    def parse_score(self, text: str) -> List[Event]:
        """解析整个乐谱文本"""
        return parse_score(text)
    
    def parse_line(self, line: str) -> List[Event]:
        """解析单行乐谱"""
        return parse_line(line)
    
    def validate_score_format(self, text: str) -> bool:
        """验证乐谱格式是否正确"""
        return validate_score_format(text)
    
    def get_score_info(self, events: List[Event]) -> dict:
        """获取乐谱信息统计"""
        return get_score_info(events)

# 保持向后兼容的函数
def parse_score(text: str) -> List[Event]:
    """解析整个乐谱文本"""
    events: List[Event] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        events.extend(parse_line(line))
    
    # 按开始时间排序
    events.sort(key=lambda e: e.start)
    return events

def parse_line(line: str) -> List[Event]:
    """解析单行乐谱"""
    events: List[Event] = []
    
    # 查找所有时间戳
    timestamps = list(TS_RE.finditer(line))
    if len(timestamps) < 1:
        return events
    
    # 提取时间戳后的内容
    content_start = timestamps[-1].end()
    content = line[content_start:].strip()
    
    if not content:
        return events
    
    # 解析音符tokens
    tokens = content.split()
    valid_tokens = [t for t in tokens if TOKEN_RE.match(t)]
    
    if not valid_tokens:
        return events
    
    # 处理时间戳
    if len(timestamps) == 1:
        # 单时间戳：开始时间
        start_time = _parse_timestamp(timestamps[0])
        end_time = start_time + 0.1  # 默认持续时间0.1秒
        
        for token in valid_tokens:
            event = Event(
                start=start_time,
                end=end_time,
                keys=[token]
            )
            events.append(event)
    
    elif len(timestamps) == 2:
        # 双时间戳：开始和结束时间
        start_time = _parse_timestamp(timestamps[0])
        end_time = _parse_timestamp(timestamps[1])
        
        if start_time < end_time:
            for token in valid_tokens:
                event = Event(
                    start=start_time,
                    end=end_time,
                    keys=[token]
                )
                events.append(event)
    
    return events

def _parse_timestamp(match) -> float:
    """解析时间戳为秒数"""
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    milliseconds = int(match.group(3)) if match.group(3) else 0
    
    return minutes * 60 + seconds + milliseconds / 1000.0

def validate_score_format(text: str) -> bool:
    """验证乐谱格式是否正确"""
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # 检查是否包含时间戳
        if not TS_RE.search(line):
            return False
        
        # 检查时间戳后是否有内容
        content_start = TS_RE.search(line).end()
        content = line[content_start:].strip()
        if not content:
            return False
    
    return True

def get_score_info(events: List[Event]) -> dict:
    """获取乐谱信息统计"""
    if not events:
        return {
            'total_events': 0,
            'total_notes': 0,
            'total_time': 0.0,
            'note_distribution': {}
        }
    
    total_events = len(events)
    total_notes = sum(len(event.keys) for event in events)
    total_time = events[-1].end if events else 0.0
    
    # 统计音符分布
    note_distribution = {}
    for event in events:
        for key in event.keys:
            note_distribution[key] = note_distribution.get(key, 0) + 1
    
    return {
        'total_events': total_events,
        'total_notes': total_notes,
        'total_time': total_time,
        'note_distribution': note_distribution
    } 