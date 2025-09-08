"""
播放列表管理模块
提供播放列表的增删改查和播放控制功能
"""

import os
import json
from typing import List, Dict, Optional, Callable
from meowauto.core import Logger

class PlaylistManager:
    """播放列表管理器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.playlist_items = []
        self.current_index = -1
        self.random_play = False
        self.loop_play = False
        
        # 播放列表回调
        self.playlist_callbacks = {
            'on_item_added': None,
            'on_item_removed': None,
            'on_item_updated': None,
            'on_current_changed': None,
            'on_playlist_cleared': None,
            'on_playlist_loaded': None,
            'on_playlist_saved': None
        }
    
    def set_callbacks(self, **callbacks):
        """设置回调函数"""
        for key, callback in callbacks.items():
            if key in self.playlist_callbacks:
                self.playlist_callbacks[key] = callback
    
    def add_item(self, file_path: str) -> bool:
        """添加项目到播放列表"""
        if not os.path.exists(file_path):
            self.logger.log(f"文件不存在: {file_path}", "ERROR")
            return False
        
        try:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 确定文件类型和时长
            file_type = "未知"
            duration = "未知"
            
            if file_ext == '.lrcp':
                file_type = "LRCp乐谱"
                # 解析乐谱获取时长
                try:
                    from meowauto.music.score_parser import parse_score
                    with open(file_path, "r", encoding="utf-8") as f:
                        score_text = f.read()
                    events = parse_score(score_text)
                    if events:
                        duration = f"{events[-1].end:.1f}秒"
                except:
                    duration = "解析失败"
            elif file_ext in ['.mid', '.midi']:
                file_type = "MIDI文件"
                try:
                    import mido
                    midi = mido.MidiFile(file_path)
                    duration = f"{midi.length:.1f}秒"
                except:
                    duration = "解析失败"
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                file_type = "音频文件"
                duration = "需转换"
            
            # 创建播放列表项目
            item = {
                'path': file_path,
                'name': file_name,
                'type': file_type,
                'duration': duration,
                'status': '未播放'
            }
            
            self.playlist_items.append(item)
            
            # 调用添加回调
            if self.playlist_callbacks['on_item_added']:
                self.playlist_callbacks['on_item_added'](item, len(self.playlist_items) - 1)
            
            self.logger.log(f"已添加到播放列表: {file_name}", "INFO")
            return True
            
        except Exception as e:
            self.logger.log(f"添加文件到播放列表失败: {str(e)}", "ERROR")
            return False
    
    def remove_item(self, index: int) -> bool:
        """从播放列表中移除指定项目"""
        if not (0 <= index < len(self.playlist_items)):
            self.logger.log(f"无效的索引: {index}", "ERROR")
            return False
        
        try:
            removed_item = self.playlist_items.pop(index)
            
            # 调整当前索引
            if self.current_index == index:
                self.current_index = -1
            elif self.current_index > index:
                self.current_index -= 1
            
            # 调用移除回调
            if self.playlist_callbacks['on_item_removed']:
                self.playlist_callbacks['on_item_removed'](removed_item, index)
            
            self.logger.log(f"已从播放列表移除: {removed_item['name']}", "INFO")
            return True
            
        except Exception as e:
            self.logger.log(f"移除播放列表项目失败: {str(e)}", "ERROR")
            return False
    
    def clear_playlist(self) -> bool:
        """清空播放列表"""
        try:
            old_count = len(self.playlist_items)
            self.playlist_items.clear()
            self.current_index = -1
            
            # 调用清空回调
            if self.playlist_callbacks['on_playlist_cleared']:
                self.playlist_callbacks['on_playlist_cleared'](old_count)
            
            self.logger.log("播放列表已清空", "INFO")
            return True
            
        except Exception as e:
            self.logger.log(f"清空播放列表失败: {str(e)}", "ERROR")
            return False
    
    def get_item(self, index: int) -> Optional[Dict]:
        """获取指定索引的项目"""
        if 0 <= index < len(self.playlist_items):
            return self.playlist_items[index]
        return None
    
    def get_current_item(self) -> Optional[Dict]:
        """获取当前播放项目"""
        return self.get_item(self.current_index)
    
    def set_current_item(self, index: int) -> bool:
        """设置当前播放项目"""
        if not (0 <= index < len(self.playlist_items)):
            return False
        
        old_index = self.current_index
        self.current_index = index
        
        # 更新项目状态
        for i, item in enumerate(self.playlist_items):
            if i == index:
                item['status'] = '当前播放'
            elif item['status'] == '当前播放':
                item['status'] = '未播放'
        
        # 调用当前项目变化回调
        if self.playlist_callbacks['on_current_changed']:
            self.playlist_callbacks['on_current_changed'](index, old_index)
        
        return True
    
    def play_next(self) -> Optional[Dict]:
        """播放下一首"""
        if not self.playlist_items:
            return None
        
        if self.random_play:
            # 随机播放
            import random
            next_index = random.randint(0, len(self.playlist_items) - 1)
        else:
            # 顺序播放
            next_index = self.current_index + 1
            if next_index >= len(self.playlist_items):
                if self.loop_play:
                    next_index = 0
                else:
                    return None
        
        if self.set_current_item(next_index):
            return self.get_current_item()
        return None
    
    def play_previous(self) -> Optional[Dict]:
        """播放上一首"""
        if not self.playlist_items:
            return None
        
        if self.random_play:
            # 随机播放
            import random
            prev_index = random.randint(0, len(self.playlist_items) - 1)
        else:
            # 顺序播放
            prev_index = self.current_index - 1
            if prev_index < 0:
                if self.loop_play:
                    prev_index = len(self.playlist_items) - 1
                else:
                    return None
        
        if self.set_current_item(prev_index):
            return self.get_current_item()
        return None
    
    def toggle_random_play(self) -> bool:
        """切换随机播放"""
        self.random_play = not self.random_play
        status = "开启" if self.random_play else "关闭"
        self.logger.log(f"随机播放已{status}", "INFO")
        return self.random_play
    
    def toggle_loop_play(self) -> bool:
        """切换循环播放"""
        self.loop_play = not self.loop_play
        status = "开启" if self.loop_play else "关闭"
        self.logger.log(f"循环播放已{status}", "INFO")
        return self.loop_play
    
    def get_playlist_info(self) -> Dict[str, any]:
        """获取播放列表信息"""
        return {
            'total_items': len(self.playlist_items),
            'current_index': self.current_index,
            'random_play': self.random_play,
            'loop_play': self.loop_play,
            'has_current': self.current_index >= 0,
            'current_item': self.get_current_item()
        }

    # ========== 兼容 App 调用的导航 API ==========
    def set_order_mode(self, mode: str) -> None:
        """设置播放顺序模式。
        支持值：'单曲'、'顺序'、'循环'、'随机'（与 UI 下拉一致）
        - 单曲: 不自动跳下一首（next_index 返回 None）
        - 顺序: 到末尾返回 None
        - 循环: 到末尾回到 0
        - 随机: 随机返回任意索引
        """
        try:
            m = str(mode or '').strip()
            if m == '随机':
                self.random_play = True
                self.loop_play = False
            elif m == '循环':
                self.random_play = False
                self.loop_play = True
            elif m == '单曲':
                self.random_play = False
                self.loop_play = False
            else:
                # 顺序
                self.random_play = False
                self.loop_play = False
            try:
                self.logger.log(f"播放模式: {m or '顺序'} (random={self.random_play}, loop={self.loop_play})", "DEBUG")
            except Exception:
                pass
        except Exception:
            pass

    def select_index(self, idx: int) -> bool:
        """选择当前索引（供 App 同步选中项）。不触发播放，仅更新指针。"""
        if not isinstance(idx, int):
            return False
        if not (0 <= idx < len(self.playlist_items)):
            return False
        self.current_index = idx
        return True

    def next_index(self) -> Optional[int]:
        """根据当前模式返回下一首索引；若无下一首返回 None。"""
        n = len(self.playlist_items)
        if n == 0:
            return None
        cur = self.current_index
        # 单曲：不自动跳转
        if not self.random_play and not self.loop_play and cur >= 0:
            # 顺序或单曲，交由顺序逻辑判断
            pass
        # 随机模式
        if self.random_play:
            try:
                import random
                # 避免与当前相同（当 n>1 时）
                if n > 1 and 0 <= cur < n:
                    cand = list(range(n))
                    cand.remove(cur)
                    return random.choice(cand)
                return random.randint(0, n - 1)
            except Exception:
                return 0 if n > 0 else None
        # 顺序/循环模式
        nxt = (cur + 1) if (0 <= cur < n) else 0
        if nxt >= n:
            if self.loop_play:
                return 0
            return None
        return nxt