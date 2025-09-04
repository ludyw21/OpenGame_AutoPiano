"""
音乐理论模块
提供乐谱解析、LRCp转换、音乐理论处理等功能
"""

from .theory import MusicTheoryProcessor
from .lrcp_converter import LrcpConverter
from .score_parser import ScoreParser

__all__ = [
    'MusicTheoryProcessor',
    'LrcpConverter', 
    'ScoreParser'
] 