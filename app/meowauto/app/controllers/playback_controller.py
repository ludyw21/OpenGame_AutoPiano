# -*- coding: utf-8 -*-
"""
PlaybackController（占位）：协调 UI 与 PlaybackService

职责分离目标：
- 从 app.py 迁出播放相关的交互控制（按钮切换/倒计时/状态更新）
- 通过服务层（PlaybackService）完成业务动作

当前阶段：
- 仅做占位与轻度封装，不改变现有行为
- 方法内部暂时回调 app.py 现有实现，后续逐步将逻辑迁移进来
"""
from __future__ import annotations
from typing import Optional, Any, List, Dict
import os

try:
    import mido
except Exception:
    mido = None  # 解析失败时返回空分部

from meowauto.midi.partitioner import TrackChannelPartitioner, PartSection


class PlaybackController:
    def __init__(self, app: Any, playback_service: Any | None = None) -> None:
        self.app = app
        self.playback_service = playback_service

    # —— UI 交互封装（占位） ——
    def toggle_auto_play(self) -> None:
        """切换自动弹琴：移植自 app._toggle_auto_play 的逻辑。"""
        app = self.app
        # 若正在倒计时，视为取消
        if getattr(app, '_counting_down', False):
            try:
                if hasattr(app, 'root') and getattr(app, '_countdown_job', None):
                    app.root.after_cancel(app._countdown_job)
            except Exception:
                pass
            app._counting_down = False
            app._countdown_job = None
            app.ui_manager.set_status("已取消倒计时")
            app._log_message("已取消倒计时")
            app.auto_play_button.configure(text="自动弹琴")
            return

        if app.auto_play_button.cget("text") == "自动弹琴":
            # 开始自动弹琴（带倒计时）
            secs = 0
            try:
                secs = int(app.countdown_seconds_var.get()) if hasattr(app, 'countdown_seconds_var') else 0
            except Exception:
                secs = 0
            if secs <= 0:
                app._start_auto_play()
                return
            # 执行倒计时
            app._counting_down = True
            app.auto_play_button.configure(text=f"倒计时{secs}s(点击取消)")
            app.pause_button.configure(state="disabled")
            app.ui_manager.set_status(f"{secs} 秒后开始自动弹琴...")

            def tick(remaining):
                if not getattr(app, '_counting_down', False):
                    return
                if remaining <= 0:
                    app._counting_down = False
                    app._countdown_job = None
                    app.auto_play_button.configure(text="自动弹琴")
                    # 开始
                    app._start_auto_play()
                    return
                try:
                    app.auto_play_button.configure(text=f"倒计时{remaining}s(点击取消)")
                    app.ui_manager.set_status(f"{remaining} 秒后开始自动弹琴...")
                except Exception:
                    pass
                if hasattr(app, 'root'):
                    app._countdown_job = app.root.after(1000, lambda: tick(remaining - 1))
                else:
                    # 退化处理：无 root.after 时直接开始
                    app._counting_down = False
                    app._start_auto_play()
            tick(secs)
        else:
            # 停止自动弹琴
            app._stop_auto_play()

    def toggle_pause(self) -> None:
        """切换暂停/恢复：移植自 app._toggle_pause 的逻辑。"""
        app = self.app
        # 检查是否有MIDI播放器在播放
        if hasattr(app, 'midi_player') and app.midi_player and app.midi_player.is_playing:
            if app.midi_player.is_paused:
                # 恢复MIDI播放
                app._resume_midi_play()
            else:
                # 暂停MIDI播放
                app._pause_midi_play()
            return

        # 检查是否有自动演奏器在播放
        if hasattr(app, 'auto_player') and app.auto_player and app.auto_player.is_playing:
            if app.auto_player.is_paused:
                # 恢复自动演奏
                app._resume_auto_play()
            else:
                # 暂停自动演奏
                app._pause_auto_play()
            return

        # 没有正在播放的内容
        app._log_message("没有正在播放的内容", "WARNING")

    # —— 时钟控制封装 ——
    def enable_network_clock(self, servers: list[str] | None = None, timeout: float | None = None, max_tries: int | None = None) -> bool:
        app = self.app
        ok = False
        # 读取配置默认值（若未显式传入）
        try:
            if servers is None or timeout is None or max_tries is None:
                try:
                    from meowauto.core.config import ConfigManager
                    cfg = ConfigManager()
                    if servers is None:
                        servers = cfg.get('ntp.servers') or None
                    if timeout is None:
                        timeout = cfg.get('ntp.timeout', 1.5)
                    if max_tries is None:
                        max_tries = cfg.get('ntp.max_tries', 5)
                except Exception:
                    # 回退默认
                    servers = servers or [
                        "ntp.ntsc.ac.cn",
                        "time.apple.com",
                        "time1.cloud.tencent.com",
                        "time2.cloud.tencent.com",
                        "time3.cloud.tencent.com",
                        "time4.cloud.tencent.com",
                        "time5.cloud.tencent.com",
                        "pool.ntp.org",
                    ]
                    timeout = 1.5 if timeout is None else timeout
                    max_tries = 5 if max_tries is None else max_tries
        except Exception:
            pass
        try:
            if self.playback_service and hasattr(self.playback_service, 'use_network_clock'):
                ok = bool(self.playback_service.use_network_clock(servers=servers, timeout=timeout, max_tries=max_tries))
        except Exception:
            ok = False
        try:
            # 偏移与时间展示（若可用）
            off_ms_txt = ""
            try:
                cp = getattr(self.playback_service, 'clock_provider', None)
                drift = getattr(cp, 'last_sys_drift_ms', None)
                if drift is None:
                    drift = getattr(cp, 'last_offset_ms', None)
                if isinstance(drift, (int, float)):
                    # 阈值保护：若绝对值超过 5e6 ms (~1.4h) 视为异常，不展示具体数值
                    if abs(drift) < 5_000_000:
                        off_ms_txt = f"，偏移 {drift:.1f} ms"
                    else:
                        off_ms_txt = "，偏移异常，已采用网络时钟"
            except Exception:
                pass
            app._log_message(f"公网对时{'成功' if ok else '失败'}{off_ms_txt}")
            app.ui_manager.set_status(("已启用公网对时" + off_ms_txt) if ok else "公网对时失败，已回退本地时钟")
        except Exception:
            pass
        return ok

    def sync_network_clock(self) -> bool:
        app = self.app
        ok = False
        try:
            cp = getattr(self.playback_service, 'clock_provider', None)
            if cp and hasattr(cp, 'sync'):
                ok = bool(cp.sync())
            else:
                if self.playback_service and hasattr(self.playback_service, 'use_network_clock'):
                    ok = bool(self.playback_service.use_network_clock())
        except Exception:
            ok = False
        try:
            off_ms_txt = ""
            try:
                cp = getattr(self.playback_service, 'clock_provider', None)
                drift = getattr(cp, 'last_sys_drift_ms', None)
                if drift is None:
                    drift = getattr(cp, 'last_offset_ms', None)
                if isinstance(drift, (int, float)):
                    if abs(drift) < 5_000_000:
                        off_ms_txt = f"，偏移 {drift:.1f} ms"
                    else:
                        off_ms_txt = "，偏移异常，已采用网络时钟"
            except Exception:
                pass
            app._log_message(f"NTP 手动同步{'成功' if ok else '失败'}{off_ms_txt}")
            app.ui_manager.set_status(("NTP 手动同步成功" + off_ms_txt) if ok else "NTP 手动同步失败")
        except Exception:
            pass
        return ok

    def use_local_clock(self) -> None:
        app = self.app
        try:
            if self.playback_service and hasattr(self.playback_service, 'use_local_clock'):
                self.playback_service.use_local_clock()
            app._log_message("已切回本地时钟")
            app.ui_manager.set_status("已切回本地时钟")
        except Exception as e:
            try:
                app._log_message(f"切回本地时钟失败: {e}", "ERROR")
            except Exception:
                pass

    # —— 服务直达入口（预留） ——
    def start_auto_from_file(self, file_path: str) -> bool:
        """通过服务层直接启动自动演奏（预留）。"""
        try:
            if self.playback_service and hasattr(self.playback_service, 'start_auto_play_from_path'):
                # 仅传必要参数；app 侧其他选项/回调仍由现有流程负责
                return bool(self.playback_service.start_auto_play_from_path(file_path))
        except Exception:
            return False

    # —— 按轨/通道分离（提供给大合奏/导出） ——
    def split_midi_by_track_channel(self, file_path: str) -> Dict[str, PartSection]:
        """读取 MIDI 文件，按 轨/通道/音色 分离事件。
        返回 {part_name: PartSection}，part_name 形如 track{t}_ch{c}_prog{p}_{name}
        """
        app = self.app
        try:
            if mido is None:
                try:
                    app._log_message("mido 不可用，无法进行按轨/通道分离", "ERROR")
                except Exception:
                    pass
                return {}
            events = self._build_note_events_with_track(file_path)
            part = TrackChannelPartitioner(include_meta=True)
            parts = part.split(events)
            try:
                app._log_message(f"按轨/通道分离完成，共 {len(parts)} 个分部")
            except Exception:
                pass
            return parts
        except Exception as e:
            try:
                app._log_message(f"按轨/通道分离失败: {e}", "ERROR")
            except Exception:
                pass
            return {}

    def _build_note_events_with_track(self, file_path: str) -> List[Dict[str, Any]]:
        """将 MIDI 转换为含 track/channel/program 的 note_on/note_off 事件序列（秒）。
        - 处理多轨；每轨维护 tempo；使用 mido.tick2second 做换算。
        - program 记录最近一次 program_change 的值；无则为 None。
        - instrument_name 暂留空字符串，后续可按 GM 名称映射。
        """
        if mido is None:
            return []
        try:
            mid = mido.MidiFile(file_path)
        except Exception:
            return []
        events: List[Dict[str, Any]] = []
        for ti, track in enumerate(mid.tracks):
            t_ticks = 0
            tempo = 500000  # 120bpm 默认
            last_prog_by_ch: Dict[int, int] = {}
            # 按 (channel,note) 记录起点 tick
            on_stack: Dict[tuple, List[Dict[str, Any]]] = {}
            for msg in track:
                t_ticks += int(getattr(msg, 'time', 0) or 0)
                if msg.type == 'set_tempo':
                    tempo = int(getattr(msg, 'tempo', tempo) or tempo)
                elif msg.type == 'program_change':
                    ch = int(getattr(msg, 'channel', 0) or 0)
                    last_prog_by_ch[ch] = int(getattr(msg, 'program', 0) or 0)
                elif msg.type == 'note_on' and int(getattr(msg, 'velocity', 0) or 0) > 0:
                    ch = int(getattr(msg, 'channel', 0) or 0)
                    note = int(getattr(msg, 'note', 0) or 0)
                    on_stack.setdefault((ch, note), []).append({
                        'tick': t_ticks,
                        'velocity': int(getattr(msg, 'velocity', 0) or 0),
                        'program': last_prog_by_ch.get(ch),
                    })
                elif msg.type in ('note_off', 'note_on'):
                    # note_on with velocity==0 作为 note_off
                    if msg.type == 'note_on' and int(getattr(msg, 'velocity', 0) or 0) > 0:
                        continue
                    ch = int(getattr(msg, 'channel', 0) or 0)
                    note = int(getattr(msg, 'note', 0) or 0)
                    key = (ch, note)
                    if key in on_stack and on_stack[key]:
                        start = on_stack[key].pop(0)
                        st = float(mido.tick2second(int(start['tick']), mid.ticks_per_beat, tempo))
                        et = float(mido.tick2second(int(t_ticks), mid.ticks_per_beat, tempo))
                        prog = start.get('program')
                        # 生成 note_on / note_off 两个事件，便于分部器处理
                        events.append({
                            'type': 'note_on',
                            'start_time': st,
                            'note': note,
                            'channel': ch,
                            'track': ti,
                            'program': prog,
                            'instrument_name': '',
                            'velocity': start.get('velocity', 0),
                        })
                        events.append({
                            'type': 'note_off',
                            'start_time': et,
                            'note': note,
                            'channel': ch,
                            'track': ti,
                            'program': prog,
                            'instrument_name': '',
                            'velocity': 0,
                        })
            # 清理未配对音符：以 0.2s 时值收尾
            for (ch, note), stack in on_stack.items():
                for start in stack:
                    st = float(mido.tick2second(int(start['tick']), mid.ticks_per_beat, tempo))
                    et = st + 0.2
                    prog = start.get('program')
                    events.append({
                        'type': 'note_on',
                        'start_time': st,
                        'note': note,
                        'channel': ch,
                        'track': ti,
                        'program': prog,
                        'instrument_name': '',
                        'velocity': start.get('velocity', 0),
                    })
                    events.append({
                        'type': 'note_off',
                        'start_time': et,
                        'note': note,
                        'channel': ch,
                        'track': ti,
                        'program': prog,
                        'instrument_name': '',
                        'velocity': 0,
                    })
        # 按时间与类型排序（release 在 press 之前）
        type_rank = {'note_off': 0, 'note_on': 1}
        events.sort(key=lambda x: (float(x.get('start_time', 0.0)), type_rank.get(x.get('type'), 2)))
        return events

    # —— 分部导出为独立 MIDI 文件 ——
    def export_partitions_to_midis(self, parts: Dict[str, PartSection], out_dir: str, *, tempo_bpm: int = 120) -> List[str]:
        """将 split 结果导出为多个 .mid 文件，返回写出的文件路径列表。
        说明：
        - 使用固定拍速 tempo_bpm（默认120），所有事件时间基于秒换算为 ticks。
        - 每个分部一个 track；事件顺序按时间并保证 note_off 在同一时间点先于 note_on。
        - 若事件缺失 channel/velocity，使用安全兜底。
        """
        if mido is None or not isinstance(parts, dict) or not parts:
            try:
                self.app._log_message("mido 不可用或无分部数据，导出跳过", "WARN")
            except Exception:
                pass
            return []
        os.makedirs(out_dir, exist_ok=True)
        written: List[str] = []
        tpq = 480
        tempo = getattr(mido, 'bpm2tempo', lambda bpm: int(60_000_000 / max(1, bpm)))(int(tempo_bpm))

        for name, section in parts.items():
            try:
                mf = mido.MidiFile(ticks_per_beat=tpq)
                tr = mido.MidiTrack()
                mf.tracks.append(tr)
                # 固定 tempo
                tr.append(mido.MetaMessage('set_tempo', tempo=int(tempo), time=0))

                evs = list(section.notes or [])
                # 排序：time + type（off 优先）
                type_rank = {'note_off': 0, 'note_on': 1}
                evs.sort(key=lambda x: (float(x.get('start_time', 0.0)), type_rank.get(x.get('type'), 2)))

                prev_tick = 0
                last_time_sec = 0.0
                for ev in evs:
                    t_sec = float(ev.get('start_time', 0.0))
                    # 换算为 ticks（相对于 0）
                    abs_ticks = int(mido.second2tick(max(0.0, t_sec), tpq, tempo))
                    delta = abs_ticks - prev_tick
                    prev_tick = abs_ticks
                    et = ev.get('type')
                    note = int(ev.get('note', 60) or 60)
                    ch = int(ev.get('channel', 0) or 0)
                    vel = int(ev.get('velocity', 64) or 64)
                    if et == 'note_on':
                        tr.append(mido.Message('note_on', note=note, velocity=max(0, min(127, vel)), channel=max(0, min(15, ch)), time=max(0, delta)))
                    elif et == 'note_off':
                        tr.append(mido.Message('note_off', note=note, velocity=0, channel=max(0, min(15, ch)), time=max(0, delta)))
                    last_time_sec = t_sec

                # 结尾留一个零时长 meta，保证文件完整
                tr.append(mido.MetaMessage('end_of_track', time=0))

                safe_name = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in (section.name or name))
                out_path = os.path.join(out_dir, f"{safe_name}.mid")
                mf.save(out_path)
                written.append(out_path)
            except Exception as e:
                try:
                    self.app._log_message(f"导出分部失败 {name}: {e}", "ERROR")
                except Exception:
                    pass
        try:
            self.app._log_message(f"分部导出完成：{len(written)} 个文件 -> {out_dir}")
        except Exception:
            pass
        return written

    def export_selected_as_single_midi(self, parts: Dict[str, PartSection], selected_names: List[str], out_path: str, *, tempo_bpm: int = 120) -> bool:
        """将所选分部合并到一个 MIDI 中（多 track），写入 out_path。
        - 固定拍速 tempo_bpm；各 track 保持各自事件序列（相同时间排序 off->on）。
        - 若 selected_names 为空则写入全部 parts。
        """
        if mido is None or not isinstance(parts, dict) or not parts:
            return False
        try:
            tpq = 480
            tempo = getattr(mido, 'bpm2tempo', lambda bpm: int(60_000_000 / max(1, bpm)))(int(tempo_bpm))
            mf = mido.MidiFile(ticks_per_beat=tpq)
            # 全局 tempo（第一个 track 写 tempo）
            first = True
            names = list(selected_names) if selected_names else list(parts.keys())
            for name in names:
                sec = parts.get(name)
                if not sec:
                    continue
                tr = mido.MidiTrack()
                mf.tracks.append(tr)
                if first:
                    tr.append(mido.MetaMessage('set_tempo', tempo=int(tempo), time=0))
                    first = False
                # 排序
                evs = list(sec.notes or [])
                type_rank = {'note_off': 0, 'note_on': 1}
                evs.sort(key=lambda x: (float(x.get('start_time', 0.0)), type_rank.get(x.get('type'), 2)))
                prev_tick = 0
                for ev in evs:
                    t_sec = float(ev.get('start_time', 0.0))
                    abs_ticks = int(mido.second2tick(max(0.0, t_sec), tpq, tempo))
                    delta = abs_ticks - prev_tick
                    prev_tick = abs_ticks
                    et = ev.get('type')
                    note = int(ev.get('note', 60) or 60)
                    ch = int(ev.get('channel', 0) or 0)
                    vel = int(ev.get('velocity', 64) or 64)
                    if et == 'note_on':
                        tr.append(mido.Message('note_on', note=note, velocity=max(0, min(127, vel)), channel=max(0, min(15, ch)), time=max(0, delta)))
                    elif et == 'note_off':
                        tr.append(mido.Message('note_off', note=note, velocity=0, channel=max(0, min(15, ch)), time=max(0, delta)))
                tr.append(mido.MetaMessage('end_of_track', time=0))
            mf.save(out_path)
            return True
        except Exception as e:
            try:
                self.app._log_message(f"合并导出失败: {e}", "ERROR")
            except Exception:
                pass
            return False

    def play_selected_parts(self, parts: Dict[str, PartSection], selected_names: List[str] | None = None,
                             *, tempo: float = 1.0, volume: float = 0.7, tempo_bpm_export: int = 120,
                             on_progress: Any | None = None,
                             mode: str | None = None,
                             my_role: str | None = None,
                             include_roles: List[str] | None = None,
                             role_overrides: Dict[str, str] | None = None) -> bool:
        """优先走 PlaybackService.play_parts 做实时路由播放；失败则回退到“临时MIDI合并+play_midi”。"""
        try:
            # 1) 优先：实时路由播放（无需生成临时文件）
            try:
                if self.playback_service and hasattr(self.playback_service, 'play_parts'):
                    # 独奏模式：仅包含我的角色
                    inc_roles = include_roles
                    if (mode or '').lower() == 'solo':
                        inc_roles = [my_role] if my_role else include_roles
                    ok = bool(self.playback_service.play_parts(
                        parts,
                        list(selected_names or []),
                        tempo=tempo,
                        on_progress=on_progress,
                        include_roles=inc_roles,
                        role_overrides=role_overrides or None,
                    ))
                    if ok:
                        return True
            except Exception:
                pass

            # 2) 回退：合并到临时 MIDI 再播放
            import tempfile, os, uuid
            if mido is None or not isinstance(parts, dict) or not parts:
                return False
            names = list(selected_names) if selected_names else list(parts.keys())
            tmp_path = os.path.join(tempfile.gettempdir(), f"meow_parts_live_{uuid.uuid4().hex[:8]}.mid")
            if not self.export_selected_as_single_midi(parts, names, tmp_path, tempo_bpm=tempo_bpm_export):
                return False
            if not os.path.exists(tmp_path):
                return False
            if not self.playback_service or not hasattr(self.playback_service, 'play_midi'):
                return False
            return bool(self.playback_service.play_midi(tmp_path, tempo=tempo, volume=volume, on_progress=on_progress))
        except Exception:
            return False

__all__ = [
    'PlaybackController',
]
