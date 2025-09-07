# -*- coding: utf-8 -*-
"""
PlaybackService: 播放相关服务（占位）
- 后续将把 app.py 中与 MIDI/自动演奏相关的逻辑迁移至此
- 当前提供最小接口占位，不在应用中直接调用
"""
from typing import Any, Callable, Optional, List, Dict
try:
    from meowauto.net.clock import ClockProvider, LocalClock, NetworkClockProvider
except Exception:
    ClockProvider = Any  # 回退占位
    LocalClock = None
    NetworkClockProvider = None

class PlaybackService:
    def __init__(self, logger: Optional[Any] = None, clock_provider: Optional[Any] = None):
        self.logger = logger
        self.midi_player = None
        self.auto_player = None
        # 默认使用本地时钟（若可用）
        try:
            self.clock_provider = clock_provider or (LocalClock() if LocalClock else None)
        except Exception:
            self.clock_provider = clock_provider or None

    def init_players(self) -> None:
        """延迟初始化播放器（占位）。"""
        try:
            if self.midi_player is None:
                from meowauto.playback import MidiPlayer
                from meowauto.core import Logger
                self.midi_player = MidiPlayer(self.logger or Logger())
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

    # ===== 时钟注入 =====
    def set_clock_provider(self, provider: Any) -> None:
        """设置/替换 ClockProvider，并尝试下发给 AutoPlayer（若支持）。"""
        self.clock_provider = provider
        try:
            if self.auto_player and hasattr(self.auto_player, 'set_clock_provider'):
                self.auto_player.set_clock_provider(provider)
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
            self.logger.log(f"PlaybackService启动播放: tempo={tempo}, use_analyzed={use_analyzed}", "DEBUG")
        
        try:
            if use_analyzed and analyzed_notes is not None and hasattr(ap, 'start_auto_play_midi_events'):
                if self.logger:
                    self.logger.log(f"使用已解析事件播放，事件数: {len(analyzed_notes) if analyzed_notes else 0}", "DEBUG")
                return bool(ap.start_auto_play_midi_events(analyzed_notes, tempo=tempo, key_mapping=key_mapping, strategy_name=strategy_name))
            if hasattr(ap, 'start_auto_play_midi'):
                if self.logger:
                    self.logger.log(f"从MIDI文件播放: {file_path}", "DEBUG")
                return bool(ap.start_auto_play_midi(file_path, tempo=tempo, key_mapping=key_mapping, strategy_name=strategy_name))
        except Exception as e:
            if self.logger:
                self.logger.log(f"播放启动失败: {e}", "ERROR")
            return False
        return False
