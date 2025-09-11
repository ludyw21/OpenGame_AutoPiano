"""
自动演奏模块
提供基于LRCp乐谱和MIDI文件的自动演奏功能
"""

import time
import threading
from typing import Any, Dict, List, Optional, Tuple, Callable
from meowauto.utils import midi_tools
from meowauto.core import Event, KeySender, Logger
from meowauto.playback.strategies import get_strategy
from meowauto.playback.keymaps import get_default_mapping
from meowauto.core.config import ConfigManager
from meowauto.music.chord_engine import ChordEngine
from meowauto.playback.keymaps_ext.drums import DRUMS_KEYMAP
from meowauto.midi.drums_parser import DrumsMidiParser

import os

class AutoPlayer:
    """自动演奏器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.is_playing = False
        self.is_paused = False
        self.play_thread = None
        self.current_tempo = 1.0
        self.current_events = []
        self.debug = False  # 调试模式：输出详细调度与事件日志
        # 可选时钟提供者（由服务层注入，仅用于日志与未来扩展）
        self._clock_provider = None
        # 可配置选项
        self.options = {
            'allow_retrigger': True,           # 允许同一键在按下状态下进行重触发（快速抬起再按下）
            'retrigger_min_gap_ms': 40,        # 重触发的最小时间间隔
            'epsilon_ms': 6,                   # 批处理窗口大小（毫秒）
            'send_ahead_ms': 0,                # 提前量（0 = 不提前，严格与事件时间对齐）
            'spin_threshold_ms': 1,            # 忙等切换阈值
            'post_action_sleep_ms': 0,         # 每次发按键后追加微睡眠
            'enable_chord_accomp': True,       # 启用和弦伴奏
            'chord_min_sustain_ms': 1500,      # 和弦最短/默认持续时长（ms）
            'chord_block_window_ms': 50,       # 将同一时间窗口内的按键对齐到同刻（块和弦）
            'chord_replace_melody': False,     # 用和弦键替代主音键（去根音）
            'enable_quantize': False,
            'quantize_grid_ms': 30,
            'enable_black_transpose': True,
            'black_transpose_strategy': 'nearest',
            'enable_key_fallback': True,
            'tap_gap_ms': 0,
            # 手动整曲移调（仅当 enable_pretranspose=True 时生效）
            'enable_pretranspose': False,
            'pretranspose_semitones': 0,
            # 多轨/多分部短时间内多键处理策略：'arpeggio' | 'merge' | 'original'
            'multi_key_cluster_mode': 'merge',
            'multi_key_cluster_window_ms': 240,
        }
        self.playback_callbacks = {
            'on_start': None,
            'on_stop': None,
            'on_pause': None,
            'on_resume': None,
            'on_progress': None,
            'on_complete': None,
            'on_error': None
        }
    
    def set_callbacks(self, **callbacks):
        """设置回调函数"""
        for key, callback in callbacks.items():
            if key in self.playback_callbacks:
                self.playback_callbacks[key] = callback
    
    def set_debug(self, enabled: bool):
        """启用/关闭调试模式"""
        self.debug = bool(enabled)
        self.logger.log(f"AutoPlayer 调试模式: {'开启' if self.debug else '关闭'}", "INFO")

    def set_clock_provider(self, provider):
        """注入时钟提供者（可为网络时钟/本地时钟）。当前播放循环仍使用本地高精度计时，
        此方法主要用于统一接口与日志展示。"""
        self._clock_provider = provider
        try:
            src = 'NTP' if getattr(provider, 'last_sync_ok', False) else 'Local'
            self.logger.log(f"[AutoPlayer] 时钟已注入: src={src}", "DEBUG")
        except Exception:
            pass
    
    def set_options(self, **kwargs):
        """设置可选参数: allow_retrigger, retrigger_min_gap_ms, epsilon_ms"""
        for k, v in kwargs.items():
            if k in self.options and v is not None:
                self.options[k] = v
        if self.debug:
            self.logger.log(f"[DEBUG] 选项: {self.options}", "DEBUG")
    
    def start_auto_play(self, events: List[Event], tempo: float = 1.0) -> bool:
        """开始自动演奏（LRCp模式）"""
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        
        if not events:
            self.logger.log("没有可演奏的事件", "ERROR")
            return False
        
        self.current_events = events
        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        
        # 启动演奏线程
        self.play_thread = threading.Thread(target=self._auto_play_thread)
        self.play_thread.daemon = True
        self.play_thread.start()
        
        # 调用开始回调
        if self.playback_callbacks['on_start']:
            self.playback_callbacks['on_start']()
        
        self.logger.log("开始自动演奏（LRCp模式）", "INFO")
        return True
    
    def start_auto_play_midi(self, midi_file: str, tempo: float = 1.0, 
                           key_mapping: Dict[str, str] = None,
                           strategy_name: Optional[str] = None) -> bool:
        """已禁用：为避免绕过统一 pretty_midi 解析管线，此入口不再使用。"""
        try:
            self.logger.log("已禁用的播放入口: start_auto_play_midi 被阻止。请使用基于解析后的事件入口。", "WARNING")
        except Exception:
            pass
        return False

    def start_auto_play_midi_drums(self, midi_file: str, tempo: float = 1.0,
                                   key_mapping: Optional[Dict[str, str]] = None) -> bool:
        """开始自动演奏（鼓专用MIDI）
        - 使用 DrumsMidiParser 读取 tempo map，输出鼓位事件
        - 直接按鼓键位映射（不走21键策略），忽略力度
        - 仅生成 note_on/note_off 键盘事件并进入 _auto_play_mapped_events_thread
        """
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        if not midi_file:
            self.logger.log("MIDI文件路径为空", "ERROR")
            return False

        # 键位映射：允许外部覆盖，默认使用 DRUMS_KEYMAP
        km = key_mapping or DRUMS_KEYMAP
        parser = DrumsMidiParser()
        notes = parser.parse(midi_file)
        if not notes:
            self.logger.log("鼓MIDI解析为空或失败", "ERROR")
            return False

        # 将鼓事件转换为按键事件
        events: List[Dict[str, Any]] = []
        for n in notes:
            try:
                st = float(n.get('start_time', 0.0))
                et = float(n.get('end_time', st))
                drum_id = str(n.get('drum_id', '')).upper()
                key = km.get(drum_id)
                if not key:
                    # 容错：若 drum_id 未映射，尝试关键别名
                    if drum_id.startswith('HIHAT'):
                        key = km.get('HIHAT_CLOSE')
                    elif 'TOM' in drum_id:
                        key = km.get('TOM1') or km.get('TOM2')
                    elif 'CRASH' in drum_id:
                        key = km.get('CRASH_MID') or km.get('CRASH_HIGH')
                    elif 'RIDE' in drum_id:
                        key = km.get('RIDE')
                    elif 'SNARE' in drum_id:
                        key = km.get('SNARE')
                    else:
                        key = km.get('KICK')
                if not key:
                    continue
                events.append({'start_time': st, 'type': 'note_on', 'key': key, 'velocity': 0, 'channel': int(n.get('channel', 9)), 'note': int(n.get('note', 36))})
                events.append({'start_time': max(et, st), 'type': 'note_off', 'key': key, 'velocity': 0, 'channel': int(n.get('channel', 9)), 'note': int(n.get('note', 36))})
            except Exception:
                continue

        if not events:
            self.logger.log("鼓MIDI映射为空", "ERROR")
            return False

        # 去重 + 多键窗口规范化 + 对同一时间戳，保证 note_off 先于 note_on
        try:
            events = self._dedup_same_time_same_key(events)
        except Exception:
            pass
        try:
            events = self._normalize_multi_key_clusters(events)
        except Exception:
            pass
        try:
            events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            pass

        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        self.play_thread = threading.Thread(target=self._auto_play_mapped_events_thread, args=(events,))
        self.play_thread.daemon = True
        self.play_thread.start()

        if self.playback_callbacks['on_start']:
            self.playback_callbacks['on_start']()
        self.logger.log("开始自动演奏（鼓MIDI专用）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 文件: {midi_file}, 鼓事件数: {len(events)}, 速度: {self.current_tempo}", "DEBUG")
        return True
    
    def start_auto_play_midi_events(self, notes: List[Dict[str, Any]], tempo: float = 1.0,
                                    key_mapping: Dict[str, str] = None,
                                    strategy_name: Optional[str] = None) -> bool:
        """开始自动演奏（使用外部解析后的MIDI音符事件）
        期望 notes 为带有 start_time/end_time/note/channel 的列表。
        注意：pretty_midi解析的start_time已经是考虑了原始MIDI tempo的准确秒数，
        这里的tempo参数仅用于用户倍速调整，不应对时间进行二次tempo处理。
        """
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        if not notes:
            self.logger.log("外部解析的MIDI事件为空", "ERROR")
            return False
        # 若未提供键位映射，使用默认
        if not key_mapping:
            key_mapping = self._get_default_key_mapping()

        # 展开为按键事件
        events: List[Dict[str, Any]] = []
        # 解析策略
        strategy = get_strategy(strategy_name or "strategy_21key")
        for n in notes:
            try:
                st = float(n.get('start_time', 0.0))
                et = float(n.get('end_time', st))
                note = int(n.get('note', 0))
                ch = int(n.get('channel', 0))
                key = strategy.map_note(note, key_mapping or self._get_default_key_mapping(), self.options)
                if not key:
                    continue
                events.append({'start_time': st, 'type': 'note_on', 'key': key, 'velocity': int(n.get('velocity', 64)), 'channel': ch, 'note': note})
                events.append({'start_time': max(et, st), 'type': 'note_off', 'key': key, 'velocity': 0, 'channel': ch, 'note': note})
            except Exception:
                continue

        # 可选：和弦伴奏（不更改原事件，仅附加映射后的伴奏键位事件）
        # 当启用“用和弦键替代主音键”时，不再追加伴奏事件，而是对主音事件进行替换
        if events and bool(self.options.get('chord_replace_melody', False)):
            try:
                events = self._apply_chord_key_replacement(events, key_mapping or self._get_default_key_mapping(), strategy_name)
                if self.debug:
                    self.logger.log(f"[DEBUG] 已替换为和弦键事件（数量 {len(events)}）", "DEBUG")
            except Exception:
                pass
        elif events and bool(self.options.get('enable_chord_accomp', False)):
            try:
                acc = self._generate_chord_accompaniment(events, key_mapping or self._get_default_key_mapping(), strategy_name)
                if acc:
                    events.extend(acc)
                    if self.debug:
                        self.logger.log(f"[DEBUG] 伴奏追加事件: {len(acc)}", "DEBUG")
            except Exception:
                pass

        # 去重：同刻同键仅保留一个
        try:
            events = self._dedup_same_time_same_key(events)
        except Exception:
            pass
        # 多键窗口规范化（琶音/合并/原样）
        try:
            events = self._normalize_multi_key_clusters(events)
        except Exception:
            pass
        # 预处理：同键延长音并集 + tap（release->press，gap 可为 0ms）
        try:
            events = self._apply_union_and_tap(events)
        except Exception:
            pass
        # 对同一时间戳，保证 note_off 先于 note_on
        try:
            events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            pass

        if not events:
            self.logger.log("展开后的回放事件为空", "ERROR")
            return False

        # DEBUG: 打印前若干条映射结果（note -> key），用于快速核对映射/移调是否生效
        if self.debug:
            try:
                previews = []
                seen = 0
                for ev in events:
                    if ev.get('type') != 'note_on':
                        continue
                    previews.append(f"note={ev.get('note')} -> key={ev.get('key')}")
                    seen += 1
                    if seen >= 10:
                        break
                if previews:
                    self.logger.log("[DEBUG] 映射预览: " + ", ".join(previews), "DEBUG")
            except Exception:
                pass

        # 去重 + 多键窗口规范化 + 对同一时间戳，保证 note_off 先于 note_on
        try:
            events = self._dedup_same_time_same_key(events)
        except Exception:
            pass
        try:
            events = self._normalize_multi_key_clusters(events)
        except Exception:
            pass
        try:
            events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            pass

        # 设置状态并启动线程
        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        # 标记使用pretty_midi事件，用于正确的tempo处理
        self._using_pretty_midi_events = True
        self.play_thread = threading.Thread(target=self._auto_play_mapped_events_thread, args=(events,))
        self.play_thread.start()
        
        # 启动回调（需可调用）
        cb = self.playback_callbacks.get('on_start')
        if callable(cb):
            cb()
        try:
            src = 'NTP' if getattr(self._clock_provider, 'last_sync_ok', False) else 'Local'
            self.logger.log(f"开始自动演奏（外部解析事件） clock={src}", "INFO")
        except Exception:
            self.logger.log("开始自动演奏（外部解析事件）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 外部事件数: {len(events)}, 速度: {self.current_tempo}, pretty_midi模式", "DEBUG")
        return True

    def start_auto_play_midi_events_mixed(self, notes: List[Dict[str, Any]], tempo: float = 1.0,
                                          role_keymaps: Dict[str, Dict[str, str]] | None = None,
                                          strategy_name: Optional[str] = None) -> bool:
        """开始自动演奏（按事件角色选择不同键位映射）。
        期望 notes: 包含 start_time/end_time/note/channel，可选字段 role（如 drums/bass/melody），也可已有 instrument_name/program 等。
        role_keymaps: 形如 { 'drums': DRUMS_KEYMAP, 'bass': BASS_KEYMAP, 'melody': DEFAULT }。
        若某事件缺少 role，则使用 'melody' 的映射，若仍缺失则使用默认映射。
        """
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        if not notes:
            self.logger.log("外部解析的MIDI事件为空", "ERROR")
            return False

        # 默认映射兜底
        default_map = None
        try:
            default_map = self._get_default_key_mapping()
        except Exception:
            default_map = None
        role_keymaps = role_keymaps or {}

        # 展开为按键事件
        events: List[Dict[str, Any]] = []
        strategy = get_strategy(strategy_name or "strategy_21key")
        for n in notes:
            try:
                st = float(n.get('start_time', 0.0))
                et = float(n.get('end_time', st))
                note = int(n.get('note', 0))
                ch = int(n.get('channel', 0))
                role = str(n.get('role', 'melody') or 'melody')
                km = role_keymaps.get(role) or role_keymaps.get('melody') or default_map
                if not km:
                    km = self._get_default_key_mapping()
                key = strategy.map_note(note, km, self.options)
                if not key:
                    continue
                events.append({'start_time': st, 'type': 'note_on', 'key': key, 'velocity': int(n.get('velocity', 64)), 'channel': ch, 'note': note})
                events.append({'start_time': max(et, st), 'type': 'note_off', 'key': key, 'velocity': 0, 'channel': ch, 'note': note})
            except Exception:
                continue

        # 可选：和弦伴奏（对合并后的事件）
        if events and bool(self.options.get('chord_replace_melody', False)):
            try:
                km = role_keymaps.get('melody') or default_map or self._get_default_key_mapping()
                events = self._apply_chord_key_replacement(events, km, strategy_name)
                if self.debug:
                    self.logger.log(f"[DEBUG] 已替换为和弦键事件（数量 {len(events)}）", "DEBUG")
            except Exception:
                pass
        elif events and bool(self.options.get('enable_chord_accomp', False)):
            try:
                km = role_keymaps.get('melody') or default_map or self._get_default_key_mapping()
                acc = self._generate_chord_accompaniment(events, km, strategy_name)
                if acc:
                    events.extend(acc)
                    if self.debug:
                        self.logger.log(f"[DEBUG] 伴奏追加事件: {len(acc)}", "DEBUG")
            except Exception:
                pass

        # 去重：同刻同键仅保留一个
        try:
            events = self._dedup_same_time_same_key(events)
        except Exception:
            pass
        # 多键窗口规范化（琶音/合并/原样）
        try:
            events = self._normalize_multi_key_clusters(events)
        except Exception:
            pass
        # 预处理：同键延长音并集 + tap
        try:
            events = self._apply_union_and_tap(events)
        except Exception:
            pass
        try:
            events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            pass
        # 启动播放（与 start_auto_play_midi_events 结尾保持一致逻辑）
        if not events:
            self.logger.log("展开后的回放事件为空", "ERROR")
            return False

        # 设置状态并启动线程
        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        # 标记使用 pretty_midi 事件，避免二次 tempo 处理
        self._using_pretty_midi_events = True
        self.play_thread = threading.Thread(target=self._auto_play_mapped_events_thread, args=(events,))
        self.play_thread.daemon = True
        self.play_thread.start()

        # 启动回调与日志
        cb = self.playback_callbacks.get('on_start')
        if callable(cb):
            cb()
        try:
            src = 'NTP' if getattr(self._clock_provider, 'last_sync_ok', False) else 'Local'
            self.logger.log(f"开始自动演奏（外部解析事件-角色混合映射） clock={src}", "INFO")
        except Exception:
            self.logger.log("开始自动演奏（外部解析事件-角色混合映射）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 外部事件数: {len(events)}, 速度: {self.current_tempo}, pretty_midi模式(mixed)", "DEBUG")
        return True

    def stop_auto_play(self):
        """停止自动演奏"""
        if not self.is_playing:
            return
        
        self.is_playing = False
        self.is_paused = False
        
        # 清除pretty_midi标记
        self._using_pretty_midi_events = False
        
        # 等待线程结束
        if self.play_thread and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)
        
        # 释放所有按键
        try:
            key_sender = KeySender()
            key_sender.release_all()
        except Exception as e:
            self.logger.log(f"释放按键失败: {str(e)}", "WARNING")
        
        # 调用停止回调
        if self.playback_callbacks['on_stop']:
            self.playback_callbacks['on_stop']()
        
        self.logger.log("自动演奏已停止", "INFO")
    
    def pause_auto_play(self):
        """暂停自动演奏"""
        if not self.is_playing:
            return
        
        self.is_paused = True
        
        # 调用暂停回调
        if self.playback_callbacks['on_pause']:
            self.playback_callbacks['on_pause']()
        
        self.logger.log("自动演奏已暂停", "INFO")
    
    def resume_auto_play(self):
        """恢复自动演奏"""
        if not self.is_playing or not self.is_paused:
            return
        
        self.is_paused = False
        
        # 调用恢复回调
        if self.playback_callbacks['on_resume']:
            self.playback_callbacks['on_resume']()
        
        self.logger.log("自动演奏已恢复", "INFO")
    
    def _auto_play_thread(self):
        """自动演奏线程 - LRCp模式"""
        try:
            if not self.current_events:
                self._handle_error("没有可演奏的事件")
                return
            
            # 开始自动演奏
            start_time = time.time()
            
            # 创建按键发送器
            key_sender = KeySender()
            
            # 构造动作表 (time, type, keys)
            actions: List[tuple] = []
            for event in self.current_events:
                actions.append((event.start, 'press', event.keys))
                actions.append((event.end, 'release', event.keys))
            
            # 按时间排序
            actions.sort(key=lambda x: x[0])
            
            # 开始执行（合并同一时间戳批处理）
            idx = 0
            jitter = 0.003
            
            while idx < len(actions) and self.is_playing:
                # 若处于暂停，等待恢复
                while self.is_paused and self.is_playing:
                    time.sleep(0.05)
                
                # 目标时间（按速度缩放）
                group_time = actions[idx][0] / max(0.01, self.current_tempo)
                
                # 等待到该批次时间点
                while True:
                    # 暂停时让等待循环让出CPU
                    if self.is_paused:
                        time.sleep(0.05)
                        continue
                    
                    now = time.time()
                    target = start_time + group_time
                    wait = target - now
                    
                    if wait > 0:
                        time.sleep(min(wait, 0.001))
                    else:
                        break
                
                # 收集同一时间片的所有动作
                j = idx
                press_keys: List[str] = []
                release_keys: List[str] = []
                
                while (j < len(actions) and 
                       abs(actions[j][0] / max(0.01, self.current_tempo) - group_time) <= jitter):
                    _, typ, keys = actions[j]
                    if typ == 'release':
                        release_keys.extend(keys)
                    else:
                        press_keys.extend(keys)
                    j += 1
                
                # 先释放再按下，减少重叠干扰
                if release_keys:
                    key_sender.release(release_keys)
                if press_keys:
                    key_sender.press(press_keys)
                
                # 更新进度
                if self.playback_callbacks['on_progress']:
                    progress = min(100, (idx / len(actions)) * 100)
                    self.playback_callbacks['on_progress'](progress)
                
                idx = j
            
            # 释放所有按键
            key_sender.release_all()
            
            # 演奏完成
            if self.is_playing:  # 只有在正常完成时才调用完成回调
                if self.playback_callbacks['on_complete']:
                    self.playback_callbacks['on_complete']()
                self.logger.log("自动演奏完成", "SUCCESS")
            
        except Exception as e:
            error_msg = f"自动演奏失败: {str(e)}"
            self._handle_error(error_msg)
        finally:
            self.is_playing = False

    def _auto_play_mapped_events_thread(self, events: List[Dict[str, Any]]):
        """自动演奏线程 - 直接使用已映射的按键事件
        事件结构需包含: 'start_time', 'type' in ('note_on','note_off'), 'key', 可选 'note','channel'
        """
        try:
            if not events:
                self._handle_error("没有可演奏的事件")
                return

            # 排序并计算总时长（同一时间戳优先释放再按下，避免抑制快速重按）
            try:
                events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
            except Exception:
                events.sort(key=lambda x: x['start_time'])
            total_time = events[-1]['start_time'] if events else 0.0

            if self.debug:
                self.logger.log(f"[DEBUG] 开始播放 {len(events)} 个事件，速度倍率: {self.current_tempo}", "DEBUG")
                if events:
                    first_time = events[0]['start_time']
                    last_time = events[-1]['start_time'] if len(events) > 1 else first_time
                    self.logger.log(f"[DEBUG] 事件时间范围: {first_time:.3f}s - {last_time:.3f}s", "DEBUG")

            from time import perf_counter
            start_perf = perf_counter()
            key_sender = KeySender()

            send_ahead = float(self.options.get('send_ahead_ms', 2)) / 1000.0
            spin_threshold = max(0.0, float(self.options.get('spin_threshold_ms', 1)) / 1000.0)
            post_action_sleep = max(0.0, float(self.options.get('post_action_sleep_ms', 0)) / 1000.0)

            # 引用计数，避免重叠音过早释放
            active_counts: Dict[str, int] = {}

            idx = 0
            while idx < len(events) and self.is_playing:
                # 暂停处理
                while self.is_paused and self.is_playing:
                    time.sleep(0.01)

                ev = events[idx]
                # 对于pretty_midi解析的事件，start_time已经是考虑了原始MIDI tempo的准确秒数
                # 只需要应用用户的倍速设置：tempo > 1.0播放更快，tempo < 1.0播放更慢
                if hasattr(self, '_using_pretty_midi_events') and self._using_pretty_midi_events:
                    # pretty_midi事件：时间已经是准确的秒数，严格按时间播放
                    # 当tempo=1.0时，直接使用原始时间；当tempo!=1.0时，按倍速调整
                    group_time = ev['start_time'] / max(0.01, self.current_tempo)
                    if self.debug and idx < 3:
                        self.logger.log(f"[DEBUG] pretty_midi事件 {idx}: 原始时间={ev['start_time']:.4f}s, 调整后={group_time:.4f}s, tempo={self.current_tempo}", "DEBUG")
                else:
                    # 传统事件：使用原有的tempo处理逻辑
                    group_time = ev['start_time'] / max(0.01, self.current_tempo)

                # 分级等待到目标时间（考虑提前量）
                target = max(0.0, group_time - send_ahead)
                while self.is_playing and not self.is_paused:
                    now = perf_counter() - start_perf
                    remain = target - now
                    
                    if remain <= 0:
                        break
                    if remain > 0.02:
                        time.sleep(remain - 0.01)
                    elif remain > spin_threshold:
                        time.sleep(0.0005)
                    else:
                        # 忙等阶段
                        while (perf_counter() - start_perf) < target and self.is_playing and not self.is_paused:
                            pass
                        break

                # 执行单个事件（严格按顺序）
                if ev['type'] == 'note_off':
                    k = ev['key']
                    c = active_counts.get(k, 0)
                    if c > 0:
                        c -= 1
                        active_counts[k] = c
                        if c == 0:
                            key_sender.release([k])
                            if post_action_sleep > 0:
                                time.sleep(post_action_sleep)
                else:  # note_on
                    k = ev['key']
                    c = active_counts.get(k, 0)
                    if c == 0:
                        key_sender.press([k])
                        if post_action_sleep > 0:
                            time.sleep(post_action_sleep)
                    active_counts[k] = c + 1

                # 进度：按时间推进
                if self.playback_callbacks['on_progress'] and total_time > 0:
                    now = perf_counter() - start_perf
                    progress = max(0.0, min(100.0, (now / (total_time / max(0.01, self.current_tempo))) * 100))
                    try:
                        self.playback_callbacks['on_progress'](progress)
                    except Exception:
                        pass

                idx += 1

            remaining_pressed = [k for k, c in active_counts.items() if c > 0]
            if remaining_pressed:
                key_sender.release(remaining_pressed)

            if self.is_playing:
                if self.playback_callbacks['on_complete']:
                    self.playback_callbacks['on_complete']()
                self.logger.log("外部事件回放完成", "SUCCESS")

        except Exception as e:
            error_msg = f"MIDI自动演奏失败: {str(e)}"
            self._handle_error(error_msg)
        finally:
            self.is_playing = False

    def _parse_midi_file(self, midi_file: str, key_mapping: Dict[str, str] = None, strategy_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """解析MIDI文件为演奏事件（策略映射，禁用和弦事件）"""
        try:
            try:
                import mido
            except ImportError:
                self.logger.log("MIDI解析失败: mido库未安装，请安装mido库", "ERROR")
                return []
            
            if not os.path.exists(midi_file):
                self.logger.log(f"MIDI文件不存在: {midi_file}", "ERROR")
                return []
            
            midi = mido.MidiFile(midi_file)
            events: List[Dict[str, Any]] = []
            
            # 直接使用mido的原生时间转换，避免手动tempo计算错误
            if self.debug:
                self.logger.log(f"[DEBUG] MIDI文件信息: ticks_per_beat={midi.ticks_per_beat}, length={midi.length:.3f}s", "DEBUG")
            
            # 如果没有提供键位映射，使用默认映射
            if not key_mapping:
                key_mapping = self._get_default_key_mapping()
            
            # 解析策略
            strategy = get_strategy(strategy_name or "strategy_21key")

            # 使用mido原生时间转换收集所有音符事件
            all_messages = []
            
            # 采用之前版本2的有效MIDI解析方案
            default_tempo = 500000  # 默认120 BPM (微秒/拍)
            ticks_per_beat = midi.ticks_per_beat
            current_tempo = default_tempo
            
            # 收集所有轨道消息及其轨内时间
            all_messages = []
            for track_num, track in enumerate(midi.tracks):
                track_time = 0
                for msg in track:
                    # 先累积 delta，再记录本条消息所在的绝对 tick，避免将事件记在“上一刻”
                    track_time += msg.time
                    all_messages.append({
                        'msg': msg,
                        'track_time': track_time,
                        'track_num': track_num
                    })
            
            # 按时间排序所有消息
            all_messages.sort(key=lambda x: x['track_time'])

            # 构建全局 tempo 变化表 (tick -> tempo)
            tempo_changes: List[Dict[str, Any]] = []
            # 保证从 tick 0 开始有一个 tempo
            tempo_changes.append({'tick': 0, 'tempo': default_tempo, 'acc_seconds': 0.0})
            last_tempo = default_tempo
            for mi in all_messages:
                msg = mi['msg']
                if msg.type == 'set_tempo':
                    t = mi['track_time']
                    # 仅当与上一次不同才记录，避免重复
                    if not tempo_changes or t != tempo_changes[-1]['tick'] or msg.tempo != last_tempo:
                        tempo_changes.append({'tick': t, 'tempo': msg.tempo, 'acc_seconds': 0.0})
                        last_tempo = msg.tempo

            # 根据变化的 tick 计算每个变化点的累积秒数 acc_seconds
            # acc_seconds 为到该变化点开始位置为止的累计秒数
            for i in range(1, len(tempo_changes)):
                prev = tempo_changes[i-1]
                cur = tempo_changes[i]
                delta_ticks = max(0, cur['tick'] - prev['tick'])
                seconds_per_tick = (prev['tempo'] / 1_000_000.0) / max(1, ticks_per_beat)
                cur['acc_seconds'] = prev['acc_seconds'] + delta_ticks * seconds_per_tick

            def tick_to_seconds(tick_pos: int) -> float:
                """将绝对 tick 位置转换为秒，按 tempo 分段积分"""
                # 找到最后一个变化点，其 tick <= tick_pos
                idx = 0
                for i in range(len(tempo_changes)):
                    if tempo_changes[i]['tick'] <= tick_pos:
                        idx = i
                    else:
                        break
                base = tempo_changes[idx]
                seconds_per_tick = (base['tempo'] / 1_000_000.0) / max(1, ticks_per_beat)
                return base['acc_seconds'] + (tick_pos - base['tick']) * seconds_per_tick
            
            # 处理所有消息
            active_notes = {}
            # 短音过滤已在MIDI解析阶段完成，此处不再重复过滤
            dropped_pairs = 0
            dropped_unfinished = 0
            total_pairs = 0
            total_unfinished = 0
            
            for msg_info in all_messages:
                msg = msg_info['msg']
                track_time = msg_info['track_time']
                
                # 处理速度变化（仅记录当前，实际换算使用 tempo 表）
                if msg.type == 'set_tempo':
                    current_tempo = msg.tempo
                    
                if msg.type == 'note_on' and msg.velocity > 0:
                    # 音符开始
                    note_key = (msg.channel, msg.note)
                    active_notes[note_key] = {
                        'start_time': track_time,
                        'velocity': msg.velocity,
                        'channel': getattr(msg, 'channel', 0)
                    }

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # 音符结束
                    note_key = (msg.channel, msg.note)
                    if note_key in active_notes:
                        start_info = active_notes.pop(note_key)
                        
                        # 转换为绝对时间（秒），使用 tempo 表精确换算
                        start_time = tick_to_seconds(start_info['start_time'])
                        end_time = tick_to_seconds(track_time)
                        duration = max(0.0, end_time - start_time)
                        total_pairs += 1
                        
                        # 预处理：手动整曲移调
                        note_for_map = msg.note
                        if bool(self.options.get('enable_pretranspose', False)):
                            try:
                                shift = int(self.options.get('pretranspose_semitones', 0))
                                note_for_map = max(0, min(127, int(note_for_map) + shift))
                            except Exception:
                                pass

                        # 应用键位映射
                        mapped_keys = strategy.map_note_to_keys({
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': duration,
                            'note': note_for_map,
                            'velocity': start_info['velocity'],
                            'channel': start_info['channel']
                        }, key_mapping)
                        
                        if mapped_keys:
                            for key in mapped_keys:
                                # 添加按下事件
                                events.append({
                                    'start_time': start_time,
                                    'type': 'note_on',
                                    'key': key,
                                    'velocity': start_info['velocity'],
                                    'channel': start_info['channel'],
                                    'note': note_for_map
                                })
                                
                                # 添加释放事件
                                events.append({
                                    'start_time': end_time,
                                    'type': 'note_off',
                                    'key': key,
                                    'velocity': 0,
                                    'channel': getattr(msg, 'channel', 0),
                                    'note': note_for_map
                                })
            
            # 处理未结束的音符（设置合理的持续时间）
            for note_key, info in active_notes.items():
                start_time = tick_to_seconds(info['start_time'])
                # 根据音符长度设置合理的持续时间
                duration = 0.5  # 默认0.5秒
                note = note_key[1]
                if note < 60:  # 低音区，持续时间稍长
                    duration = 0.8
                elif note > 72:  # 高音区，持续时间稍短
                    duration = 0.3
                
                end_time = start_time + duration
                total_unfinished += 1
                
                # 预处理：手动整曲移调
                note_for_map = note
                if bool(self.options.get('enable_pretranspose', False)):
                    try:
                        shift = int(self.options.get('pretranspose_semitones', 0))
                        note_for_map = max(0, min(127, int(note_for_map) + shift))
                    except Exception:
                        pass

                mapped_keys = strategy.map_note_to_keys({
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'note': note_for_map,
                    'velocity': info['velocity'],
                    'channel': info['channel']
                }, key_mapping)
                
                if mapped_keys:
                    for key in mapped_keys:
                        # 添加按下事件
                        events.append({
                            'start_time': start_time,
                            'type': 'note_on',
                            'key': key,
                            'velocity': info['velocity'],
                            'channel': info['channel'],
                            'note': note_for_map
                        })
                        
                        # 添加释放事件
                        events.append({
                            'start_time': end_time,
                            'type': 'note_off',
                            'key': key,
                            'velocity': 0,
                            'channel': info['channel'],
                            'note': note_for_map
                        })
            
            # 按时间排序
            events.sort(key=lambda x: x['start_time'])
            
            if self.debug:
                self.logger.log(f"[DEBUG] 生成 {len(events)} 个播放事件", "DEBUG")
                if events:
                    first_event = events[0]
                    last_event = events[-1]
                    self.logger.log(f"[DEBUG] 播放事件时间范围: {first_event['start_time']:.3f}s - {last_event['start_time']:.3f}s", "DEBUG")
            
            # 可选：和弦伴奏或替代
            if events and bool(self.options.get('chord_replace_melody', False)):
                try:
                    events = self._apply_chord_key_replacement(events, key_mapping, strategy_name)
                    if self.debug:
                        self.logger.log(f"[DEBUG] 已替换为和弦键事件（数量 {len(events)}）", "DEBUG")
                except Exception:
                    pass
            elif events and bool(self.options.get('enable_chord_accomp', False)):
                try:
                    acc = self._generate_chord_accompaniment(events, key_mapping, strategy_name)
                    if acc:
                        events.extend(acc)
                        if self.debug:
                            self.logger.log(f"[DEBUG] 伴奏追加事件: {len(acc)}", "DEBUG")
                except Exception:
                    pass

            # 预处理：黑键移调与量化（采用版本2的方案）
            # 短音过滤已在MIDI解析阶段完成
            if self.debug:
                self.logger.log(f"短音过滤已在MIDI解析阶段完成，此处跳过", "INFO")
            if bool(self.options.get('enable_black_transpose', True)):
                events = midi_tools.transpose_black_keys(events, strategy=str(self.options.get('black_transpose_strategy', 'down')))

            if bool(self.options.get('enable_quantize', True)):
                grid_ms = int(self.options.get('quantize_grid_ms', 30))
                events = midi_tools.quantize_events(events, grid_ms=max(1, grid_ms))

            # 按时间排序；同一时间戳优先释放再按下，避免抑制快速重按
            try:
                events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
            except Exception:
                events.sort(key=lambda x: x['start_time'])
            if self.debug and events:
                try:
                    tempos = []
                    if not is_smpte:
                        try:
                            tempos = [tc.get('tempo') for tc in tempo_changes]  # type: ignore
                        except Exception:
                            tempos = []
                    first_ev = events[0]
                    last_ev = events[-1]
                    span = max(0.0, float(last_ev.get('start_time', 0.0)) - float(first_ev.get('start_time', 0.0)))
                    self.logger.log(
                        f"[DEBUG] ticks_per_beat={ticks_per_beat}, timebase={'SMPTE' if is_smpte else 'PPQ'}, tempo_changes={0 if is_smpte else len(tempo_changes)}, tempos(sample)={tempos[:4] if tempos else '[]'}, smpte_spt={smpte_seconds_per_tick if is_smpte else 'n/a'}",
                        "DEBUG",
                    )
                    self.logger.log(
                        f"[DEBUG] 事件总数={len(events)}, 首个时间={first_ev.get('start_time', 0.0):.6f}s, 末个时间={last_ev.get('start_time', 0.0):.6f}s, 跨度={span:.6f}s",
                        "DEBUG",
                    )
                    self.logger.log(f"[DEBUG] 事件示例: {events[:5]}", "DEBUG")
                except Exception:
                    pass

            # 自校准：若与 mido 计算的总时长相差过大，则按比例缩放到一致
            try:
                if events:
                    # 使用事件中最大时间作为跨度，更稳健
                    try:
                        my_total = max(float(ev.get('start_time', 0.0)) for ev in events)
                    except Exception:
                        my_total = float(events[-1].get('start_time', 0.0))
                    mf_len = 0.0
                    try:
                        mf = mido.MidiFile(midi_file)
                        mf_len = float(getattr(mf, 'length', 0.0) or 0.0)
                    except Exception:
                        mf_len = 0.0
                    # 若 mido.length 不可用，退化为用 tempo_changes/PPQ 或 SMPTE 常量积分求长度
                    if mf_len <= 0.0:
                        try:
                            if not is_smpte:
                                # PPQ：用 tempo_changes 积分到最大 tick
                                max_tick = 0
                                try:
                                    # all_messages 已排序
                                    max_tick = max(int(mi['track_time']) for mi in all_messages) if all_messages else 0
                                except Exception:
                                    max_tick = 0
                                if tempo_changes:
                                    acc = 0.0
                                    for i in range(1, len(tempo_changes)):
                                        prev = tempo_changes[i-1]
                                        cur = tempo_changes[i]
                                        dt = max(0, int(cur['tick']) - int(prev['tick']))
                                        spt = (prev['tempo'] / 1_000_000.0) / max(1, ticks_per_beat)
                                        acc += dt * spt
                                    if tempo_changes:
                                        last = tempo_changes[-1]
                                        tail = max(0, max_tick - int(last['tick']))
                                        spt = (last['tempo'] / 1_000_000.0) / max(1, ticks_per_beat)
                                        acc += tail * spt
                                    mf_len = acc
                            else:
                                # SMPTE：常量秒/每tick 乘以最大 tick
                                max_tick = 0
                                try:
                                    max_tick = max(int(mi['track_time']) for mi in all_messages) if all_messages else 0
                                except Exception:
                                    max_tick = 0
                                mf_len = float(max_tick) * float(smpte_seconds_per_tick)
                        except Exception:
                            pass
                    if my_total > 0.0 and mf_len > 0.0:
                        ratio = mf_len / my_total if my_total > 1e-9 else 1.0
                        # 偏差超过5%即缩放，尽量与 mido 时长对齐（覆盖个别曲目二倍速/半速）
                        if abs(1.0 - ratio) >= 0.05:
                            for ev in events:
                                try:
                                    ev['start_time'] = float(ev.get('start_time', 0.0)) * ratio
                                except Exception:
                                    pass
                            if self.debug:
                                try:
                                    self.logger.log(f"[DEBUG] 时间轴校准: my_total={my_total:.6f}s -> {my_total*ratio:.6f}s, mido.length={mf_len:.6f}s, ratio={ratio:.6f}", "DEBUG")
                                except Exception:
                                    pass
            except Exception:
                pass

            # 预处理：同键延长音并集 + tap（release->press, gap 可为 0ms）
            try:
                events = self._apply_union_and_tap(events)
            except Exception:
                pass
            # 最终排序（确保同刻先 off 再 on）
            try:
                events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
            except Exception:
                pass
            return events
        except Exception as e:
            # 兜底：解析过程中出现异常
            try:
                self._handle_error(f"MIDI解析失败: {str(e)}")
            except Exception:
                pass
            return []
    
    def _get_default_key_mapping(self) -> Dict[str, str]:
        """获取默认键位映射。

        优先读取配置项 `playback.keymap_profile`：
        - drums -> DRUMS_KEYMAP
        - bass  -> BASS_KEYMAP
        - guitar-> GUITAR_KEYMAP
        - 其它/缺省 -> 21 键钢琴映射
        """
        try:
            profile = "piano"
            try:
                cfg = ConfigManager()
                profile = str(cfg.get('playback.keymap_profile', 'piano')).lower()
            except Exception:
                profile = "piano"
            if profile == 'drums':
                return DRUMS_KEYMAP
            if profile == 'bass':
                return BASS_KEYMAP
            if profile == 'guitar':
                return GUITAR_KEYMAP
            return get_default_mapping()
        except Exception:
            return get_default_mapping()
    
    def _apply_union_and_tap(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对同一 key 的按键区间做并集合并，并在每个子音起点插入 tap（release→press）。
        - tap_gap_ms: 0 代表零间隔（同刻 off→on，依赖排序保证顺序）。
        - retrigger_min_gap_ms: 限制最小重触发间隔，避免极限抖动。
        - 仅当 allow_retrigger=True 时插入 tap。
        传入/返回: 事件列表，元素包含 'start_time','type' in ('note_on','note_off'),'key'。
        """
        if not events:
            return events
        allow_rt = bool(self.options.get('allow_retrigger', True))
        tap_gap_ms = float(self.options.get('tap_gap_ms', 0))
        retrig_gap_ms = float(self.options.get('retrigger_min_gap_ms', 40))
        eps_ms = float(self.options.get('epsilon_ms', 6))
        tap_gap = max(0.0, tap_gap_ms) / 1000.0
        retrig_gap = max(0.0, retrig_gap_ms) / 1000.0
        eps = max(0.0, eps_ms) / 1000.0

        # 1) 先按 key 重建原始区间 [on, off]
        # 确保按时间和类型顺序
        try:
            evs = sorted(events, key=lambda x: (float(x.get('start_time', 0.0)), 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            evs = list(events)

        per_key_intervals: Dict[str, List[Tuple[float, float]]] = {}
        stacks: Dict[str, List[float]] = {}
        for ev in evs:
            k = ev.get('key')
            if not k:
                continue
            t = float(ev.get('start_time', 0.0))
            typ = ev.get('type')
            if typ == 'note_on':
                stacks.setdefault(k, []).append(t)
            elif typ == 'note_off':
                st_list = stacks.get(k)
                if st_list:
                    st = st_list.pop(0)
                    if t < st:
                        t = st
                    per_key_intervals.setdefault(k, []).append((st, t))

        # 2) 对每个 key 的区间做并集
        def merge_union(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
            if not intervals:
                return []
            arr = sorted([(min(a, b), max(a, b)) for a, b in intervals], key=lambda x: x[0])
            merged: List[Tuple[float, float]] = []
            cs, ce = arr[0]
            for s, e in arr[1:]:
                if s <= ce + eps:
                    ce = max(ce, e)
                else:
                    merged.append((cs, ce))
                    cs, ce = s, e
            merged.append((cs, ce))
            return merged

        per_key_union: Dict[str, List[Tuple[float, float]]] = {k: merge_union(iv) for k, iv in per_key_intervals.items()}

        # 3) 生成“并集段”的主 on/off 事件
        out: List[Dict[str, Any]] = []
        for k, unions in per_key_union.items():
            for s, e in unions:
                out.append({'start_time': s, 'type': 'note_on', 'key': k, 'velocity': 64})
                out.append({'start_time': e, 'type': 'note_off', 'key': k, 'velocity': 0})

        # 4) 段内插入 tap：对每个原始区间的起点，若不等于并集段起点，则插入 off→on
        if allow_rt:
            for k, intervals in per_key_intervals.items():
                unions = per_key_union.get(k, [])
                if not unions:
                    continue
                # 为快速判断“是否等于段起点”，做列表
                union_starts = [s for s, _ in unions]
                union_ends = [e for _, e in unions]
                last_tap_time = -1e9
                for st, en in sorted(intervals, key=lambda x: x[0]):
                    # 找到 st 所在并集段（st ∈ [us, ue]）
                    seg_idx = -1
                    for i, (us, ue) in enumerate(unions):
                        if st >= us - eps and st <= ue + eps:
                            seg_idx = i
                            break
                    if seg_idx < 0:
                        continue
                    us, ue = unions[seg_idx]
                    # 若与段起点“相等”，不需要 tap（主 on 已存在）
                    if any(abs(st - us0) <= eps for us0 in union_starts):
                        continue
                    # 最小重触发间隔
                    if (st - last_tap_time) < retrig_gap:
                        continue
                    # 若 tap_on 超过段末，跳过（避免制造孤立按下）
                    tap_on_time = st + tap_gap
                    if tap_on_time > ue - 1e-6:
                        continue
                    # 插入即时 tap：off at st, on at st+gap（gap=0 时同刻，通过排序保证 off→on）
                    out.append({'start_time': st, 'type': 'note_off', 'key': k, 'velocity': 0})
                    out.append({'start_time': tap_on_time, 'type': 'note_on', 'key': k, 'velocity': 64})
                    last_tap_time = st

        # 对于原本不包含在 per_key_intervals 的“非按键类事件”，保持（本模块中均是按键事件，可忽略）
        # 最终返回组合后的事件
        return out if out else events

    def _dedup_same_time_same_key(self, events: List[Dict[str, Any]], eps: float = 1e-6) -> List[Dict[str, Any]]:
        """去重：若同一时刻映射到同一键位上出现重复事件，仅保留一个。
        - 按 (time_bucket, key, type) 维度去重，保留首次出现，避免将 off 与 on 互相吞并。
        - time_bucket 采用 eps 容差进行量化，默认 1e-6 秒。
        """
        if not events:
            return events
        seen = set()
        out: List[Dict[str, Any]] = []
        def bucket_time(t: float) -> int:
            try:
                return int(round(float(t) / max(eps, 1e-9)))
            except Exception:
                return int(round(0.0 / max(eps, 1e-9)))
        for ev in events:
            try:
                k = ev.get('key')
                t = ev.get('start_time')
                typ = ev.get('type')
                if k is None or t is None or typ not in ('note_on','note_off'):
                    out.append(ev)
                    continue
                b = bucket_time(float(t))
                sig = (b, str(k), str(typ))
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(ev)
            except Exception:
                out.append(ev)
        return out

    def _normalize_multi_key_clusters(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """多键窗口规范化：控制短时间窗口内的多键触发风格。
        - mode = 'merge': 将窗口内所有 note_on 对齐到同一时间（块和弦），时间取窗口内最小值或网格对齐。
        - mode = 'arpeggio': 在窗口内按键序（key 字典序）均匀铺开（琶音效果）。
        - mode = 'original': 不处理。
        仅处理 note_on 事件；note_off 保持原样（后续 union/tap 会处理时值连贯性）。
        """
        if not events:
            return events
        mode = str(self.options.get('multi_key_cluster_mode', 'merge')).lower()
        if mode not in ('merge', 'arpeggio'):
            return events  # original
        try:
            win_ms = float(self.options.get('multi_key_cluster_window_ms', 50))
        except Exception:
            win_ms = 50.0
        win = max(0.0, win_ms) / 1000.0
        if win <= 0:
            return events

        # 仅取 note_on 参与聚类
        ons = [ev for ev in events if ev.get('type') == 'note_on' and ev.get('start_time') is not None]
        if not ons:
            return events
        # 排序后聚类
        ons_sorted = sorted(ons, key=lambda x: float(x.get('start_time', 0.0)))
        clusters: List[List[Dict[str, Any]]] = []
        cur: List[Dict[str, Any]] = []
        for ev in ons_sorted:
            t = float(ev.get('start_time', 0.0))
            if not cur:
                cur = [ev]
            else:
                t0 = float(cur[0].get('start_time', 0.0))
                if (t - t0) <= win:
                    cur.append(ev)
                else:
                    clusters.append(cur)
                    cur = [ev]
        if cur:
            clusters.append(cur)

        # 应用处理
        if mode == 'merge':
            for cluster in clusters:
                t0 = min(float(e.get('start_time', 0.0)) for e in cluster)
                # 对齐到 t0，使同窗内形成“块和弦”
                for e in cluster:
                    e['start_time'] = t0
        elif mode == 'arpeggio':
            # 在窗口内均匀分布 note_on，按 key 排序稳定输出
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                t0 = min(float(e.get('start_time', 0.0)) for e in cluster)
                span = max(win, 1e-6)
                cluster_sorted = sorted(cluster, key=lambda x: str(x.get('key')))
                n = len(cluster_sorted)
                for i, e in enumerate(cluster_sorted):
                    # 均匀铺开 [t0, t0+span) 区间
                    e['start_time'] = t0 + (span * i / max(1, n))
        return events
 
    
    def _generate_chord_accompaniment(self, events: List[Dict[str, Any]], key_mapping: Dict[str, str], strategy_name: Optional[str]) -> List[Dict[str, Any]]:
        """根据已映射旋律事件，调用新版 ChordEngine 生成与主音节奏对齐的和弦伴奏。"""
        try:
            if not events:
                return []
            # 惰性初始化引擎
            if not hasattr(self, "_chord_engine") or self._chord_engine is None:
                self._chord_engine = ChordEngine()
            accomp = self._chord_engine.generate_accompaniment(events, self.options)
            if self.debug:
                try:
                    self.logger.log(f"[DEBUG] ChordEngine 追加事件: {len(accomp)}", "DEBUG")
                except Exception:
                    pass
            return accomp
        except Exception:
            return []

    def _apply_chord_key_replacement(self, events: List[Dict[str, Any]], key_mapping: Dict[str, str], strategy_name: Optional[str]) -> List[Dict[str, Any]]:
        """仅对“触发和弦组合”的主音执行替代：
        - 条件：事件发生时刻 t 存在和弦组合（>=2 个和弦键处于按下区间）。
        - 动作：将该主音的按下/抬起对，替换为多个和弦键的按下/抬起（1->N）。
        - 其余主音事件保持不变；不追加伴奏事件。
        """
        try:
            if not events:
                return []
            # 构建和弦键时间线
            accomp = self._generate_chord_accompaniment(events, key_mapping, strategy_name)
            if not accomp:
                return events
            # parse accompaniment into intervals per chord key
            stacks: Dict[str, List[float]] = {}
            intervals: List[Tuple[float, float, str]] = []
            for ev in accomp or []:
                if ev.get('type') == 'note_on':
                    k = ev.get('key')
                    if k is None:
                        continue
                    stacks.setdefault(k, []).append(float(ev.get('start_time', 0.0)))
                elif ev.get('type') == 'note_off':
                    k = ev.get('key')
                    if k is None:
                        continue
                    st_list = stacks.get(k)
                    if st_list:
                        st = st_list.pop(0)
                        et = float(ev.get('start_time', st))
                        if et > st:
                            intervals.append((st, et, k))
            # 合并并排序区间（可选）
            intervals.sort(key=lambda x: (x[0], x[1]))

            # 快速查找：按时间定位覆盖 t 的所有区间（和弦）
            starts = [iv[0] for iv in intervals]

            def find_keys_at(t: float) -> List[str]:
                import bisect
                i = bisect.bisect_right(starts, t) - 1
                if i < 0:
                    return []
                keys: List[str] = []
                # 从 i 向后回溯，收集覆盖 t 的区间
                for j in range(i, -1, -1):
                    st, et, k = intervals[j]
                    if t >= st and t <= et:
                        keys.append(k)
                    if t > et:
                        break
                return keys

            # 检查是否启用和弦替代主音功能
            chord_replace_melody = self.options.get('chord_replace_melody', False)
            
            if not chord_replace_melody:
                # 不替代主音，直接返回原事件加上和弦伴奏
                out = list(events)
                for ev in accomp:
                    out.append(ev)
                out.sort(key=lambda x: (float(x.get('start_time', 0.0)), 0 if x.get('type')=='note_off' else 1))
                return out
            
            # 启用替代功能：遍历事件，按"音对"替代：仅当 t 处存在 >=1 个和弦键
            out: List[Dict[str, Any]] = []
            # 记录每个 (note, channel) 的起始时间及是否替代与和弦键列表
            note_on_stack: Dict[Tuple[int, int], List[float]] = {}
            replaced_meta: Dict[Tuple[int, int, float], List[str]] = {}

            # 第一遍：标记哪些 note_on 需要替代，并记录 chord_keys
            for ev in events:
                if ev.get('type') == 'note_on':
                    ch = int(ev.get('channel', 0))
                    note = int(ev.get('note', -1))
                    st = float(ev.get('start_time', 0.0))
                    note_on_stack.setdefault((note, ch), []).append(st)
                    chord_keys = find_keys_at(st)
                    if len(chord_keys) >= 1:  # 只要有和弦键就替代
                        replaced_meta[(note, ch, st)] = chord_keys
            # 清空临时栈，用于第二遍成对处理
            note_on_stack.clear()

            # 第二遍：构造输出事件
            for ev in events:
                etype = ev.get('type')
                ch = int(ev.get('channel', 0))
                note = int(ev.get('note', -1))
                t = float(ev.get('start_time', 0.0))
                if etype == 'note_on':
                    note_on_stack.setdefault((note, ch), []).append(t)
                    if (note, ch, t) in replaced_meta:
                        # 跳过原始 note_on（将由成对的 note_off 一起生成替代事件）
                        continue
                    else:
                        out.append(ev)
                elif etype == 'note_off':
                    st_list = note_on_stack.get((note, ch))
                    if st_list:
                        st = st_list.pop()
                    else:
                        st = t  # 容错
                    if (note, ch, st) in replaced_meta:
                        chord_keys = replaced_meta[(note, ch, st)]
                        # 将该音替换为多个和弦键的 on/off 对，保持相同时长
                        for k in chord_keys:
                            out.append({'start_time': st, 'type': 'note_on', 'key': k, 'velocity': int(ev.get('velocity', 64)), 'channel': ch, 'note': note})
                        for k in chord_keys:
                            out.append({'start_time': t, 'type': 'note_off', 'key': k, 'velocity': 0, 'channel': ch, 'note': note})
                    else:
                        out.append(ev)
                else:
                    out.append(ev)
            # 输出仍按时间排序
            out.sort(key=lambda x: (float(x.get('start_time', 0.0)), 0 if x.get('type')=='note_on' else 1))
            return out
        except Exception:
            return events
    
    def _map_midi_note_to_key(self, midi_note: int, key_mapping: Dict[str, str]) -> Optional[str]:
        """将MIDI音符映射到固定21键(L/M/H x 1..7)，半音采用就近度数映射。
        强化回退策略：若 key_id 不在映射中，按邻近度数/区域回退，确保总能返回某个键位，避免丢音。"""
        try:
            # 八度计算
            octave = (midi_note // 12) - 1

            # 选择区域：<=3 为低音(L)，<=4 为中音(M)，其余为高音(H)
            if octave <= 3:
                region = 'L'
            elif octave <= 4:
                region = 'M'
            else:
                region = 'H'

            # 半音-度数最近映射：C=0, D=2, E=4, F=5, G=7, A=9, B=11
            pc = midi_note % 12
            scale_degrees = [0, 2, 4, 5, 7, 9, 11]
            # 选择与 pc 最近的度数
            nearest = min(scale_degrees, key=lambda d: abs(d - pc))
            degree_index = scale_degrees.index(nearest)  # 0..6
            degree = str(degree_index + 1)  # '1'..'7'

            # 优先目标 key_id
            key_id = f"{region}{degree}"
            if key_id in key_mapping:
                return key_mapping[key_id]

            # 若禁用回退策略，则直接返回 None，不进行后续回退
            if not bool(self.options.get('enable_key_fallback', True)):
                return None

            # 回退1：同区域内按度数邻近顺序寻找
            order = ['1','2','3','4','5','6','7']
            idx = order.index(degree) if degree in order else 0
            candidates = []
            # 交替向两侧扩散
            for step in range(1, 7):
                # 左
                li = idx - step
                if li >= 0:
                    candidates.append(f"{region}{order[li]}")
                # 右
                ri = idx + step
                if ri < len(order):
                    candidates.append(f"{region}{order[ri]}")
            for cid in candidates:
                if cid in key_mapping:
                    return key_mapping[cid]

            # 回退2：邻近区域（优先 M 作为中枢），尽量保持音高相近
            region_priority = {
                'L': ['M','H'],
                'M': ['L','H'],
                'H': ['M','L'],
            }
            for rg in region_priority.get(region, ['M','L','H']):
                cid = f"{rg}{degree}"
                if cid in key_mapping:
                    return key_mapping[cid]
                # 同步度数扩散
                for step in range(1, 7):
                    li = idx - step
                    if li >= 0 and f"{rg}{order[li]}" in key_mapping:
                        return key_mapping[f"{rg}{order[li]}"]
                    ri = idx + step
                    if ri < len(order) and f"{rg}{order[ri]}" in key_mapping:
                        return key_mapping[f"{rg}{order[ri]}"]

            # 回退3：实在找不到，返回映射中的任意一个键（稳定地选第一个）
            if key_mapping:
                # 优先返回有序的 L/M/H 顺序中的第一个
                for rg in ['M','L','H']:
                    for d in order:
                        cid = f"{rg}{d}"
                        if cid in key_mapping:
                            return key_mapping[cid]
                # 或者直接返回一个值
                return next(iter(key_mapping.values()))
            return None
        except Exception:
            return None
    
    def _get_note_degree(self, midi_note: int) -> str:
        """获取MIDI音符的度数"""
        try:
            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            note_name = note_names[midi_note % 12]
            
            # 度数映射
            degree_mapping = {
                'C': '1', 'C#': '1',   # 1度 = C, C#
                'D': '2', 'D#': '2',   # 2度 = D, D#
                'E': '3',              # 3度 = E
                'F': '4', 'F#': '4',   # 4度 = F, F#
                'G': '5', 'G#': '5',   # 5度 = G, G#
                'A': '6', 'A#': '6',   # 6度 = A, A#
                'B': '7'               # 7度 = B
            }
            
            return degree_mapping.get(note_name, '1')
        except Exception:
            return '1'
    
    def _detect_chord_from_notes(self, notes: List[int]) -> Optional[str]:
        """从音符集合检测和弦"""
        try:
            # 标准化到八度内
            normalized_notes = [note % 12 for note in notes]
            normalized_notes = list(set(normalized_notes))  # 去重
            normalized_notes.sort()
            
            # 和弦识别模式
            chord_patterns = {
                (0, 4, 7): 'C',      # 大三和弦 C-E-G
                (0, 3, 7): 'Dm',     # 小三和弦 D-F-A
                (0, 4, 7, 10): 'G7', # 属七和弦 G-B-D-F
                (2, 5, 9): 'Em',     # 小三和弦 E-G-B
                (5, 9, 0): 'F',      # 大三和弦 F-A-C
                (7, 11, 2): 'G',     # 大三和弦 G-B-D
                (9, 0, 4): 'Am'      # 小三和弦 A-C-E
            }
            
            # 尝试匹配和弦模式
            for pattern, chord_name in chord_patterns.items():
                if tuple(normalized_notes) == pattern:
                    return chord_name
            
            return None
            
        except Exception:
            return None
    
    def _handle_error(self, error_msg: str):
        """处理错误"""
        self.logger.log(error_msg, "ERROR")
        if self.playback_callbacks['on_error']:
            self.playback_callbacks['on_error'](error_msg)
    
    def get_status(self) -> Dict[str, Any]:
        """获取播放状态"""
        return {
            'is_playing': self.is_playing,
            'is_paused': self.is_paused,
            'current_tempo': self.current_tempo,
            'event_count': len(self.current_events) if self.current_events else 0
        } 