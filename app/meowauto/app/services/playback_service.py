# -*- coding: utf-8 -*-
"""
PlaybackService: 播放相关服务（占位）
- 后续将把 app.py 中与 MIDI/自动演奏相关的逻辑迁移至此
- 当前提供最小接口占位，不在应用中直接调用
"""
from typing import Any, Callable, Optional, List, Dict
from meowauto.midi import analyzer
from meowauto.core import Logger
try:
    from meowauto.net.clock import ClockProvider, LocalClock, NetworkClockProvider
except Exception:
    ClockProvider = Any  # 回退占位
    LocalClock = None
    NetworkClockProvider = None

class PlaybackService:
    def __init__(self, logger: Optional[Any] = None, clock_provider: Optional[Any] = None):
        # 确保有可用的 logger
        self.logger = logger or Logger()
        self.midi_player = None
        self.auto_player = None
        # 默认使用本地时钟（若可用）
        try:
            self.clock_provider = clock_provider or (LocalClock() if LocalClock else None)
        except Exception:
            self.clock_provider = clock_provider or None
        # 解析/播放前置设置（可由页面UI注入）
        self.analysis_settings: Dict[str, Any] = {
            'auto_transpose': True,        # 自动选择白键率最高的整体移调（默认开启）
            'manual_semitones': 0,         # 当 auto_transpose=False 时使用
            'min_note_duration_ms': 25,    # 短音阈值（仅对非鼓），默认25ms
        }
        # 最近一次分析统计（供UI展示）
        self.last_analysis_stats: Dict[str, Any] = {'k': 0, 'white_rate': None}

    def init_players(self) -> None:
        """延迟初始化播放器（占位）。"""
        try:
            if self.midi_player is None:
                from meowauto.playback import MidiPlayer
                self.midi_player = MidiPlayer(self.logger)
        except Exception:
            pass
        try:
            if self.auto_player is None:
                try:
                    from meowauto.playback import AutoPlayer  # 常规导入路径
                except Exception:
                    from meowauto.playback.auto_player import AutoPlayer  # 回退导入
                self.auto_player = AutoPlayer(self.logger)
                # 初始化后尝试下发时钟
                try:
                    if self.clock_provider and hasattr(self.auto_player, 'set_clock_provider'):
                        self.auto_player.set_clock_provider(self.clock_provider)
                except Exception:
                    pass
        except Exception:
            pass

    # ===== 解析设置注入 =====
    def configure_analysis_settings(self, *, auto_transpose: Optional[bool] = None,
                                    manual_semitones: Optional[int] = None,
                                    min_note_duration_ms: Optional[int] = None) -> None:
        try:
            if auto_transpose is not None:
                self.analysis_settings['auto_transpose'] = bool(auto_transpose)
            if manual_semitones is not None:
                try:
                    self.analysis_settings['manual_semitones'] = int(manual_semitones)
                except Exception:
                    pass
            if min_note_duration_ms is not None:
                try:
                    self.analysis_settings['min_note_duration_ms'] = max(0, int(min_note_duration_ms))
                except Exception:
                    pass
            if self.logger:
                self.logger.log(f"[DEBUG] 更新解析设置: {self.analysis_settings}", "DEBUG")
        except Exception:
            pass

    # 内部：应用短音过滤与整体移调（白键率最高）。对鼓轨/通道跳过。
    def _apply_pre_filters_and_transpose(self, notes: List[Dict]) -> List[Dict]:
        if not notes:
            return []
        try:
            min_ms = int(self.analysis_settings.get('min_note_duration_ms', 25) or 25)
        except Exception:
            min_ms = 25
        thr = max(0, min_ms) / 1000.0

        # 过滤（仅非鼓）
        out: List[Dict] = []
        dropped = 0
        for n in notes:
            try:
                is_drum = bool(n.get('is_drum')) or (int(n.get('channel', 0)) == 9)
            except Exception:
                is_drum = False
            dur = float(n.get('duration', 0.0))
            if dur <= 0:
                st = float(n.get('start_time', 0.0)); et = float(n.get('end_time', st))
                dur = max(0.0, et - st)
            if not is_drum and thr > 0 and dur < thr:
                dropped += 1
                continue
            out.append(dict(n))
        if self.logger and min_ms > 0:
            self.logger.log(f"[DEBUG] 短音过滤: 丢弃 {dropped} / {len(notes)} (<{min_ms}ms)", "DEBUG")

        # 自动移调（白键率最高），仅对非鼓的 note 生效
        auto_tx = bool(self.analysis_settings.get('auto_transpose', True))
        try:
            manual_k = int(self.analysis_settings.get('manual_semitones', 0) or 0)
        except Exception:
            manual_k = 0

        def is_white(p: int) -> bool:
            return (p % 12) in (0, 2, 4, 5, 7, 9, 11)

        # 统计函数（按事件计数；duration 权重留作后续可选）
        def white_rate_for_k(k: int) -> float:
            cnt = 0
            tot = 0
            for n in out:
                try:
                    is_drum = bool(n.get('is_drum')) or (int(n.get('channel', 0)) == 9)
                except Exception:
                    is_drum = False
                if is_drum:
                    continue
                try:
                    p0 = int(n.get('note', 0))
                except Exception:
                    continue
                p = p0 + int(k)
                # 超出音域的不纳入分母
                if p < 0 or p > 127:
                    continue
                tot += 1
                if is_white(p):
                    cnt += 1
            if tot == 0:
                return 0.0
            return cnt / float(max(1, tot))

        k_chosen = 0
        if auto_tx:
            candidates = list(range(-12, 13))
            scores = []
            for k in candidates:
                rate = white_rate_for_k(k)
                scores.append((k, rate))
            # 日志：输出前5名候选
            try:
                top5 = sorted(scores, key=lambda x: x[1], reverse=True)[:5]
                if self.logger:
                    self.logger.log("[DEBUG] 白键率候选TOP5: " + ", ".join([f"k={k:+d}:{r:.3f}" for k, r in top5]), "DEBUG")
            except Exception:
                pass
            # 选择：白键率最高，若并列取 |k| 最小
            if scores:
                best_rate = max(r for _, r in scores)
                tied = [k for k, r in scores if r == best_rate]
                k_chosen = sorted(tied, key=lambda x: (abs(x), x))[0]
        else:
            k_chosen = max(-12, min(12, manual_k))

        # 应用移调
        if k_chosen != 0:
            for n in out:
                try:
                    is_drum = bool(n.get('is_drum')) or (int(n.get('channel', 0)) == 9)
                except Exception:
                    is_drum = False
                if is_drum:
                    continue
                try:
                    p0 = int(n.get('note', 0))
                    n['note_orig'] = p0
                    p1 = p0 + int(k_chosen)
                    n['note'] = max(0, min(127, p1))
                except Exception:
                    pass
        # 统计白键率（用于UI展示）
        try:
            rate_chosen = white_rate_for_k(k_chosen)
        except Exception:
            rate_chosen = None
        self.last_analysis_stats = {'k': k_chosen, 'white_rate': rate_chosen}
        if self.logger and (auto_tx or k_chosen != 0):
            if rate_chosen is not None:
                self.logger.log(f"[DEBUG] 整体移调: k={k_chosen}，白键率={rate_chosen:.3f}，白键率自动={auto_tx}", "DEBUG")
            else:
                self.logger.log(f"[DEBUG] 整体移调: k={k_chosen}，白键率自动={auto_tx}", "DEBUG")
        return out

    def get_last_analysis_stats(self) -> Dict[str, Any]:
        return dict(self.last_analysis_stats)

    # ===== 时钟注入 =====
    def set_clock_provider(self, provider: Any) -> None:
        """设置/替换 ClockProvider，并尝试下发给 AutoPlayer（若支持）。"""
        self.clock_provider = provider
        try:
            if self.auto_player and hasattr(self.auto_player, 'set_clock_provider'):
                self.auto_player.set_clock_provider(provider)
        except Exception:
            pass

    # ===== 下发 AutoPlayer 选项（供 app.py 调用） =====
    def configure_auto_player(self, *, debug: Optional[bool] = None, options: Optional[Dict[str, Any]] = None) -> None:
        """配置 AutoPlayer 的调试开关与各类可选参数（和弦/黑键移调/回退等）。"""
        try:
            self.init_players()
            ap = self.auto_player
            if not ap:
                return
            if debug is not None and hasattr(ap, 'set_debug'):
                try:
                    ap.set_debug(bool(debug))
                except Exception:
                    pass
            if isinstance(options, dict) and hasattr(ap, 'set_options'):
                try:
                    ap.set_options(**options)
                except Exception:
                    pass
            if self.logger:
                self.logger.log("[DEBUG] AutoPlayer 配置已更新", "DEBUG")
        except Exception:
            pass

    def use_network_clock(self, *, servers: Optional[list] = None, timeout: float = 1.5, max_tries: int = 3) -> bool:
        """启用基于公网 NTP 的网络时钟，并尝试立即同步。"""
        try:
            if not NetworkClockProvider:
                return False
            ntp = NetworkClockProvider(servers=servers, timeout=timeout, max_tries=max_tries)
            self.set_clock_provider(ntp)
            # 如果构造未成功同步，这里再补一次（不会抛错）
            try:
                return bool(ntp.sync())
            except Exception:
                return False
        except Exception:
            return False

    def play_parts(self, parts: dict, selected_names: Optional[List] = None,
                   *, tempo: float = 1.0, strategy_name: str = 'strategy_21key',
                   on_progress: Optional[Callable[[float], None]] = None,
                   include_roles: Optional[List[str]] = None,
                   role_overrides: Optional[Dict[str, str]] = None) -> bool:
        """基于分部进行实时路由播放：为事件标注角色并交给 AutoPlayer 混合映射入口。
        - parts: Dict[str, PartSection]（要求 notes 为标准 note_on/note_off 对应的区间事件，至少含 start_time/end_time/note/channel）
        - selected_names: 选中的分部名；None 表示全部
        - tempo: 回放速度
        - strategy_name: 键位映射策略名
        """
        try:
            self.init_players()
            ap = self.auto_player
            if not ap or not hasattr(ap, 'start_auto_play_midi_events_mixed'):
                return False
            if not isinstance(parts, dict) or not parts:
                return False

            names = list(selected_names) if selected_names else list(parts.keys())
            notes: list = []

            def guess_role(ev: dict, part_name: str, meta: dict | None) -> str:
                try:
                    name_l = (part_name or '').lower()
                    if 'drum' in name_l or 'percussion' in name_l:
                        return 'drums'
                    ch = ev.get('channel')
                    if isinstance(ch, int) and ch == 9:
                        return 'drums'
                    prog = ev.get('program')
                    if isinstance(prog, int) and 32 <= prog <= 39:
                        return 'bass'
                    pitch = ev.get('note')
                    if isinstance(pitch, int) and pitch < 48:
                        return 'bass'
                    if meta:
                        mname = str(meta.get('instrument_name', '')).lower()
                        if 'drum' in mname or 'percussion' in mname:
                            return 'drums'
                        if 'bass' in mname:
                            return 'bass'
                except Exception:
                    pass
                return 'melody'

            for n in names:
                sec = parts.get(n)
                if not sec:
                    continue
                sec_meta = getattr(sec, 'meta', {}) if hasattr(sec, 'meta') else {}
                evs = getattr(sec, 'notes', []) if hasattr(sec, 'notes') else []
                for ev in evs:
                    if not isinstance(ev, dict):
                        continue
                    st = ev.get('start_time'); et = ev.get('end_time')
                    note = ev.get('note'); ch = ev.get('channel', 0)
                    if st is None or et is None or note is None:
                        # 尝试从 note_on/note_off 风格重建（若提供 type/time）
                        # 简化：跳过不完整事件
                        continue
                    # 角色：先取事件自带 -> 分部覆盖 -> 自动推断
                    role = ev.get('role') or None
                    # 分部级覆盖
                    if not role and role_overrides and n in role_overrides:
                        role = role_overrides.get(n) or None
                    if not role:
                        role = guess_role(ev, n, sec_meta)
                    # 角色过滤（若指定）
                    if include_roles and role not in include_roles:
                        continue
                    out = dict(ev)
                    out['start_time'] = float(st)
                    out['end_time'] = float(et)
                    out['note'] = int(note)
                    out['channel'] = int(ch) if isinstance(ch, int) else 0
                    out['role'] = role
                    notes.append(out)

            if not notes:
                return False

            # 绑定进度回调
            if on_progress is not None:
                try:
                    self.set_auto_callbacks(on_progress=on_progress)
                except Exception:
                    pass

            # 角色映射集：鼓、贝斯明确指定，其余走 AutoPlayer 默认
            try:
                # 优先从 keymaps_ext 导入以避免循环
                from meowauto.playback.keymaps_ext import DRUMS_KEYMAP, BASS_KEYMAP  # type: ignore
                role_keymaps = {
                    'drums': DRUMS_KEYMAP,
                    'bass': BASS_KEYMAP,
                }
            except Exception:
                try:
                    from meowauto.playback.keymaps import DRUMS_KEYMAP, BASS_KEYMAP  # 次选导入
                    role_keymaps = {
                        'drums': DRUMS_KEYMAP,
                        'bass': BASS_KEYMAP,
                    }
                except Exception:
                    try:
                        from meowauto.playback import DRUMS_KEYMAP, BASS_KEYMAP  # 最后回退
                        role_keymaps = {
                            'drums': DRUMS_KEYMAP,
                            'bass': BASS_KEYMAP,
                        }
                    except Exception:
                        role_keymaps = {}

            return bool(ap.start_auto_play_midi_events_mixed(notes, tempo=tempo, role_keymaps=role_keymaps, strategy_name=strategy_name))
        except Exception:
            return False

    def use_local_clock(self) -> None:
        """切换回本地时钟。"""
        try:
            if LocalClock:
                self.set_clock_provider(LocalClock())
        except Exception:
            pass
        try:
            if self.auto_player is None:
                try:
                    from meowauto.playback import AutoPlayer  # 常规导入路径
                except Exception:
                    from meowauto.playback.auto_player import AutoPlayer  # 回退导入
                from meowauto.core import Logger
                self.auto_player = AutoPlayer(self.logger or Logger())
                # 初始化后尝试下发时钟
                try:
                    if self.clock_provider and hasattr(self.auto_player, 'set_clock_provider'):
                        self.auto_player.set_clock_provider(self.clock_provider)
                except Exception:
                    pass
        except Exception:
            pass

    def play_midi(self, path: str, tempo: float = 1.0, volume: float = 0.7,
                  on_progress: Optional[Callable[[float], None]] = None) -> bool:
        self.init_players()
        if not self.midi_player:
            return False
        try:
            try:
                self.midi_player.set_tempo(tempo)
            except Exception:
                pass
            try:
                self.midi_player.set_volume(volume)
            except Exception:
                pass
            return bool(self.midi_player.play_midi(path, progress_callback=on_progress))
        except Exception:
            return False

    def stop_all(self) -> None:
        try:
            if self.midi_player:
                self.midi_player.stop_midi()
        except Exception:
            pass
        try:
            if self.auto_player:
                self.auto_player.stop_auto_play()
        except Exception:
            pass

    # 仅停止/暂停/恢复自动演奏（不影响 MIDI 播放）
    def stop_auto_only(self, auto_player: Optional[Any] = None) -> None:
        try:
            ap = auto_player or self.auto_player
            if ap:
                ap.stop_auto_play()
        except Exception:
            pass

    def pause_auto_only(self, auto_player: Optional[Any] = None) -> None:
        try:
            ap = auto_player or self.auto_player
            if ap and hasattr(ap, 'pause_auto_play'):
                ap.pause_auto_play()
        except Exception:
            pass

    def resume_auto_only(self, auto_player: Optional[Any] = None) -> None:
        try:
            ap = auto_player or self.auto_player
            if ap and hasattr(ap, 'resume_auto_play'):
                ap.resume_auto_play()
        except Exception:
            pass

    # ===== 自动演奏：启动与配置封装 =====
    def configure_auto_player(self, *, debug: Optional[bool] = None, options: Optional[dict] = None) -> None:
        """配置 AutoPlayer 的调试与高级选项（若存在相应接口）。"""
        self.init_players()
        ap = self.auto_player
        if not ap:
            return
        try:
            if debug is not None and hasattr(ap, 'set_debug'):
                ap.set_debug(bool(debug))
        except Exception:
            pass
        try:
            if options and hasattr(ap, 'set_options'):
                ap.set_options(**options)
        except Exception:
            pass

    def set_auto_callbacks(self,
                           on_start: Optional[Callable[[], None]] = None,
                           on_pause: Optional[Callable[[], None]] = None,
                           on_resume: Optional[Callable[[], None]] = None,
                           on_stop: Optional[Callable[[], None]] = None,
                           on_progress: Optional[Callable[[float], None]] = None,
                           on_complete: Optional[Callable[[], None]] = None,
                           on_error: Optional[Callable[[str], None]] = None) -> None:
        """下发回调（若 AutoPlayer 支持 set_callbacks）。"""
        self.init_players()
        ap = self.auto_player
        if not ap:
            return
        try:
            if hasattr(ap, 'set_callbacks'):
                ap.set_callbacks(
                    on_start=on_start,
                    on_pause=on_pause,
                    on_resume=on_resume,
                    on_stop=on_stop,
                    on_progress=on_progress,
                    on_complete=on_complete,
                    on_error=on_error,
                )
        except Exception:
            pass

    def start_auto_play_from_path(self,
                                  file_path: str,
                                  *,
                                  tempo: float = 1.0,
                                  key_mapping: Any | None = None,
                                  strategy_name: str = 'strategy_21key',
                                  use_analyzed: bool = False,
                                  analyzed_notes: Any | None = None) -> bool:
        """从路径或已分析事件启动自动演奏。"""
        self.init_players()
        ap = self.auto_player
        if not ap:
            return False
        
        # 添加调试日志
        if self.logger:
            try:
                self.logger.log(
                    f"PlaybackService启动播放: tempo={tempo}, use_analyzed={use_analyzed}, analysis_settings={self.analysis_settings}",
                    "DEBUG"
                )
            except Exception:
                self.logger.log(f"PlaybackService启动播放: tempo={tempo}, use_analyzed={use_analyzed}", "DEBUG")
        
        try:
            # 统一管线：优先使用传入的已解析事件，否则自行解析（pretty_midi）
            if use_analyzed and analyzed_notes is not None and hasattr(ap, 'start_auto_play_midi_events'):
                # 即便传入已解析事件，也必须走统一的“过滤+自动移调”前置处理
                notes_in = list(analyzed_notes or [])
                notes2 = self._apply_pre_filters_and_transpose(notes_in)
                if self.logger:
                    stats = self.get_last_analysis_stats()
                    self.logger.log(
                        f"使用已解析事件播放，原事件数: {len(notes_in)}, 过滤/移调后: {len(notes2)}, k={stats.get('k')}, white_rate={stats.get('white_rate')}",
                        "DEBUG"
                    )
                if not notes2:
                    return False
                ok = bool(ap.start_auto_play_midi_events(notes2, tempo=tempo, key_mapping=key_mapping, strategy_name=strategy_name))
                try:
                    ok = ok and bool(getattr(ap, 'is_playing', False))
                except Exception:
                    pass
                if self.logger and not ok:
                    self.logger.log("[DEBUG] AutoPlayer 启动失败（已解析事件路径）", "ERROR")
                return ok

            # 自行解析（pretty_midi）并走事件入口（避免任何 mido 直通路径）
            res = analyzer.parse_midi(file_path)
            if not isinstance(res, dict) or not res.get('ok'):
                if self.logger:
                    self.logger.log(f"解析MIDI失败: {res.get('error') if isinstance(res, dict) else 'unknown'}", "ERROR")
                return False
            notes = res.get('notes') or []
            # 解析来源与时序信息输出（用于诊断速度/时间问题）
            try:
                src = res.get('source')
                total = int(res.get('total_notes') or len(notes))
                end_time = float(res.get('end_time') or 0.0)
                init_t = float(res.get('initial_tempo') or 0.0)
                self.logger.log(
                    f"[DEBUG] 解析完成: source={src}, total_notes={total}, end_time={end_time:.3f}s, initial_tempo={init_t}",
                    "DEBUG"
                )
            except Exception:
                pass
            if not notes:
                if self.logger:
                    self.logger.log("解析到的音符为空", "ERROR")
                return False
            # 应用短音过滤与自动移调
            notes2 = self._apply_pre_filters_and_transpose(notes)
            if self.logger:
                self.logger.log(
                    f"[DEBUG] 解析得到事件数: {len(notes)}，过滤/移调后: {len(notes2)}，准备进入统一事件播放入口 (strategy={strategy_name}, tempo={tempo})",
                    "DEBUG"
                )
            if not notes2:
                if self.logger:
                    self.logger.log("预处理后事件为空，终止播放", "ERROR")
                return False
            ok = bool(ap.start_auto_play_midi_events(notes2, tempo=tempo, key_mapping=key_mapping, strategy_name=strategy_name))
            try:
                ok = ok and bool(getattr(ap, 'is_playing', False))
            except Exception:
                pass
            if self.logger and not ok:
                self.logger.log("[DEBUG] AutoPlayer 启动失败（文件解析路径）", "ERROR")
            return ok
        except Exception as e:
            if self.logger:
                self.logger.log(f"播放启动失败: {e}", "ERROR")
            return False
        return False
