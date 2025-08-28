"""
自动演奏模块
提供基于LRCp乐谱和MIDI文件的自动演奏功能
"""

import time
import threading
from typing import List, Optional, Callable, Dict, Any
from meowauto.utils import midi_tools
from meowauto.core import Event, KeySender, Logger
from meowauto.playback.strategies import get_strategy
from meowauto.playback.keymaps import get_default_mapping
from meowauto.music.chord_engine import ChordEngine

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
            'send_ahead_ms': 0,                # 提前量（0 = 不提前，严格与事件时间对齐）
            'spin_threshold_ms': 1,            # 忙等阈值（最后阶段改为忙等，保证更精准触发）
            'post_action_sleep_ms': 0,         # 每批动作后的微停，0 表示不强制微停
            # 可选：和弦伴奏（附加映射事件，不改原事件）
            'enable_chord_accomp': True,       # 启用和弦伴奏（默认开启）
            'chord_accomp_mode': 'triad',      # triad/triad7/greedy
            'chord_accomp_min_sustain_ms': 120,# 伴奏最小延音阈值（毫秒）
            # MIDI 预处理
            'enable_quantize': False,          # 启用时间量化（默认关闭，保证“所见即所得”的时间）
            'quantize_grid_ms': 30,            # 量化栅格（毫秒）
            'enable_black_transpose': True,    # 启用黑键移调
            'black_transpose_strategy': 'down', # 移调策略：down/nearest
            # 键位映射策略
            'enable_key_fallback': True        # 启用21键映射的强化回退策略
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
                           key_mapping: Dict[str, str] = None,
                           strategy_name: Optional[str] = None) -> bool:
        """开始自动演奏（MIDI模式）
        解析 MIDI -> 展开为 note_on/note_off 事件 -> 直接走映射事件线程（逐事件调度，无同窗批处理）。
        """
        if self.is_playing:
            self.logger.log("自动演奏已在进行中", "WARNING")
            return False
        
        if not midi_file:
            self.logger.log("MIDI文件路径为空", "ERROR")
            return False
        
        # 解析并展开为事件，再使用“已映射事件线程”播放，避免旧的批处理逻辑
        events = self._parse_midi_file(midi_file, key_mapping=key_mapping, strategy_name=strategy_name)
        if not events:
            return False

        # 对同一时间戳，保证 note_off 先于 note_on
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
        
        # 调用开始回调
        if self.playback_callbacks['on_start']:
            self.playback_callbacks['on_start']()
        
        self.logger.log("开始自动演奏（MIDI模式，经解析后逐事件调度）", "INFO")
        if self.debug:
            self.logger.log(f"[DEBUG] 文件: {midi_file}, 展开事件数: {len(events)}, 速度: {self.current_tempo}", "DEBUG")
        return True
    
    def start_auto_play_midi_events(self, notes: List[Dict[str, Any]], tempo: float = 1.0,
                                    key_mapping: Dict[str, str] = None,
                                    strategy_name: Optional[str] = None) -> bool:
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
        if events and bool(self.options.get('enable_chord_accomp', False)):
            try:
                acc = self._generate_chord_accompaniment(events, key_mapping or self._get_default_key_mapping(), strategy_name)
                if acc:
                    events.extend(acc)
                    if self.debug:
                        self.logger.log(f"[DEBUG] 伴奏追加事件: {len(acc)}", "DEBUG")
            except Exception:
                pass

        if not events:
            self.logger.log("展开后的回放事件为空", "ERROR")
            return False

        # 对同一时间戳，保证 note_off 先于 note_on
        try:
            events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            pass

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

            # 排序并计算总时长（同一时间戳优先释放再按下，避免抑制快速重按）
            try:
                events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
            except Exception:
                events.sort(key=lambda x: x['start_time'])
            total_time = events[-1]['start_time'] if events else 0.0

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
            default_tempo = 500000  # 默认120 BPM (微秒/拍)
            ticks_per_beat = midi.ticks_per_beat
            current_tempo = default_tempo
            
            # 如果没有提供键位映射，使用默认映射
            if not key_mapping:
                key_mapping = self._get_default_key_mapping()
            
            # 解析策略
            strategy = get_strategy(strategy_name or "strategy_21key")

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
                    
                # 统一处理 note_on/note_off，包括 vel=0 的 note_on 作为 note_off
                ch = getattr(msg, 'channel', 0)
                if msg.type == 'note_on' and msg.velocity > 0:
                    # 音符开始：按 (channel, note) 入栈，支持同音重叠
                    key_id = (ch, msg.note)
                    stack = active_notes.setdefault(key_id, [])
                    stack.append({
                        'start_time': track_time,
                        'velocity': msg.velocity,
                        'channel': ch
                    })

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # 音符结束：匹配最近一次同键入栈
                    note = msg.note
                    key_id = (ch, note)
                    if key_id in active_notes and active_notes[key_id]:
                        start_info = active_notes[key_id].pop()
                        if not active_notes[key_id]:
                            del active_notes[key_id]

                        # 转换为绝对时间（秒），使用 tempo 表精确换算
                        start_time = tick_to_seconds(start_info['start_time'])
                        end_time = tick_to_seconds(track_time)

                        # 使用策略映射到按键
                        key = strategy.map_note(note, key_mapping, self.options)
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
                                'channel': ch,
                                'note': note
                            })
                        else:
                            if self.debug:
                                try:
                                    self.logger.log(
                                        f"[DEBUG] map_note returned None: note={note}, ch={ch}, pc={note % 12}, strategy={getattr(strategy, 'name', 'unknown')}, fallback={bool(self.options.get('enable_key_fallback', True))}",
                                        "DEBUG",
                                    )
                                except Exception:
                                    pass
            
            # 处理未结束的音符（设置合理的持续时间），支持 (channel,note) 的多重入栈
            for (ch, note), stack in list(active_notes.items()):
                while stack:
                    info = stack.pop()
                    start_time = tick_to_seconds(info['start_time'])
                    # 根据音符区间设置合理的默认持续时间
                    duration = 0.5  # 默认0.5秒
                    if note < 60:  # 低音区，持续时间稍长
                        duration = 0.8
                    elif note > 72:  # 高音区，持续时间稍短
                        duration = 0.3
                    end_time = start_time + duration

                    # 使用策略映射
                    key = strategy.map_note(note, key_mapping, self.options)
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
                    else:
                        if self.debug:
                            try:
                                self.logger.log(
                                    f"[DEBUG] map_note returned None (dangling): note={note}, ch={ch}, pc={note % 12}, strategy={getattr(strategy, 'name', 'unknown')}, fallback={bool(self.options.get('enable_key_fallback', True))}",
                                    "DEBUG",
                                )
                            except Exception:
                                pass
            
            # 可选：和弦伴奏（对原始事件集生成伴奏，再一起移调与排序）
            if events and bool(self.options.get('enable_chord_accomp', False)):
                try:
                    acc = self._generate_chord_accompaniment(events, key_mapping, strategy_name)
                    if acc:
                        events.extend(acc)
                        if self.debug:
                            self.logger.log(f"[DEBUG] 伴奏追加事件: {len(acc)}", "DEBUG")
                except Exception:
                    pass

            # 预处理：黑键移调（不改变时间，只改变映射），不再做任何时间量化
            if bool(self.options.get('enable_black_transpose', True)):
                events = midi_tools.transpose_black_keys(events, strategy=str(self.options.get('black_transpose_strategy', 'down')))

            # 按时间排序；同一时间戳优先释放再按下，避免抑制快速重按
            try:
                events.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
            except Exception:
                events.sort(key=lambda x: x['start_time'])
            if self.debug and events:
                self.logger.log(f"[DEBUG] 解析后事件数: {len(events)}，示例: {events[:5]}", "DEBUG")

            return events
        except Exception as e:
            # 兜底：解析过程中出现异常
            try:
                self._handle_error(f"MIDI解析失败: {str(e)}")
            except Exception:
                pass
            return []
    
    def _get_default_key_mapping(self) -> Dict[str, str]:
        """获取默认21键位映射（委托到 keymaps.get_default_mapping）。"""
        try:
            return get_default_mapping()
        except Exception:
            return {}
    
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