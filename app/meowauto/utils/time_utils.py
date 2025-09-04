"""
时间工具类
提供时间处理和格式化的工具函数
"""

import re
from typing import Optional

class TimeUtils:
    """时间工具类"""
    
    def __init__(self):
        # 时间戳正则表达式
        self.TS_RE = re.compile(r'\[(\d+):(\d+\.?\d*)\]')
    
    def ts_match_to_seconds(self, m: re.Match) -> float:
        """将时间戳匹配转换为秒数"""
        mm = int(m.group(1))
        ss = int(m.group(2))
        ms = int((m.group(3) or "0").ljust(3, "0"))
        return mm * 60 + ss + ms / 1000.0
    
    def quantize_time(self, t: float, step: float = 0.03) -> float:
        """时间量化，默认30ms栅格（更利于聚合和弦）"""
        return round(t / step) * step
    
    def seconds_to_timestamp(self, seconds: float) -> str:
        """将秒数转换为时间戳格式 [分:秒.毫秒]"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"
    
    def format_time_display(self, current_time: float, total_time: float) -> str:
        """格式化时间显示"""
        def format_seconds(seconds: float) -> str:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        
        current_str = format_seconds(current_time)
        total_str = format_seconds(total_time)
        return f"{current_str} / {total_str}"
    
    def parse_timestamp(self, timestamp: str) -> Optional[float]:
        """解析时间戳字符串为秒数"""
        match = self.TS_RE.match(timestamp)
        if match:
            return self.ts_match_to_seconds(match)
        return None

# 保持向后兼容的函数
def _ts_match_to_seconds(m: re.Match) -> float:
    """将时间戳匹配转换为秒数（向后兼容）"""
    utils = TimeUtils()
    return utils.ts_match_to_seconds(m)

def _quantize_time(t: float, step: float = 0.03) -> float:
    """时间量化，默认30ms栅格（向后兼容）"""
    utils = TimeUtils()
    return utils.quantize_time(t, step)

def _seconds_to_timestamp(seconds: float) -> str:
    """将秒数转换为时间戳格式（向后兼容）"""
    utils = TimeUtils()
    return utils.seconds_to_timestamp(seconds) 