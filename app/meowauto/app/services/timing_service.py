# -*- coding: utf-8 -*-
"""
TimingService: 统一对时与单次定时调度服务
- 使用 NetworkClockProvider 提供的网络时钟与 schedule_at 能力
- 提供手动补偿（ms）与自动网络延迟估计（最小RTT）
- 单次计划：按 24 小时制 HH:MM:SS.mmm 计算下一个触发（若已过则拒绝/提示）
"""
from __future__ import annotations
from typing import Callable, Optional, Dict, Any, Tuple
import time
import uuid
import threading

try:
    from meowauto.net.clock import NetworkClockProvider, LocalClock
except Exception:
    NetworkClockProvider = None  # type: ignore
    LocalClock = None  # type: ignore

try:
    from meowauto.core import Logger
except Exception:
    class Logger:  # type: ignore
        def log(self, msg: str, level: str = "INFO"):
            print(f"[{level}] {msg}")

class TimingService:
    def __init__(self, logger: Optional[Any] = None, *, tk_root: Optional[object] = None):
        self.logger = logger or Logger()
        self.tk_root = tk_root
        # 启动时不进行网络对时，避免卡顿；默认先用本地时钟，待用户操作或创建计划时再进行对时
        self.clock = LocalClock() if LocalClock else None
        self.manual_compensation_ms: int = 0
        self.last_latency_ms: float = 0.0
        self.last_sys_delta_ms: float = 0.0  # NTP时间与系统time.time()的差值（毫秒）
        self.schedules: Dict[str, Dict[str, Any]] = {}
        # 自动对时与动态调整参数
        self.resync_interval_sec: float = 1.0
        self.adjust_threshold_ms: float = 5.0  # 计划触发时间变化大于该阈值则重置计时器
        self.ntp_enabled: bool = True
        self.ntp_servers: list[str] | None = None
        self._bg_resync_thread: Optional[threading.Thread] = None
        self._bg_resync_stop: bool = False
        self.last_local_chain_ms: float = 0.0
        self.include_ntp_delta: bool = True  # 是否将 NTP-本地偏差并入合成偏移与触发计算

        # 初始化时从配置加载默认设置（若可用），但不主动对时，避免启动卡顿
        try:
            from meowauto.core.config import ConfigManager  # type: ignore
            cfg = ConfigManager()
            en = cfg.get('ntp.enabled', True)
            servers = cfg.get('ntp.servers', [
                'ntp.ntsc.ac.cn',
                'time1.cloud.tencent.com',
                'time2.cloud.tencent.com',
                'time3.cloud.tencent.com',
            ])
            interval = float(cfg.get('ntp.resync_interval_sec', 1.0))
            threshold = float(cfg.get('ntp.adjust_threshold_ms', 5.0))
            self.include_ntp_delta = bool(cfg.get('ntp.include_delta', True))
            self.set_resync_settings(interval, threshold)
            self.ntp_enabled = bool(en)
            self.ntp_servers = list(servers)
            # 不调用 configure_ntp()，延迟到用户点击或创建计划时
        except Exception:
            # 回退到内置默认参数，但仍不主动联网
            self.ntp_enabled = True
            self.ntp_servers = [
                'ntp.ntsc.ac.cn',
                'time1.cloud.tencent.com',
                'time2.cloud.tencent.com',
                'time3.cloud.tencent.com',
            ]

    def _ensure_clock_initialized(self) -> None:
        """在需要时将 clock 切换为网络时钟（不在 __init__ 主动执行，避免启动卡顿）。"""
        try:
            if not self.ntp_enabled:
                return
            if NetworkClockProvider is None:
                return
            # 如果当前不是网络时钟，则按保存的服务器列表实例化
            if not self.clock or (LocalClock and isinstance(self.clock, LocalClock)):
                servers = self.ntp_servers or [
                    'ntp.ntsc.ac.cn',
                    'time1.cloud.tencent.com',
                    'time2.cloud.tencent.com',
                    'time3.cloud.tencent.com',
                ]
                self.clock = NetworkClockProvider(servers=servers, timeout=1.5, max_tries=3)
        except Exception:
            pass

    # —— 对时相关 ——
    def configure_ntp(self, servers: Optional[list] = None, timeout: float = 1.5, max_tries: int = 3) -> bool:
        try:
            if not NetworkClockProvider:
                return False
            self.ntp_enabled = True
            self.ntp_servers = list(servers) if servers else None
            self.clock = NetworkClockProvider(servers=servers, timeout=timeout, max_tries=max_tries)
            ok = bool(self.clock.sync())
            self.logger.log(f"[TIMING] 公网对时{'成功' if ok else '失败'}: offset_ms={getattr(self.clock, 'last_offset_ms', 0.0):.1f}, drift_ms={getattr(self.clock, 'last_sys_drift_ms', 0.0):.1f}")
            # 顺便测量一次网络延迟
            try:
                stat = self.clock.measure_latency()  # type: ignore[attr-defined]
                if stat and stat.get('ok'):
                    self.last_latency_ms = float(stat.get('rtt_ms') or 0.0)
                    self.last_sys_delta_ms = float(stat.get('sys_delta_ms') or 0.0)
                    self.logger.log(f"[TIMING] 网络延迟估计: rtt_min={self.last_latency_ms:.2f} ms, delta={self.last_sys_delta_ms:.2f} ms, server={stat.get('server')}", "DEBUG")
            except Exception:
                pass
            # 持久化设置（若可用）
            try:
                from meowauto.core.config import ConfigManager  # type: ignore
                cfg = ConfigManager()
                cfg.set('ntp.enabled', True)
                if self.ntp_servers:
                    cfg.set('ntp.servers', self.ntp_servers)
                cfg.save()
            except Exception:
                pass
            return ok
        except Exception:
            return False

    def set_ntp_servers(self, servers: list[str]) -> bool:
        """设置NTP服务器列表并立即尝试对时。"""
        try:
            return self.configure_ntp(servers=servers)
        except Exception:
            return False

    def set_resync_settings(self, interval_sec: float | int | None = None, adjust_threshold_ms: float | int | None = None) -> None:
        try:
            if interval_sec is not None:
                self.resync_interval_sec = float(interval_sec)
            if adjust_threshold_ms is not None:
                self.adjust_threshold_ms = float(adjust_threshold_ms)
            self.logger.log(f"[TIMING] 对时参数: interval={self.resync_interval_sec}s, adjust>{self.adjust_threshold_ms}ms 触发重排", "DEBUG")
            # 持久化设置（若可用）
            try:
                from meowauto.core.config import ConfigManager  # type: ignore
                cfg = ConfigManager()
                cfg.set('ntp.resync_interval_sec', self.resync_interval_sec)
                cfg.set('ntp.adjust_threshold_ms', self.adjust_threshold_ms)
                if self.ntp_servers is not None:
                    cfg.set('ntp.servers', self.ntp_servers)
                cfg.save()
            except Exception:
                pass
        except Exception:
            pass

    def ensure_background_resync(self) -> None:
        """启动全局后台对时线程（与是否存在计划无关），用于实时刷新 rtt/sys_delta。"""
        try:
            if self._bg_resync_thread and self._bg_resync_thread.is_alive():
                return
        except Exception:
            pass
        def _bg_loop():
            while not self._bg_resync_stop:
                try:
                    time.sleep(self.resync_interval_sec)
                    if not self.ntp_enabled:
                        continue
                    ok = False
                    if self.clock and hasattr(self.clock, 'sync'):
                        ok = bool(self.clock.sync())
                    if ok and hasattr(self.clock, 'measure_latency'):
                        stat = self.clock.measure_latency()
                        if stat and stat.get('ok'):
                            self.last_latency_ms = float(stat.get('rtt_ms') or 0.0)
                            self.last_sys_delta_ms = float(stat.get('sys_delta_ms') or 0.0)
                    self.logger.log(f"[TIMING] 后台对时: enabled={self.ntp_enabled} rtt={self.last_latency_ms:.2f}ms Δ={self.last_sys_delta_ms:.2f}ms", "DEBUG")
                except Exception:
                    # 静默继续
                    pass
        try:
            self._bg_resync_stop = False
            t = threading.Thread(target=_bg_loop, daemon=True)
            t.start()
            self._bg_resync_thread = t
        except Exception:
            pass

    def sync_now(self) -> Dict[str, Any]:
        try:
            provider = 'Local'
            ok = False
            if self.clock and hasattr(self.clock, 'sync'):
                ok = bool(self.clock.sync())
                provider = 'NTP' if ok else 'Local'
            drift = getattr(self.clock, 'last_sys_drift_ms', None)
            off = getattr(self.clock, 'last_offset_ms', None)
            self.logger.log(f"[TIMING] 手动同步{('成功' if ok else '失败')} provider={provider} offset_ms={off} drift_ms={drift}")
            # 刷新一次延迟估计
            try:
                if ok and hasattr(self.clock, 'measure_latency'):
                    stat = self.clock.measure_latency()
                    if stat and stat.get('ok'):
                        self.last_latency_ms = float(stat.get('rtt_ms') or 0.0)
                        self.last_sys_delta_ms = float(stat.get('sys_delta_ms') or 0.0)
                        self.logger.log(f"[TIMING] 延迟刷新 rtt_min={self.last_latency_ms:.2f} ms delta={self.last_sys_delta_ms:.2f} ms", "DEBUG")
            except Exception:
                pass
            return {'ok': ok, 'provider': provider, 'offset_ms': off, 'rtt_ms': self.last_latency_ms}
        except Exception:
            return {'ok': False}

    def use_local(self) -> None:
        try:
            if LocalClock:
                self.clock = LocalClock()
                self.logger.log("[TIMING] 已切回本地时钟")
            self.ntp_enabled = False
            # 持久化设置（若可用）
            try:
                from meowauto.core.config import ConfigManager  # type: ignore
                cfg = ConfigManager()
                cfg.set('ntp.enabled', False)
                cfg.save()
            except Exception:
                pass
        except Exception:
            pass

    def set_manual_compensation(self, ms: int) -> None:
        try:
            self.manual_compensation_ms = int(ms)
            self.logger.log(f"[TIMING] 手动补偿设置: {self.manual_compensation_ms} ms", "DEBUG")
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        try:
            base = float(self.last_latency_ms) + float(self.manual_compensation_ms)
            if self.include_ntp_delta:
                base += float(self.last_sys_delta_ms)
            net_shift = base
            return {
                'provider': 'NTP' if getattr(self.clock, 'last_sync_ok', False) else 'Local',
                'offset_ms': getattr(self.clock, 'last_offset_ms', 0.0),
                'rtt_ms': float(self.last_latency_ms),
                'sys_delta_ms': float(self.last_sys_delta_ms),
                'manual_compensation_ms': int(self.manual_compensation_ms),
                'auto_latency_ms': float(self.last_latency_ms),
                'net_shift_ms': net_shift,
                'local_chain_ms': float(self.last_local_chain_ms),
                'include_ntp_delta': bool(self.include_ntp_delta),
            }
        except Exception:
            return {}

    # —— 计划调度（单次） ——
    def _today_target_unix(self, hh: int, mm: int, ss: int, ms: int) -> float:
        # 以“网络时间轴的 now()”为基准计算今天零点，并拼接到目标时刻；若未同步则使用本地系统时间
        if self.clock and getattr(self.clock, 'last_sync_ok', False) and hasattr(self.clock, 'now'):
            now_net = float(self.clock.now())  # 已同步：等同于 unix 秒
        else:
            now_net = time.time()  # 未同步：使用系统时间
        # 将网络时间换算为本地 civil 时间
        lt = time.localtime(now_net)
        # 今天 00:00:00 的时间戳（本地时区）
        day_start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, lt.tm_wday, lt.tm_yday, lt.tm_isdst))
        target = day_start + hh * 3600 + mm * 60 + ss + ms / 1000.0
        return target

    def schedule_play(self,
                      instrument: str,
                      when_hms_ms: Tuple[int, int, int, int],
                      *,
                      play_func: Callable[[str], bool],
                      tempo: float = 1.0,
                      use_analyzed: Optional[bool] = True,
                      ) -> str:
        """创建单次计划：到点后调用 play_func(instrument)。
        - 目标时间 = 今天 HH:MM:SS.mmm 的网络时间 unix
        - 实际触发 = 目标时间 + auto_rtt + manual_compensation
        若目标时间已过（距离 now_net < 50ms），直接返回失败应由上层控制，此处仍允许创建，但会很快触发。
        """
        hh, mm, ss, ms = [int(x) for x in when_hms_ms]
        base_unix = self._today_target_unix(hh, mm, ss, ms)
        # 自动延迟：使用最近测得的最小 RTT
        auto_ms = float(self.last_latency_ms or 0.0)
        # 手动补偿
        manual_ms = float(self.manual_compensation_ms or 0)
        # NTP-本地偏差（可选并入）
        delta_ms = float(self.last_sys_delta_ms or 0.0) if self.include_ntp_delta else 0.0
        schedule_unix = base_unix + (auto_ms + manual_ms + delta_ms) / 1000.0

        # 若目标计划时间已经过去较多（>50ms），视为不合法，返回失败
        now_s = time.time()
        if schedule_unix - now_s < 0.05:
            self.logger.log(
                f"[TIMING] 计划创建失败：目标时间已过 id=-- inst={instrument} base={base_unix:.3f} now={now_s:.3f} -> at={schedule_unix:.3f}",
                "ERROR",
            )
            return ""

        sid = uuid.uuid4().hex[:10]
        self.logger.log(
            f"[TIMING] 创建计划 id={sid} inst={instrument} base={base_unix:.3f} +auto={auto_ms:.1f}ms +manual={manual_ms:.1f}ms -> at={schedule_unix:.3f}",
            "INFO",
        )

        def _on_fire():
            t_now = time.time()
            err_ms = (t_now - schedule_unix) * 1000.0
            self.logger.log(
                f"[TIMING] 触发 id={sid} inst={instrument} at={schedule_unix:.3f} now={t_now:.3f} err={err_ms:.2f}ms tempo={tempo}",
                "INFO",
            )
            try:
                ok = bool(play_func(instrument))
                self.logger.log(f"[TIMING] 播放触发 {'成功' if ok else '失败'} inst={instrument}")
            finally:
                # 单次计划：触发后移除
                try:
                    sc = self.schedules.get(sid)
                    if sc is not None:
                        sc['fired'] = True
                except Exception:
                    pass
                self.schedules.pop(sid, None)

        # 调度
        handle = None
        try:
            if self.clock and hasattr(self.clock, 'schedule_at'):
                handle = self.clock.schedule_at(schedule_unix, _on_fire, tk_root=self.tk_root)  # type: ignore[attr-defined]
            else:
                # 退回本地：粗略调度
                delay = max(0.0, schedule_unix - time.time())
                th = threading.Timer(delay, _on_fire)
                th.daemon = True
                th.start()
                handle = th
        except Exception:
            handle = None
        self.schedules[sid] = {
            'instrument': instrument,
            'when': when_hms_ms,
            'base_unix': base_unix,
            'schedule_unix': schedule_unix,
            'auto_latency_ms': auto_ms,
            'manual_compensation_ms': manual_ms,
            'handle': handle,
            'tempo': float(tempo),
            'use_analyzed': bool(use_analyzed),
            'cancelled': False,
            'fired': False,
        }

        # 立即刷新一次对时与本地链路延迟，便于UI立刻显示
        try:
            # 若需要网络对时，确保此时才实例化网络时钟，避免应用启动时卡顿
            self._ensure_clock_initialized()
            if self.ntp_enabled and hasattr(self.clock, 'sync'):
                _ = self.clock.sync()
            if self.ntp_enabled and hasattr(self.clock, 'measure_latency'):
                stat0 = self.clock.measure_latency()
                if stat0 and stat0.get('ok'):
                    self.last_latency_ms = float(stat0.get('rtt_ms') or 0.0)
                    self.last_sys_delta_ms = float(stat0.get('sys_delta_ms') or 0.0)
                    self.schedules[sid]['auto_latency_ms'] = self.last_latency_ms
            # 记录一次关键信息便于观察
            net_shift0 = (self.last_latency_ms + self.manual_compensation_ms + (self.last_sys_delta_ms if self.include_ntp_delta else 0.0))
            self.logger.log(
                f"[TIMING] 计划初始化: id={sid} NTP-本地偏差={self.last_sys_delta_ms:.2f}ms 网络往返延迟={self.last_latency_ms:.2f}ms 手动补偿={self.manual_compensation_ms:.2f}ms 合成偏移={net_shift0:.2f}ms at={schedule_unix:.3f}",
                "INFO",
            )
        except Exception:
            pass
        try:
            start0 = time.perf_counter()
            evt0 = threading.Event()
            def _ping0():
                evt0.set()
            t0 = threading.Timer(0.0, _ping0)
            t0.daemon = True
            t0.start()
            evt0.wait(timeout=0.5)
            self.last_local_chain_ms = max(0.0, (time.perf_counter() - start0) * 1000.0)
        except Exception:
            pass

        # 启动维护线程：周期性对时并动态调整触发时间
        def _maintain():
            self.logger.log(f"[TIMING] 维护线程启动: id={sid} interval={self.resync_interval_sec}s threshold={self.adjust_threshold_ms}ms include_ntp_delta={self.include_ntp_delta}", "INFO")
            while True:
                # 线程生命检查
                sc = self.schedules.get(sid)
                if not sc:
                    self.logger.log(f"[TIMING] 维护线程退出: 计划不存在 id={sid}", "DEBUG")
                    return
                if sc.get('cancelled') or sc.get('fired'):
                    self.logger.log(f"[TIMING] 维护线程退出: 状态 cancelled/fired id={sid}", "DEBUG")
                    return
                # 周期节拍
                try:
                    time.sleep(self.resync_interval_sec)
                except Exception:
                    pass
                    # 若关闭NTP，则跳过对时维护
                if not self.ntp_enabled:
                    continue
                # 同步网络时钟与延迟估计
                try:
                    ok = False
                    if hasattr(self.clock, 'sync'):
                        ok = bool(self.clock.sync())
                    if ok and hasattr(self.clock, 'measure_latency'):
                        stat = self.clock.measure_latency()
                        if stat and stat.get('ok'):
                            self.last_latency_ms = float(stat.get('rtt_ms') or 0.0)
                            self.last_sys_delta_ms = float(stat.get('sys_delta_ms') or 0.0)
                            sc['auto_latency_ms'] = self.last_latency_ms
                    st = self.get_status()
                    # 提升为 INFO，便于默认日志等级可见
                    self.logger.log(
                        f"[TIMING] 周期对时: 来源={st.get('provider')} NTP-本地偏差={self.last_sys_delta_ms:.2f}ms 网络往返延迟={self.last_latency_ms:.2f}ms 手动补偿={self.manual_compensation_ms:.2f}ms 合成偏移={st.get('net_shift_ms'):.2f}ms",
                        "INFO",
                    )
                except Exception as e:
                    self.logger.log(f"[TIMING] 周期对时异常: {e}", "WARNING")
                    # 测量本地链路延迟（基于Timer(0)的调度开销）
                    try:
                        start = time.perf_counter()
                        evt = threading.Event()
                        def _ping():
                            evt.set()
                        t = threading.Timer(0.0, _ping)
                        t.daemon = True
                        t.start()
                        evt.wait(timeout=0.5)
                        self.last_local_chain_ms = max(0.0, (time.perf_counter() - start) * 1000.0)
                    except Exception as e:
                        self.logger.log(f"[TIMING] 本地链路测量异常: {e}", "WARNING")
                    # 重新计算目标触发时刻
                    try:
                        auto_ms_new = float(self.last_latency_ms or 0.0)
                        manual_ms_new = float(self.manual_compensation_ms or 0.0)
                        delta_ms_new = float(self.last_sys_delta_ms or 0.0) if self.include_ntp_delta else 0.0
                        new_schedule_unix = sc['base_unix'] + (auto_ms_new + manual_ms_new + delta_ms_new) / 1000.0
                        now_s = time.time()
                        # 若新目标已过，则不再调整（很快就会触发/或已错过）
                        if new_schedule_unix <= now_s:
                            continue
                        old_schedule_unix = sc.get('schedule_unix', new_schedule_unix)
                        diff_ms = abs(new_schedule_unix - old_schedule_unix) * 1000.0
                        if diff_ms > self.adjust_threshold_ms:
                            # 取消旧调度并重建
                            try:
                                if sc.get('handle') is not None:
                                    h = sc['handle']
                                    if hasattr(h, 'cancel'):
                                        h.cancel()
                                    elif hasattr(self.clock, 'cancel'):
                                        self.clock.cancel(h)  # type: ignore
                            except Exception:
                                pass
                            # 重建
                            try:
                                if self.clock and hasattr(self.clock, 'schedule_at'):
                                    new_handle = self.clock.schedule_at(new_schedule_unix, _on_fire, tk_root=self.tk_root)  # type: ignore[attr-defined]
                                else:
                                    delay = max(0.0, new_schedule_unix - time.time())
                                    th2 = threading.Timer(delay, _on_fire)
                                    th2.daemon = True
                                    th2.start()
                                    new_handle = th2
                                sc['handle'] = new_handle
                                sc['schedule_unix'] = new_schedule_unix
                                self.logger.log(
                                    f"[TIMING] 计划重置: id={sid} old={old_schedule_unix:.3f} -> new={new_schedule_unix:.3f} (Δ={diff_ms:.2f}ms)",
                                    "INFO",
                                )
                            except Exception as e:
                                self.logger.log(f"[TIMING] 重建调度异常: {e}", "WARNING")
                    except Exception as e:
                        self.logger.log(f"[TIMING] 目标重算异常: {e}", "WARNING")

        try:
            # 启动线程前打印一次关键信息，便于定位线程是否提交
            self.logger.log(
                f"[TIMING] 准备启动维护线程: id={sid} ntp_enabled={self.ntp_enabled} interval={self.resync_interval_sec}s threshold={self.adjust_threshold_ms}ms include_ntp_delta={self.include_ntp_delta}",
                "INFO",
            )
            thm = threading.Thread(target=_maintain, daemon=True)
            thm.start()
            self.logger.log(f"[TIMING] 维护线程已提交: id={sid} alive={thm.is_alive()}", "INFO")
        except Exception:
            try:
                import traceback
                self.logger.log(f"[TIMING] 维护线程启动失败: id={sid}\n{traceback.format_exc()}", "ERROR")
            except Exception:
                self.logger.log(f"[TIMING] 维护线程启动失败(未知异常) id={sid}", "ERROR")
        return sid

    def cancel_schedule(self, schedule_id: str) -> bool:
        sc = self.schedules.get(schedule_id)
        if not sc:
            return False
        handle = sc.get('handle')
        ok = True
        try:
            sc['cancelled'] = True
            if handle is not None:
                if hasattr(handle, 'cancel'):
                    handle.cancel()  # type: ignore
                elif hasattr(self.clock, 'cancel'):
                    self.clock.cancel(handle)  # type: ignore
        except Exception:
            ok = False
        self.schedules.pop(schedule_id, None)
        self.logger.log(f"[TIMING] 计划已取消 id={schedule_id}")
        return ok

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        try:
            return dict(self.schedules.get(schedule_id) or {})
        except Exception:
            return None

__all__ = [
    'TimingService',
]
