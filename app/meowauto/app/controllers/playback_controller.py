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
import time
import os
try:
    from tkinter import messagebox as mb
except Exception:
    mb = None

try:
    import mido
except Exception:
    mido = None  # 解析失败时返回空分部

from meowauto.midi.partitioner import TrackChannelPartitioner, PartSection


class PlaybackController:
    def __init__(self, app: Any, playback_service: Any | None = None) -> None:
        self.app = app
        self.playback_service = playback_service
        # 定时与对时：状态
        self._last_schedule_id: str | None = None

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

    # —— 新：TimingService 桥接 ——
    def _ensure_timing_service(self):
        try:
            ps = self.playback_service
            if not ps:
                return None
            ts = getattr(ps, 'get_timing_service', None)
            cur = ts() if callable(ts) else None
            if cur:
                return cur
            # 创建并注入
            try:
                from meowauto.app.services.timing_service import TimingService
            except Exception:
                return None
            t = TimingService(getattr(ps, 'logger', None), tk_root=getattr(self.app, 'root', None))
            if hasattr(ps, 'set_timing_service'):
                ps.set_timing_service(t)
            # 同步时钟到 AutoPlayer
            try:
                cp = getattr(t, 'clock', None)
                if cp is not None and hasattr(ps, 'set_clock_provider'):
                    ps.set_clock_provider(cp)
            except Exception:
                pass
            return t
        except Exception:
            return None

    def _timing_enable_network_clock(self):
        ts = self._ensure_timing_service()
        if not ts:
            return
        # 使用UI传入的服务器（可选），否则默认
        servers = None
        try:
            sv = getattr(self.app, 'timing_servers_var', None)
            if sv is not None:
                raw = sv.get().strip()
                if raw:
                    servers = [s.strip() for s in raw.split(',') if s.strip()]
        except Exception:
            servers = None
        ok = bool(ts.configure_ntp(servers=servers))
        st = ts.get_status()
        off = st.get('offset_ms'); rtt = st.get('rtt_ms')
        try:
            self.app._log_message(f"公网对时{'成功' if ok else '失败'} offset={off}ms rtt={rtt}ms")
            self.app.ui_manager.set_status(f"公网对时{'成功' if ok else '失败'} offset={off}ms rtt={rtt}ms")
        except Exception:
            pass

    def _timing_sync_now(self):
        ts = self._ensure_timing_service()
        if not ts:
            return
        st = ts.sync_now()
        try:
            self.app._log_message(f"手动对时{'成功' if st.get('ok') else '失败'} provider={st.get('provider')} offset={st.get('offset_ms')}ms rtt={st.get('rtt_ms')}ms")
            self.app.ui_manager.set_status(f"手动对时{'成功' if st.get('ok') else '失败'}")
        except Exception:
            pass

    def _timing_use_local(self):
        ts = self._ensure_timing_service()
        if not ts:
            return
        ts.use_local()
        try:
            self.app._log_message("已切回本地时钟")
            self.app.ui_manager.set_status("已切回本地时钟")
        except Exception:
            pass

    def _timing_apply_servers(self):
        """从UI读取服务器列表并应用（启用NTP）。"""
        ts = self._ensure_timing_service()
        if not ts:
            return
        servers = []
        try:
            raw = getattr(self.app, 'timing_servers_var', None)
            if raw is not None:
                s = raw.get().strip()
            else:
                s = getattr(self, 'timing_servers_var', None).get().strip() if hasattr(self, 'timing_servers_var') else ''
            if s:
                servers = [x.strip() for x in s.split(',') if x.strip()]
        except Exception:
            servers = []
        ok = False
        if servers:
            ok = bool(ts.set_ntp_servers(servers))
        else:
            ok = bool(ts.configure_ntp())
        try:
            self.app._log_message(f"应用NTP服务器{'成功' if ok else '失败'}: {servers if servers else '[默认]'}")
        except Exception:
            pass

    def _timing_toggle_ntp(self, enable: bool):
        ts = self._ensure_timing_service()
        if not ts:
            return
        if enable:
            # 尝试使用当前输入服务器启用
            self._timing_apply_servers()
        else:
            self._timing_use_local()

    def _timing_schedule_for_current_instrument(self):
        ts = self._ensure_timing_service()
        if not ts:
            return
        # 读取 UI 变量（由 playback_controls 注入）
        try:
            hh = int(getattr(self.app, 'timing_hh_var').get()) if hasattr(self.app, 'timing_hh_var') else int(getattr(self, 'timing_hh_var').get())
            mm = int(getattr(self.app, 'timing_mm_var').get()) if hasattr(self.app, 'timing_mm_var') else int(getattr(self, 'timing_mm_var').get())
            ss = int(getattr(self.app, 'timing_ss_var').get()) if hasattr(self.app, 'timing_ss_var') else int(getattr(self, 'timing_ss_var').get())
            ms = int(getattr(self.app, 'timing_ms_var').get()) if hasattr(self.app, 'timing_ms_var') else int(getattr(self, 'timing_ms_var').get())
        except Exception:
            return
        try:
            manual = int(getattr(self.app, 'timing_manual_ms_var').get()) if hasattr(self.app, 'timing_manual_ms_var') else int(getattr(self, 'timing_manual_ms_var').get())
        except Exception:
            manual = 0
        try:
            ts.set_manual_compensation(manual)
        except Exception:
            pass

        inst = getattr(self.app, 'current_instrument', None) or getattr(self, 'current_instrument', None) or '电子琴'
        tempo = 1.0
        try:
            tempo = float(getattr(self.app, 'tempo_var').get()) if hasattr(self.app, 'tempo_var') else float(getattr(self, 'tempo_var').get())
        except Exception:
            tempo = 1.0

        def play_func(instrument: str) -> bool:
            ps = self.playback_service
            if not ps:
                return False
            return bool(ps.play_for_instrument(instrument, tempo=tempo, use_analyzed=True, controller_ref=self.app))

        sid = ts.schedule_play(inst, (hh, mm, ss, ms), play_func=play_func, tempo=tempo, use_analyzed=True)
        st = ts.get_status()
        if not sid:
            # 失败：多半为目标时间已过
            try:
                self.app._log_message(f"创建计划失败：目标时间已过或参数非法 {hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}", "ERROR")
                if hasattr(self.app, 'timing_status_var'):
                    self.app.timing_status_var.set("创建计划失败：检查目标时间")
                # 弹窗提示
                if mb:
                    mb.showerror("创建计划失败", f"目标时间已过或参数非法:\n{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}")
            except Exception:
                pass
            return
        self._last_schedule_id = sid
        try:
            self.app._log_message(f"已创建单次计划 id={sid} {hh:02d}:{mm:02d}:{ss:02d}.{ms:03d} provider={st.get('provider')} offset={st.get('offset_ms')}ms rtt={st.get('rtt_ms')}ms manual={st.get('manual_compensation_ms')}ms")
        except Exception:
            pass

    def _timing_cancel_schedule(self):
        ts = self._ensure_timing_service()
        if not ts or not self._last_schedule_id:
            return
        ok = bool(ts.cancel_schedule(self._last_schedule_id))
        try:
            self.app._log_message(f"取消计划 {'成功' if ok else '失败'} id={self._last_schedule_id}")
        except Exception:
            pass
        self._last_schedule_id = None

    def _timing_test_now(self):
        # 立即按当前设置触发一次
        inst = getattr(self.app, 'current_instrument', None) or '电子琴'
        tempo = 1.0
        try:
            tempo = float(getattr(self.app, 'tempo_var').get()) if hasattr(self.app, 'tempo_var') else 1.0
        except Exception:
            tempo = 1.0
        ps = self.playback_service
        if not ps:
            return
        ps.play_for_instrument(inst, tempo=tempo, use_analyzed=True, controller_ref=self.app)

    def _timing_get_ui_status(self) -> dict:
        """提供给UI查询当前对时/延迟链路状态与最近计划触发时间。"""
        ts = self._ensure_timing_service()
        if not ts:
            return {}
        st = ts.get_status() or {}
        # 最近计划
        sched = None
        if self._last_schedule_id:
            try:
                sched = ts.get_schedule(self._last_schedule_id)
            except Exception:
                sched = None
        # 组装字符串
        next_str = ""
        remaining_ms = None
        if sched and sched.get('schedule_unix'):
            try:
                su = float(sched['schedule_unix'])
                lt = time.localtime(su)
                next_str = time.strftime("%Y-%m-%d %H:%M:%S", lt) + f".{int((su - int(su))*1000):03d}"
                # 倒计时
                now_s = time.time()
                remaining_ms = max(0.0, (su - now_s) * 1000.0)
            except Exception:
                next_str = ""
        return {
            'provider': st.get('provider'),
            'sys_delta_ms': st.get('sys_delta_ms'),
            'rtt_ms': st.get('rtt_ms'),
            'manual_compensation_ms': st.get('manual_compensation_ms'),
            'auto_latency_ms': st.get('auto_latency_ms'),
            'net_shift_ms': st.get('net_shift_ms'),
            'local_chain_ms': st.get('local_chain_ms'),
            'next_fire': next_str,
            'remaining_ms': remaining_ms,
        }

    def _timing_set_resync_settings(self, interval_sec: float | int | None = None, adjust_threshold_ms: float | int | None = None):
        ts = self._ensure_timing_service()
        if not ts:
            return
        try:
            if hasattr(ts, 'set_resync_settings'):
                ts.set_resync_settings(interval_sec=interval_sec, adjust_threshold_ms=adjust_threshold_ms)
        except Exception:
            pass

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
        - 处理多轨；使用“全局 tempo 映射表”进行 tick→秒 换算，确保所有轨道对齐。
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
        # 1) 预扫描：收集所有消息的绝对 tick，用于构建全局 tempo 映射表
        msgs: List[Dict[str, Any]] = []
        for ti, track in enumerate(mid.tracks):
            t = 0
            for msg in track:
                # 先累积 delta，再记录本条消息的绝对 tick
                t += int(getattr(msg, 'time', 0) or 0)
                msgs.append({'msg': msg, 'tick': t, 'track': ti})
        msgs.sort(key=lambda x: x['tick'])

        ticks_per_beat = int(getattr(mid, 'ticks_per_beat', 480) or 480)
        is_smpte = bool(ticks_per_beat < 0)
        default_tempo = 500000  # 120 BPM

        # 2) 构建 tick→秒 转换
        smpte_seconds_per_tick = 0.0
        if not is_smpte:
            tempo_changes: List[Dict[str, Any]] = [{'tick': 0, 'tempo': default_tempo, 'acc_seconds': 0.0}]
            last_t = default_tempo
            for it in msgs:
                m = it['msg']
                if getattr(m, 'type', None) == 'set_tempo':
                    tk = int(it['tick'])
                    if not tempo_changes or tk != tempo_changes[-1]['tick'] or getattr(m, 'tempo', last_t) != last_t:
                        tempo_changes.append({'tick': tk, 'tempo': int(getattr(m, 'tempo', last_t) or last_t), 'acc_seconds': 0.0})
                        last_t = int(getattr(m, 'tempo', last_t) or last_t)
            for i in range(1, len(tempo_changes)):
                prev = tempo_changes[i-1]
                cur = tempo_changes[i]
                dt = max(0, int(cur['tick']) - int(prev['tick']))
                spt = (float(prev['tempo']) / 1_000_000.0) / max(1, abs(ticks_per_beat))
                cur['acc_seconds'] = float(prev['acc_seconds']) + dt * spt

            def tick_to_seconds(tp: int) -> float:
                idx = 0
                for j in range(len(tempo_changes)):
                    if int(tempo_changes[j]['tick']) <= int(tp):
                        idx = j
                    else:
                        break
                base = tempo_changes[idx]
                spt = (float(base['tempo']) / 1_000_000.0) / max(1, abs(ticks_per_beat))
                return float(base['acc_seconds']) + (int(tp) - int(base['tick'])) * spt
        else:
            # SMPTE 时间基：根据分辨率计算固定“秒/每tick”
            div = int(ticks_per_beat)
            hi = (div >> 8) & 0xFF
            lo = div & 0xFF
            if hi >= 128:
                hi -= 256
            fps = abs(hi) if hi != 0 else 30
            tpf = lo if lo > 0 else 80
            smpte_seconds_per_tick = 1.0 / (float(fps) * float(tpf))

            def tick_to_seconds(tp: int) -> float:
                return float(int(tp)) * float(smpte_seconds_per_tick)

        # 3) 遍历生成 note_on/note_off 事件（用全局 tick_to_seconds 换算）
        #    同时记录 program_change 以携带 program 元信息
        last_prog_by_track_ch: Dict[tuple, int] = {}
        on_stack: Dict[tuple, List[Dict[str, Any]]] = {}
        for it in msgs:
            m = it['msg']
            tk = int(it['tick'])
            ti = int(it['track'])
            tpe = getattr(m, 'type', None)
            if tpe == 'program_change':
                ch = int(getattr(m, 'channel', 0) or 0)
                last_prog_by_track_ch[(ti, ch)] = int(getattr(m, 'program', 0) or 0)
                continue
            if tpe == 'note_on' and int(getattr(m, 'velocity', 0) or 0) > 0:
                ch = int(getattr(m, 'channel', 0) or 0)
                note = int(getattr(m, 'note', 0) or 0)
                on_stack.setdefault((ti, ch, note), []).append({
                    'tick': tk,
                    'velocity': int(getattr(m, 'velocity', 0) or 0),
                    'program': last_prog_by_track_ch.get((ti, ch)),
                })
            elif tpe in ('note_off', 'note_on'):
                if tpe == 'note_on' and int(getattr(m, 'velocity', 0) or 0) > 0:
                    continue
                ch = int(getattr(m, 'channel', 0) or 0)
                note = int(getattr(m, 'note', 0) or 0)
                key = (ti, ch, note)
                stack = on_stack.get(key)
                if stack:
                    st_rec = stack.pop(0)
                    st = float(tick_to_seconds(int(st_rec['tick'])))
                    et = float(tick_to_seconds(tk))
                    prog = st_rec.get('program')
                    events.append({'type': 'note_on',  'start_time': st, 'note': note, 'channel': ch, 'track': ti, 'program': prog, 'instrument_name': '', 'velocity': st_rec.get('velocity', 0)})
                    events.append({'type': 'note_off', 'start_time': et, 'note': note, 'channel': ch, 'track': ti, 'program': prog, 'instrument_name': '', 'velocity': 0})

        # 4) 清理未配对：给固定时值（0.2s）
        for (ti, ch, note), stack in on_stack.items():
            for st_rec in stack:
                st = float(tick_to_seconds(int(st_rec['tick'])))
                et = st + 0.2
                prog = st_rec.get('program')
                events.append({'type': 'note_on',  'start_time': st, 'note': note, 'channel': ch, 'track': ti, 'program': prog, 'instrument_name': '', 'velocity': st_rec.get('velocity', 0)})
                events.append({'type': 'note_off', 'start_time': et, 'note': note, 'channel': ch, 'track': ti, 'program': prog, 'instrument_name': '', 'velocity': 0})

        # 5) 排序（同刻先 off 后 on）
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
