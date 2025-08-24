"""
乐谱工具类
提供乐谱解析和处理的工具函数
"""

import re
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Event:
    """乐谱事件"""
    start: float
    end: float
    keys: List[str]

class ScoreUtils:
    """乐谱工具类"""
    
    def __init__(self):
        # 时间戳正则表达式
        self.TS_RE = re.compile(r'\[(\d+):(\d+\.?\d*)\]')
        # Token正则表达式
        self.TOKEN_RE = re.compile(r'^[LMH][1-7]$|^[CDEFG][m7]?$')
    
    def ts_match_to_seconds(self, m: re.Match) -> float:
        """将时间戳匹配转换为秒数"""
        mm = int(m.group(1))
        ss_str = m.group(2)
        # 处理秒数部分，可能包含小数
        if '.' in ss_str:
            ss_parts = ss_str.split('.')
            ss = int(ss_parts[0])
            ms = int(ss_parts[1].ljust(3, "0"))
        else:
            ss = int(ss_str)
            ms = 0
        return mm * 60 + ss + ms / 1000.0
    
    def parse_line(self, line: str) -> List[Event]:
        """解析一行乐谱：
        1) 延长音： [start][end] TOKENS  -> 在 start 按下，在 end 释放
        2) 多个独立时间： [t1][t2] TOKENS 但若 t1==t2 或未按升序，可视为两个独立 tap
        3) 单时间戳： [t] TOKENS -> tap
        4) 兼容旧写法：多个时间戳后跟 token -> 分别 tap
        """
        ts = list(self.TS_RE.finditer(line))
        if not ts:
            return []
        
        tail_start = ts[-1].end()
        tokens_str = line[tail_start:].strip()
        if not tokens_str:
            return []
        
        tokens = tokens_str.split()
        valid_tokens = [tok for tok in tokens if self.TOKEN_RE.fullmatch(tok)]
        if not valid_tokens:
            return []

        # token -> key 映射
        keys: List[str] = []
        for tok in valid_tokens:
            if tok[0] in ("L", "M", "H"):
                octave = tok[0]
                num = tok[1]
                if octave == "L": 
                    keys.append('a' if num == '1' else 's' if num == '2' else 'd' if num == '3' else 
                               'f' if num == '4' else 'g' if num == '5' else 'h' if num == '6' else 'j')
                elif octave == "M": 
                    keys.append('q' if num == '1' else 'w' if num == '2' else 'e' if num == '3' else 
                               'r' if num == '4' else 't' if num == '5' else 'y' if num == '6' else 'u')
                else:  # H
                    keys.append('1' if num == '1' else '2' if num == '2' else '3' if num == '3' else 
                               '4' if num == '4' else '5' if num == '5' else '6' if num == '6' else '7')
            else:
                # 和弦→底栏单键（与游戏键位一致）
                chord_map = {"C": "z", "Dm": "x", "Em": "c", "F": "v", "G": "b", "Am": "n", "G7": "m"}
                key = chord_map.get(tok)
                if key:
                    keys.append(key)

        events: List[Event] = []
        
        # 延长音情形：恰好两个时间戳且第二个时间 > 第一个
        if len(ts) == 2:
            t1 = self.ts_match_to_seconds(ts[0])
            t2 = self.ts_match_to_seconds(ts[1])
            if t2 > t1:  # 视为延长音
                events.append(Event(start=t1, end=t2, keys=keys.copy()))
                return events
        
        # 其它：全部视为独立 tap
        for m in ts:
            t = self.ts_match_to_seconds(m)
            events.append(Event(start=t, end=t, keys=keys.copy()))
        
        return events
    
    def parse_score(self, text: str) -> List[Event]:
        """解析整个乐谱文本"""
        events: List[Event] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            events.extend(self.parse_line(line))
        
        # 按开始时间排序
        events.sort(key=lambda e: e.start)
        return events

# 保持向后兼容的函数
def _ts_match_to_seconds(m: re.Match) -> float:
    """将时间戳匹配转换为秒数（向后兼容）"""
    utils = ScoreUtils()
    return utils.ts_match_to_seconds(m)

def parse_line(line: str) -> List[Event]:
    """解析一行乐谱（向后兼容）"""
    utils = ScoreUtils()
    return utils.parse_line(line)

def parse_score(text: str) -> List[Event]:
    """解析整个乐谱文本（向后兼容）"""
    utils = ScoreUtils()
    return utils.parse_score(text) 