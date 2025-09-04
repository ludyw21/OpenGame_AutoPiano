"""
和弦工具类
提供和弦识别和处理的工具函数
"""

from typing import Optional, Dict

class ChordUtils:
    """和弦工具类"""
    
    def __init__(self):
        # 和弦键位映射
        self.chord_key_mapping = {
            "C": "z", "Dm": "x", "Em": "c", "F": "v", 
            "G": "b", "Am": "n", "G7": "m"
        }
    
    def digit_from_token(self, token: Optional[str]) -> Optional[str]:
        """从token中提取度数"""
        if not token or len(token) != 2:
            return None
        d = token[1]
        return d if d in '1234567' else None
    
    def digit_to_chord_key(self, digit: Optional[str], key_mapping: Dict[str, str] = None) -> Optional[str]:
        """将度数转换为和弦键位"""
        if not digit:
            return None
        
        # 使用传入的键位映射或默认映射
        mapping = key_mapping or self.chord_key_mapping
        
        chord_order = ['C', 'Dm', 'Em', 'F', 'G', 'Am', 'G7']
        # 1..7 -> C..G7
        try:
            chord_name = chord_order[int(digit) - 1]
        except Exception:
            return None
        
        key = mapping.get(chord_name)
        return key
    
    def detect_chord_label(self, tokens: list) -> Optional[str]:
        """根据度数组合识别 C/Dm/Em/F/G/Am/G7 和弦名"""
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
    
    def get_chord_key(self, chord_name: str) -> Optional[str]:
        """获取和弦对应的键位"""
        return self.chord_key_mapping.get(chord_name)
    
    def get_all_chord_keys(self) -> Dict[str, str]:
        """获取所有和弦键位映射"""
        return self.chord_key_mapping.copy()

# 保持向后兼容的函数
def _digit_from_token(token: Optional[str]) -> Optional[str]:
    """从token中提取度数（向后兼容）"""
    utils = ChordUtils()
    return utils.digit_from_token(token)

def _digit_to_chord_key(digit: Optional[str], key_mapping: Dict[str, str] = None) -> Optional[str]:
    """将度数转换为和弦键位（向后兼容）"""
    utils = ChordUtils()
    return utils.digit_to_chord_key(digit, key_mapping)

def _detect_chord_label(tokens: list) -> Optional[str]:
    """根据度数组合识别 C/Dm/Em/F/G/Am/G7 和弦名（向后兼容）"""
    utils = ChordUtils()
    return utils.detect_chord_label(tokens) 