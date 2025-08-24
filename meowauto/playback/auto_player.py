"""
自动演奏模块
提供基于LRCp乐谱和MIDI文件的自动演奏功能
"""

import time
import threading
from typing import List, Optional, Callable, Dict, Any
from meowauto.utils import midi_tools
from meowauto.core import Event, KeySender, Logger
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
        # 可配置选项
        self.options = {
            'allow_retrigger': True,           # 允许同一键在按下状态下进行重触发（快速抬起再按下）
            'retrigger_min_gap_ms': 40,        # 重触发的最小时间间隔
            'epsilon_ms': 6,                   # 批处理窗口大小（毫秒）
            'send_ahead_ms': 2,                # 提前量（为抵消系统调度/输入延迟，负值表示延后）
            'spin_threshold_ms': 1,            # 忙等阈值（最后阶段改为忙等，保证更精准触发）
            'post_action_sleep_ms': 0,         # 每批动作后的微停，0 表示不强制微停
            'enable_chord_keys': True,         # 启用和弦按键（z,x,c,v,b,n,m）
            'chord_drop_root': False,          # 使用和弦键时，是否去掉根音的单键映射
            'chord_mode': 'triad7',            # 和弦识别模式：triad7/triad/greedy
            'chord_min_sustain_ms': 120,       # 和弦键最小延音（毫秒）
            # MIDI 预处理
            'enable_quantize': True,           # 启用时间量化
            'quantize_grid_ms': 30,            # 量化栅格（毫秒）
            'enable_black_transpose': True,    # 启用黑键移调
            'black_transpose_strategy': 'down' # 移调策略：down/nearest
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
                           key_mapping: Dict[str, str] = None) -> bool:
        """开始自动演奏（MIDI模式）"""
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        
        if not midi_file:
            self.logger.log("MIDI文件路径为空", "ERROR")
            return False
        
        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        
        # 启动MIDI演奏线程
        self.play_thread = threading.Thread(
            target=self._auto_play_midi_thread, 
            args=(midi_file, key_mapping)
        )
        self.play_thread.daemon = True
        self.play_thread.start()
        
        # 调用开始回调
        if self.playback_callbacks['on_start']:
            self.playback_callbacks['on_start']()
        
        self.logger.log("开始自动演奏（MIDI模式）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 文件: {midi_file}, 速度: {self.current_tempo}", "DEBUG")
        return True
    
    def start_auto_play_midi_events(self, notes: List[Dict[str, Any]], tempo: float = 1.0,
                                    key_mapping: Dict[str, str] = None) -> bool:
        """开始自动演奏（使用外部解析后的MIDI音符事件）
        期望 notes 为带有 start_time/end_time/note/channel 的列表。本方法会按固定21键映射展开为 note_on/note_off 事件，
        并直接进入回放线程，不再进行黑键移调或量化等后处理。
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
        for n in notes:
            try:
                st = float(n.get('start_time', 0.0))
                et = float(n.get('end_time', st))
                note = int(n.get('note', 0))
                ch = int(n.get('channel', 0))
                key = self._map_midi_note_to_key(note, key_mapping)
                if not key:
                    continue
                events.append({'start_time': st, 'type': 'note_on', 'key': key, 'velocity': int(n.get('velocity', 64)), 'channel': ch, 'note': note})
                events.append({'start_time': max(et, st), 'type': 'note_off', 'key': key, 'velocity': 0, 'channel': ch, 'note': note})
            except Exception:
                continue

        if not events:
            self.logger.log("展开后的回放事件为空", "ERROR")
            return False

        # 设置状态并启动线程
        self.current_tempo = tempo
        self.is_playing = True
        self.is_paused = False
        self.play_thread = threading.Thread(target=self._auto_play_mapped_events_thread, args=(events,))
        self.play_thread.daemon = True
        self.play_thread.start()

        if self.playback_callbacks['on_start']:
            self.playback_callbacks['on_start']()
        self.logger.log("开始自动演奏（外部MIDI事件）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 外部事件数: {len(events)}, 速度: {self.current_tempo}", "DEBUG")
        return True
    
    def stop_auto_play(self):
        """停止自动演奏"""
        if not self.is_playing:
            return
        
        self.is_playing = False
        self.is_paused = False
        
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

            # 排序并计算总时长
            events.sort(key=lambda x: x['start_time'])
            total_time = events[-1]['start_time'] if events else 0.0

            from time import perf_counter
            start_perf = perf_counter()
            key_sender = KeySender()

            idx = 0
            epsilon = max(0.001, float(self.options.get('epsilon_ms', 6)) / 1000.0)
            send_ahead = float(self.options.get('send_ahead_ms', 2)) / 1000.0
            spin_threshold = max(0.0, float(self.options.get('spin_threshold_ms', 1)) / 1000.0)
            post_action_sleep = max(0.0, float(self.options.get('post_action_sleep_ms', 0)) / 1000.0)

            # 引用计数避免过早释放
            active_counts: Dict[str, int] = {}

            # === 和弦检测与和弦键位支持（与 _auto_play_midi_thread 保持一致） ===
            chord_key_map: Dict[str, str] = {
                'C': 'z', 'Dm': 'x', 'Em': 'c', 'F': 'v', 'G': 'b', 'Am': 'n', 'G7': 'm'
            }
            chord_patterns: Dict[str, set] = {
                'G7': {7, 11, 2, 5},  # 优先识别七和弦
                'C': {0, 4, 7},
                'Dm': {2, 5, 9},
                'Em': {4, 7, 11},
                'F': {5, 9, 0},
                'G': {7, 11, 2},
                'Am': {9, 0, 4},
            }
            # 记录键最近一次按下，用于重触发/延迟释放判断
            last_press_time: Dict[str, float] = {}
            # 正在按下的和弦：chord_key -> {pc: count}
            active_chords_pc_counts: Dict[str, Dict[int, int]] = {}
            # 和弦延迟释放：chord_key -> 可释放时间戳（perf_counter 相对 start_perf）
            chord_pending_release: Dict[str, float] = {}

            def detect_chord_from_note_ons(note_on_events: List[Dict[str, Any]]) -> Optional[tuple]:
                """从一批 note_on 事件中检测和弦，返回 (name, patt)。遵循 options['chord_mode'] 策略。"""
                if not note_on_events:
                    return None
                pcs = set((ev.get('note', 0) % 12) for ev in note_on_events if 'note' in ev)
                if not pcs:
                    return None
                mode = str(self.options.get('chord_mode', 'triad7'))
                if mode == 'triad7':
                    for name, patt in chord_patterns.items():
                        if patt.issubset(pcs):
                            return (name, patt)
                    return None
                if mode == 'triad':
                    triad_names = [n for n in chord_patterns.keys() if n != 'G7']
                    for name in triad_names:
                        patt = chord_patterns[name]
                        if patt.issubset(pcs):
                            return (name, patt)
                    return None
                # greedy: 选择交集最大的候选，至少2个共有成员
                best = None
                best_size = 0
                for name, patt in chord_patterns.items():
                    inter = patt.intersection(pcs)
                    sz = len(inter)
                    if sz > best_size and sz >= 2:
                        best = (name, patt)
                        best_size = sz
                return best

            while idx < len(events) and self.is_playing:
                while self.is_paused and self.is_playing:
                    time.sleep(0.01)

                group_time = events[idx]['start_time'] / max(0.01, self.current_tempo)

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
                        while (perf_counter() - start_perf) < target and self.is_playing and not self.is_paused:
                            pass
                        break

                j = idx
                batch: List[Dict[str, Any]] = []
                while j < len(events):
                    t = events[j]['start_time'] / max(0.01, self.current_tempo)
                    if abs(t - group_time) <= epsilon:
                        batch.append(events[j])
                        j += 1
                    else:
                        break

                release_once: List[str] = []
                press_once: List[str] = []
                chord_press: List[str] = []

                for ev in batch:
                    if ev['type'] == 'note_off':
                        k = ev['key']
                        c = active_counts.get(k, 0)
                        if c > 0:
                            c -= 1
                            active_counts[k] = c
                            if c == 0:
                                release_once.append(k)
                        # 若存在和弦键，按音级减少其计数，必要时释放
                        pc = ev.get('note', 0) % 12 if 'note' in ev else None
                        if pc is not None:
                            for ck, pc_counts in list(active_chords_pc_counts.items()):
                                if pc in pc_counts and pc_counts[pc] > 0:
                                    pc_counts[pc] -= 1
                                    if all(v <= 0 for v in pc_counts.values()):
                                        # 所有成员结束，考虑释放和弦键（加入延迟释放逻辑）
                                        nowt = perf_counter() - start_perf
                                        chord_min_sustain = max(0.0, float(self.options.get('chord_min_sustain_ms', 120)) / 1000.0)
                                        first_press = last_press_time.get(ck, nowt)
                                        elapsed = nowt - first_press
                                        if elapsed >= chord_min_sustain:
                                            if ck not in release_once:
                                                release_once.append(ck)
                                            ckc = active_counts.get(ck, 0)
                                            if ckc > 0:
                                                active_counts[ck] = max(0, ckc - 1)
                                            del active_chords_pc_counts[ck]
                                            chord_pending_release.pop(ck, None)
                                        else:
                                            chord_pending_release[ck] = nowt + (chord_min_sustain - elapsed)
                                            del active_chords_pc_counts[ck]

                # 检查到期的延迟释放的和弦
                if chord_pending_release:
                    nowt = perf_counter() - start_perf
                    due = [ck for ck, t in chord_pending_release.items() if nowt >= t]
                    for ck in due:
                        if ck not in release_once:
                            release_once.append(ck)
                        ckc = active_counts.get(ck, 0)
                        if ckc > 0:
                            active_counts[ck] = max(0, ckc - 1)
                        chord_pending_release.pop(ck, None)

                if release_once:
                    key_sender.release(release_once)
                    if post_action_sleep > 0:
                        time.sleep(post_action_sleep)

                # 和弦检测（仅处理按下事件）
                enable_chord_keys = bool(self.options.get('enable_chord_keys', False))
                chord_drop_root = bool(self.options.get('chord_drop_root', False))
                detected = None
                if enable_chord_keys:
                    note_on_events = [ev for ev in batch if ev['type'] == 'note_on']
                    detected = detect_chord_from_note_ons(note_on_events)
                    if detected:
                        name, patt = detected
                        ck = chord_key_map.get(name)
                        if ck:
                            if ck not in active_chords_pc_counts:
                                active_chords_pc_counts[ck] = {pc: 0 for pc in patt}
                            for ev in note_on_events:
                                pc = ev.get('note', 0) % 12
                                if pc in active_chords_pc_counts[ck]:
                                    active_chords_pc_counts[ck][pc] += 1

                for ev in batch:
                    if ev['type'] == 'note_on':
                        k = ev['key']
                        c = active_counts.get(k, 0)
                        if c == 0:
                            press_once.append(k)
                            active_counts[k] = 1
                            last_press_time[k] = perf_counter() - start_perf
                        else:
                            # 简化：不做重触发，直接递增计数，等待后续 note_off 对齐
                            active_counts[k] = c + 1

                # 若检测到和弦，按下和弦键
                if enable_chord_keys and detected:
                    name, _ = detected
                    ck = chord_key_map.get(name)
                    if ck:
                        cc = active_counts.get(ck, 0)
                        if cc == 0:
                            chord_press.append(ck)
                            active_counts[ck] = 1
                            last_press_time[ck] = perf_counter() - start_perf
                        else:
                            active_counts[ck] = cc + 1
                        if ck in chord_pending_release:
                            chord_pending_release.pop(ck, None)

                if press_once:
                    key_sender.press(press_once)
                    for k in press_once:
                        last_press_time[k] = perf_counter() - start_perf

                if chord_press:
                    key_sender.press(list(dict.fromkeys(chord_press)))

                if self.playback_callbacks['on_progress'] and total_time > 0:
                    now = perf_counter() - start_perf
                    progress = max(0.0, min(100.0, (now / (total_time / max(0.01, self.current_tempo))) * 100))
                    try:
                        self.playback_callbacks['on_progress'](progress)
                    except Exception:
                        pass

                idx = j

            remaining_pressed = [k for k, c in active_counts.items() if c > 0]
            if remaining_pressed:
                key_sender.release(remaining_pressed)

            if self.is_playing:
                if self.playback_callbacks['on_complete']:
                    self.playback_callbacks['on_complete']()
                self.logger.log("外部事件回放完成", "SUCCESS")

        except Exception as e:
            error_msg = f"外部事件回放失败: {str(e)}"
            self._handle_error(error_msg)
        finally:
            self.is_playing = False
    
    def _auto_play_midi_thread(self, midi_file: str, key_mapping: Dict[str, str] = None):
        """自动演奏线程 - MIDI模式（精确时序 + 固定21键映射）"""
        try:
            # 解析MIDI文件
            events = self._parse_midi_file(midi_file, key_mapping)
            if not events:
                self._handle_error("MIDI文件解析失败")
                return

            # 按时间排序并计算总时长
            events.sort(key=lambda x: x['start_time'])
            total_time = events[-1]['start_time'] if events else 0.0
            if self.debug:
                self.logger.log(f"[DEBUG] 解析到事件数: {len(events)}, 总时长: {total_time:.3f}s", "DEBUG")

            # 开始自动演奏
            from time import perf_counter
            start_perf = perf_counter()
            key_sender = KeySender()

            idx = 0
            epsilon = max(0.001, float(self.options.get('epsilon_ms', 6)) / 1000.0)  # 批处理窗口，默认 ~6ms
            send_ahead = float(self.options.get('send_ahead_ms', 2)) / 1000.0
            spin_threshold = max(0.0, float(self.options.get('spin_threshold_ms', 1)) / 1000.0)
            post_action_sleep = max(0.0, float(self.options.get('post_action_sleep_ms', 0)) / 1000.0)
            chord_mode = str(self.options.get('chord_mode', 'triad7'))
            chord_min_sustain = max(0.0, float(self.options.get('chord_min_sustain_ms', 120)) / 1000.0)
            # 键位引用计数，避免多个音符映射同一键时的过早释放
            active_counts: Dict[str, int] = {}
            last_press_time: Dict[str, float] = {}
            # 和弦键映射与生命周期跟踪（按音级统计）
            chord_key_map: Dict[str, str] = {
                'C': 'z', 'Dm': 'x', 'Em': 'c', 'F': 'v', 'G': 'b', 'Am': 'n', 'G7': 'm'
            }
            chord_patterns: Dict[str, set] = {
                'G7': {7, 11, 2, 5},  # 优先识别七和弦
                'C': {0, 4, 7},
                'Dm': {2, 5, 9},
                'Em': {4, 7, 11},
                'F': {5, 9, 0},
                'G': {7, 11, 2},
                'Am': {9, 0, 4},
            }
            chord_roots: Dict[str, int] = {
                'C': 0, 'Dm': 2, 'Em': 4, 'F': 5, 'G': 7, 'Am': 9, 'G7': 7
            }
            # 正在按下的和弦：chord_key -> {pc: count}
            active_chords_pc_counts: Dict[str, Dict[int, int]] = {}
            # 和弦延迟释放：chord_key -> 可释放时间戳（perf_counter 相对 start_perf）
            chord_pending_release: Dict[str, float] = {}

            def detect_chord(note_ons: List[Dict[str, Any]]) -> Optional[tuple]:
                """从一批 note_on 事件中检测和弦，返回 (name, pcs)。根据 chord_mode 调整识别策略。
                triad7: 优先匹配七和弦，再匹配三和弦（要求模式完整子集）
                triad: 仅匹配三和弦（要求模式完整子集）
                greedy: 贪心匹配，优先匹配包含成员最多的已知和弦，允许部分匹配（至少2个成员）。"""
                if not note_ons:
                    return None
                pcs = set((ev.get('note', 0) % 12) for ev in note_ons if 'note' in ev)
                if not pcs:
                    return None
                mode = chord_mode
                # triad7: 按定义顺序，G7 放在字典前面已优先
                if mode == 'triad7':
                    for name, patt in chord_patterns.items():
                        if patt.issubset(pcs):
                            return (name, patt)
                    return None
                # triad: 过滤掉七和弦
                if mode == 'triad':
                    triad_names = [n for n in chord_patterns.keys() if n != 'G7']
                    for name in triad_names:
                        patt = chord_patterns[name]
                        if patt.issubset(pcs):
                            return (name, patt)
                    return None
                # greedy: 选择交集最大的候选，至少2个共有成员
                best = None
                best_size = 0
                for name, patt in chord_patterns.items():
                    inter = patt.intersection(pcs)
                    sz = len(inter)
                    if sz > best_size and sz >= 2:
                        best = (name, patt)
                        best_size = sz
                return best

            while idx < len(events) and self.is_playing:
                # 暂停等待
                while self.is_paused and self.is_playing:
                    time.sleep(0.01)
                # 计算本批目标时间（按照当前速度缩放）
                group_time = events[idx]['start_time'] / max(0.01, self.current_tempo)

                # 等待到该批次时间点：分级等待 + 忙等，结合提前量
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

                # 收集同窗事件
                j = idx
                batch_events: List[Dict[str, Any]] = []

                while j < len(events):
                    t = events[j]['start_time'] / max(0.01, self.current_tempo)
                    if abs(t - group_time) <= epsilon:
                        batch_events.append(events[j])
                        j += 1
                    else:
                        break

                # 两阶段：先处理释放，再处理按下，结合引用计数
                release_once: List[str] = []
                press_once: List[str] = []
                chord_press: List[str] = []

                # 释放阶段
                for ev in batch_events:
                    if ev['type'] == 'note_off':
                        k = ev['key']
                        c = active_counts.get(k, 0)
                        if c > 0:
                            c -= 1
                            active_counts[k] = c
                            if c == 0:
                                release_once.append(k)
                        # 若存在和弦键，按音级减少其计数，必要时释放
                        pc = ev.get('note', 0) % 12 if 'note' in ev else None
                        if pc is not None:
                            for ck, pc_counts in list(active_chords_pc_counts.items()):
                                if pc in pc_counts and pc_counts[pc] > 0:
                                    pc_counts[pc] -= 1
                                    if all(v <= 0 for v in pc_counts.values()):
                                        # 所有成员结束，考虑释放和弦键（加入延迟释放逻辑）
                                        # 首次达到结束时刻记录可释放时间
                                        nowt = perf_counter() - start_perf
                                        first_press = last_press_time.get(ck, nowt)
                                        elapsed = nowt - first_press
                                        if elapsed >= chord_min_sustain:
                                            # 达到最小延音，立即释放
                                            if ck not in release_once:
                                                release_once.append(ck)
                                            # 同步减少和弦键计数并移除跟踪
                                            ckc = active_counts.get(ck, 0)
                                            if ckc > 0:
                                                active_counts[ck] = max(0, ckc - 1)
                                            del active_chords_pc_counts[ck]
                                            chord_pending_release.pop(ck, None)
                                        else:
                                            # 未达到最小延音，推迟释放
                                            chord_pending_release[ck] = nowt + (chord_min_sustain - elapsed)
                                            # 清空计数，但保留 active_counts 由延迟释放处理
                                            del active_chords_pc_counts[ck]

                # 检查到期的延迟释放的和弦
                if chord_pending_release:
                    nowt = perf_counter() - start_perf
                    due = [ck for ck, t in chord_pending_release.items() if nowt >= t]
                    for ck in due:
                        if ck not in release_once:
                            release_once.append(ck)
                        # 同步减少和弦键活动计数
                        ckc = active_counts.get(ck, 0)
                        if ckc > 0:
                            active_counts[ck] = max(0, ckc - 1)
                        chord_pending_release.pop(ck, None)

                if release_once:
                    if self.debug:
                        dbg_now = perf_counter() - start_perf
                        self.logger.log(f"[DEBUG] {dbg_now:.6f}s release {release_once}", "DEBUG")
                    key_sender.release(release_once)
                    if post_action_sleep > 0:
                        time.sleep(post_action_sleep)

                # 按下阶段 + 重触发处理
                retrigger_release: List[str] = []
                retrigger_press: List[str] = []
                allow_retrigger = bool(self.options.get('allow_retrigger', True))
                retrigger_gap = max(0.0, float(self.options.get('retrigger_min_gap_ms', 40)) / 1000.0)

                # 和弦检测（仅处理按下事件）
                enable_chord_keys = bool(self.options.get('enable_chord_keys', False))
                chord_drop_root = bool(self.options.get('chord_drop_root', False))
                detected = None
                if enable_chord_keys:
                    note_on_events = [ev for ev in batch_events if ev['type'] == 'note_on']
                    detected = detect_chord(note_on_events)
                    if detected:
                        name, patt = detected
                        ck = chord_key_map.get(name)
                        if ck:
                            # 初始化和弦成员PC计数
                            if ck not in active_chords_pc_counts:
                                active_chords_pc_counts[ck] = {pc: 0 for pc in patt}
                            # 增加与本批相关的PC计数
                            for ev in note_on_events:
                                pc = ev.get('note', 0) % 12
                                if pc in active_chords_pc_counts[ck]:
                                    active_chords_pc_counts[ck][pc] += 1

                for ev in batch_events:
                    if ev['type'] == 'note_on':
                        k = ev['key']
                        c = active_counts.get(k, 0)
                        # 不抑制旋律：即使检测到和弦，也允许单个音符按键照常触发
                        if c == 0:
                            press_once.append(k)
                            active_counts[k] = 1
                            last_press_time[k] = perf_counter() - start_perf
                        else:
                            # 已按下同键，考虑重触发
                            if allow_retrigger:
                                nowt = perf_counter() - start_perf
                                lastt = last_press_time.get(k, -1e9)
                                if (nowt - lastt) >= retrigger_gap:
                                    retrigger_release.append(k)
                                    retrigger_press.append(k)
                                    last_press_time[k] = nowt
                            # 不论是否重触发，计数加一，保障后续 note_off 对齐
                            active_counts[k] = c + 1

                # 若检测到和弦，按下和弦键
                if enable_chord_keys and detected:
                    name, _ = detected
                    ck = chord_key_map.get(name)
                    if ck:
                        cc = active_counts.get(ck, 0)
                        if cc == 0:
                            chord_press.append(ck)
                            active_counts[ck] = 1
                            # 记录首次按下时间用于延迟释放判断
                            last_press_time[ck] = perf_counter() - start_perf
                        else:
                            active_counts[ck] = cc + 1
                        # 新一轮按下时，若存在延迟释放计划，需取消
                        if ck in chord_pending_release:
                            chord_pending_release.pop(ck, None)

                # 执行按下
                if press_once:
                    if self.debug:
                        dbg_now = perf_counter() - start_perf
                        self.logger.log(f"[DEBUG] {dbg_now:.6f}s press   {press_once}", "DEBUG")
                    key_sender.press(press_once)
                    for k in press_once:
                        last_press_time[k] = perf_counter() - start_perf

                if chord_press:
                    if self.debug:
                        dbg_now = perf_counter() - start_perf
                        self.logger.log(f"[DEBUG] {dbg_now:.6f}s chord  {chord_press}", "DEBUG")
                    key_sender.press(list(dict.fromkeys(chord_press)))

                # 执行重触发（快速抬起再按下）
                if retrigger_release:
                    if self.debug:
                        dbg_now = perf_counter() - start_perf
                        self.logger.log(f"[DEBUG] {dbg_now:.6f}s retrigR {retrigger_release}", "DEBUG")
                    key_sender.release(list(dict.fromkeys(retrigger_release)))
                    if post_action_sleep > 0:
                        time.sleep(post_action_sleep)
                if retrigger_press:
                    if self.debug:
                        dbg_now = perf_counter() - start_perf
                        self.logger.log(f"[DEBUG] {dbg_now:.6f}s retrigP {retrigger_press}", "DEBUG")
                    key_sender.press(list(dict.fromkeys(retrigger_press)))

                # 进度以时间为准
                if self.playback_callbacks['on_progress'] and total_time > 0:
                    now = perf_counter() - start_perf
                    progress = max(0.0, min(100.0, (now / (total_time / max(0.01, self.current_tempo))) * 100))
                    try:
                        self.playback_callbacks['on_progress'](progress)
                    except Exception:
                        pass

                idx = j

            # 释放所有仍被按住的按键
            remaining_pressed = [k for k, c in active_counts.items() if c > 0]
            if remaining_pressed:
                key_sender.release(remaining_pressed)

            # 演奏完成
            if self.is_playing:
                if self.playback_callbacks['on_complete']:
                    self.playback_callbacks['on_complete']()
                self.logger.log("MIDI自动演奏完成", "SUCCESS")
                if self.debug:
                    end_perf = perf_counter() - start_perf
                    self.logger.log(f"[DEBUG] 实际用时: {end_perf:.3f}s", "DEBUG")

        except Exception as e:
            error_msg = f"MIDI自动演奏失败: {str(e)}"
            self._handle_error(error_msg)
        finally:
            self.is_playing = False
    
    def _parse_midi_file(self, midi_file: str, key_mapping: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """解析MIDI文件为演奏事件（固定21键映射，禁用和弦事件）"""
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
            default_tempo = 500000  # 默认120 BPM (微秒/拍)
            ticks_per_beat = midi.ticks_per_beat
            current_tempo = default_tempo
            
            # 如果没有提供键位映射，使用默认映射
            if not key_mapping:
                key_mapping = self._get_default_key_mapping()
            
            # 收集所有轨道消息及其轨内时间
            all_messages = []
            for track_num, track in enumerate(midi.tracks):
                track_time = 0
                for msg in track:
                    all_messages.append({
                        'msg': msg,
                        'track_time': track_time,
                        'track_num': track_num
                    })
                    track_time += msg.time
            
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
            global_time = 0
            active_notes = {}
            
            for msg_info in all_messages:
                msg = msg_info['msg']
                track_time = msg_info['track_time']
                
                # 处理速度变化（仅记录当前，实际换算使用 tempo 表）
                if msg.type == 'set_tempo':
                    current_tempo = msg.tempo
                    
                if msg.type == 'note_on' and msg.velocity > 0:
                    # 音符开始
                    active_notes[msg.note] = {
                        'start_time': track_time,
                        'velocity': msg.velocity,
                        'channel': getattr(msg, 'channel', 0)
                    }

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # 音符结束
                    note = msg.note
                    if note in active_notes:
                        start_info = active_notes[note]
                        
                        # 转换为绝对时间（秒），使用 tempo 表精确换算
                        start_time = tick_to_seconds(start_info['start_time'])
                        end_time = tick_to_seconds(track_time)
                        
                        # 映射到固定21键
                        key = self._map_midi_note_to_key(note, key_mapping)
                        if key:
                            # 添加按下事件
                            events.append({
                                'start_time': start_time,
                                'type': 'note_on',
                                'key': key,
                                'velocity': start_info['velocity'],
                                'channel': start_info['channel'],
                                'note': note
                            })
                            
                            # 添加释放事件
                            events.append({
                                'start_time': end_time,
                                'type': 'note_off',
                                'key': key,
                                'velocity': 0,
                                'channel': getattr(msg, 'channel', 0),
                                'note': note
                            })
                        
                        del active_notes[note]
            
            # 处理未结束的音符（设置合理的持续时间）
            for note, info in active_notes.items():
                start_time = tick_to_seconds(info['start_time'])
                # 根据音符长度设置合理的持续时间
                duration = 0.5  # 默认0.5秒
                if note < 60:  # 低音区，持续时间稍长
                    duration = 0.8
                elif note > 72:  # 高音区，持续时间稍短
                    duration = 0.3
                
                end_time = start_time + duration
                
                key = self._map_midi_note_to_key(note, key_mapping)
                if key:
                    # 添加按下事件
                    events.append({
                        'start_time': start_time,
                        'type': 'note_on',
                        'key': key,
                        'velocity': info['velocity'],
                        'channel': info['channel'],
                        'note': note
                    })
                    
                    # 添加释放事件
                    events.append({
                        'start_time': end_time,
                        'type': 'note_off',
                        'key': key,
                        'velocity': 0,
                        'channel': info['channel'],
                        'note': note
                    })
            
            # 预处理：黑键移调与量化
            if bool(self.options.get('enable_black_transpose', True)):
                events = midi_tools.transpose_black_keys(events, strategy=str(self.options.get('black_transpose_strategy', 'down')))

            # 按时间排序
            events.sort(key=lambda x: x['start_time'])

            if bool(self.options.get('enable_quantize', True)):
                grid_ms = int(self.options.get('quantize_grid_ms', 30))
                events = midi_tools.quantize_events(events, grid_ms=max(1, grid_ms))
            if self.debug:
                if events:
                    self.logger.log(f"[DEBUG] 事件样例: {events[:3]}", "DEBUG")
                self.logger.log(f"[DEBUG] MIDI解析完成: {len(events)} 个事件", "DEBUG")
            else:
                self.logger.log(f"MIDI解析完成: {len(events)} 个事件", "INFO")
            return events
            
        except Exception as e:
            self.logger.log(f"MIDI文件解析失败: {str(e)}", "ERROR")
            return []
    
    def _get_default_key_mapping(self) -> Dict[str, str]:
        """获取默认键盘映射 - 21键系统"""
        return {
            # 低音区 (L1-L7): a, s, d, f, g, h, j
            'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
            
            # 中音区 (M1-M7): q, w, e, r, t, y, u  
            'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
            
            # 高音区 (H1-H7): 1, 2, 3, 4, 5, 6, 7
            'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7'
        }
    
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