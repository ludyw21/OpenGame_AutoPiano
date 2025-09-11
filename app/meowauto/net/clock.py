# -*- coding: utf-8 -*-
"""
时钟提供者（占位模块）

目标：
- 为本地/网络同步时钟提供统一接口，供 AutoPlayer/PlaybackService 注入
- 便于未来扩展 NTP/房主广播/P2P 逻辑
"""
from __future__ import annotations
from typing import Protocol, Callable, Optional, List
import time
import socket
import struct


class ClockProvider(Protocol):
    """抽象时钟接口：提供单调时间与调度。"""
    def now(self) -> float:
        """返回单调时间（秒）。"""
        ...

    def schedule(self, delay: float, cb: Callable[[], None]) -> Optional[object]:
        """在 delay 秒后回调 cb，返回可取消句柄（可选）。"""
        ...

    def cancel(self, handle: object) -> None:
        """取消此前的 schedule。"""
        ...


class LocalClock:
    """本地单机时钟（占位实现）。"""
    def now(self) -> float:
        return time.monotonic()

    def schedule(self, delay: float, cb: Callable[[], None]) -> Optional[object]:
        # 占位：上层可用 Tk.after/线程计时等具体机制实现
        return None

    def cancel(self, handle: object) -> None:
        return None


class NetworkClockProvider:
    """网络时钟（NTP 简实现）：从公网 NTP 获取时间，换算为与 monotonic 对齐的时间轴。

    说明：
    - 采用 SNTP（UDP/123）读取服务端 Transmit Timestamp（秒）
    - 计算 offset_monotonic = ntp_unix - time.monotonic()，使 now() 可单调递增
    - 不依赖第三方库；若网络不可达，将回退到本地 monotonic
    """
    # 常见公共 NTP 服务器默认列表
    DEFAULT_SERVERS: List[str] = [
        'ntp.ntsc.ac.cn',           # 国家授时中心
        'time.apple.com',           # Apple 公共 NTP
        'time1.cloud.tencent.com',  # 腾讯云公共 NTP（1-5均可）
        'time2.cloud.tencent.com',
        'time3.cloud.tencent.com',
        'time4.cloud.tencent.com',
        'time5.cloud.tencent.com',
        'pool.ntp.org',             # 国际 NTP 池
    ]

    _NTP_EPOCH = 2208988800  # NTP(1900) -> Unix(1970)

    def __init__(self, *, servers: Optional[List[str]] = None, timeout: float = 1.5, max_tries: int = 3):
        self.servers = servers or list(self.DEFAULT_SERVERS)
        self.timeout = float(timeout)
        self.max_tries = int(max_tries)
        self._offset = 0.0  # 与 monotonic 的偏移（秒）
        self._last_sync_ok = False
        self._last_sync_time = 0.0  # 最近一次成功同步的本地时间（monotonic 轴）
        self._last_sys_drift_ms = 0.0  # 与系统 time.time() 的差值（毫秒），正值表示网络钟领先系统钟
        # 初始化时尝试一次同步（非致命）
        try:
            self.sync()
        except Exception:
            pass

    def measure_latency(self, samples: int = 5, timeout: Optional[float] = None) -> dict:
        """多次采样以估计网络往返时延（RTT）与当前 offset。

        返回示例：
        {
          'ok': True,
          'rtt_ms': 8.4,              # 采用样本中的最小 RTT 作为估计
          'offset_ms': 123.1,         # 当前 offset（monotonic->unix）的毫秒估计
          'samples': [ {'server': 'ntp.ntsc.ac.cn', 'rtt_ms': 9.2}, ... ],
          'server': 'ntp.ntsc.ac.cn'  # 最小 RTT 样本对应的服务器
        }
        """
        results: List[dict] = []
        best: Optional[dict] = None
        to = float(timeout) if (timeout is not None) else self.timeout
        for i in range(max(1, int(samples))):
            for host in list(self.servers):
                t0 = time.perf_counter()
                t_ntp = self._query_ntp(host)
                t1 = time.perf_counter()
                if t_ntp is None:
                    continue
                rtt_ms = max(0.0, (t1 - t0) * 1000.0)
                # 使用系统时钟与 NTP 时间的差值，避免把 monotonic 偏移当作可读 offset
                sys_delta_ms = (t_ntp - time.time()) * 1000.0
                rec = {'server': host, 'rtt_ms': rtt_ms, 'sys_delta_ms': sys_delta_ms}
                results.append(rec)
                if (best is None) or (rtt_ms < best['rtt_ms']):
                    best = rec
        if not best:
            return {'ok': False, 'rtt_ms': None, 'sys_delta_ms': None, 'samples': results}
        return {'ok': True, 'rtt_ms': float(best['rtt_ms']), 'sys_delta_ms': float(best['sys_delta_ms']), 'samples': results, 'server': best['server']}

    def _query_ntp(self, host: str) -> Optional[float]:
        """查询单个 NTP 服务器，返回 Unix 时间戳（秒）。失败返回 None。"""
        try:
            addr = (host, 123)
            # 48字节请求包，LI=0, VN=4, Mode=3(client)
            packet = b'\x1b' + 47 * b'\0'
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(self.timeout)
                s.sendto(packet, addr)
                data, _ = s.recvfrom(512)
                if len(data) < 48:
                    return None
                # 取 transmit timestamp（bytes 40..47）
                tx_sec, tx_frac = struct.unpack('!II', data[40:48])
                ntp_seconds = tx_sec + tx_frac / 2**32
                unix_seconds = ntp_seconds - self._NTP_EPOCH
                return float(unix_seconds)
        except Exception:
            return None

    def sync(self) -> bool:
        """轮询服务器进行对时，成功则更新 offset 并返回 True。"""
        tries = 0
        for host in list(self.servers):
            if tries >= self.max_tries:
                break
            tries += 1
            t_ntp = self._query_ntp(host)
            if t_ntp is not None:
                # 将 NTP 对齐到 monotonic 轴
                now_mono = time.monotonic()
                self._offset = t_ntp - now_mono
                self._last_sync_ok = True
                self._last_sync_time = now_mono
                try:
                    # 记录相对系统时钟的漂移（毫秒）
                    self._last_sys_drift_ms = (t_ntp - time.time()) * 1000.0
                except Exception:
                    self._last_sys_drift_ms = 0.0
                return True
        # 全部失败
        self._last_sync_ok = False
        return False

    def now(self) -> float:
        # 若同步成功，返回单调时间 + 偏移；否则回退到本地单调时间
        if self._last_sync_ok:
            return time.monotonic() + self._offset
        return time.monotonic()

    def schedule(self, delay: float, cb: Callable[[], None]):
        # 交由上层（如 Tk.after/线程）实现，这里保持占位
        return None

    def cancel(self, handle: object) -> None:
        return None

    def schedule_at(self, unix_ts: float, cb: Callable[[], None], *, tk_root: Optional[object] = None, tolerance_ms: int = 2):
        """在给定“网络时间轴”的绝对 Unix 秒时间戳调度回调。

        - 当 last_sync_ok=True 时：目标单调时刻 = unix_ts - self._offset
        - 否则退回本地系统时钟：目标单调时刻 = 当前 monotonic + (unix_ts - time.time())
        - 分级等待：长睡眠 -> 短睡眠 -> 忙等（<= tolerance_ms）
        - 若提供 tk_root（Tk对象），将使用 after 进行细粒度调度，句柄可被 cancel
        """
        import threading

        tol = max(0.0, float(tolerance_ms) / 1000.0)
        now_mono = time.monotonic()
        if self._last_sync_ok:
            target_mono = float(unix_ts) - float(self._offset)
        else:
            # 回退：按本地系统时间估算
            delta = float(unix_ts) - time.time()
            target_mono = now_mono + max(0.0, delta)

        # 线程定时 + 可选 Tk.after 兜底校准
        cancelled = {'flag': False}
        after_id = {'v': None}

        def runner():
            if cancelled['flag']:
                return
            while True:
                now = time.monotonic()
                remain = target_mono - now
                if remain <= 0:
                    break
                if remain > 0.1:
                    time.sleep(min(0.5, remain - 0.05))
                elif remain > 0.01:
                    time.sleep(remain - 0.005)
                elif remain > tol:
                    time.sleep(0.001)
                else:
                    # 忙等阶段
                    while (time.monotonic() < target_mono) and not cancelled['flag']:
                        pass
                    break
            if cancelled['flag']:
                return
            # 最终触发，若 tk_root 可用则切回主线程
            if tk_root is not None and hasattr(tk_root, 'after'):
                try:
                    after_id['v'] = tk_root.after(0, cb)
                    return
                except Exception:
                    pass
            try:
                cb()
            except Exception:
                pass

        th = threading.Thread(target=runner, daemon=True)
        th.start()

        class _Handle:
            def cancel(self_inner):
                cancelled['flag'] = True
                try:
                    if tk_root is not None and after_id['v'] is not None:
                        tk_root.after_cancel(after_id['v'])
                except Exception:
                    pass

        return _Handle()


# 兼容导出别名
NTPClockProvider = NetworkClockProvider

# —— 可读属性（向后兼容：不依赖属性也能工作） ——
def _get_last_offset(self: NetworkClockProvider) -> float:
    return float(getattr(self, '_offset', 0.0))

def _get_last_offset_ms(self: NetworkClockProvider) -> float:
    try:
        return _get_last_offset(self) * 1000.0
    except Exception:
        return 0.0

def _get_last_sync_ok(self: NetworkClockProvider) -> bool:
    return bool(getattr(self, '_last_sync_ok', False))

def _get_last_sync_time(self: NetworkClockProvider) -> float:
    return float(getattr(self, '_last_sync_time', 0.0))

# 以属性形式暴露，避免破坏现有使用方式
NetworkClockProvider.last_offset = property(lambda self: _get_last_offset(self))
NetworkClockProvider.last_offset_ms = property(lambda self: _get_last_offset_ms(self))
NetworkClockProvider.last_sync_ok = property(lambda self: _get_last_sync_ok(self))
NetworkClockProvider.last_sync_time = property(lambda self: _get_last_sync_time(self))
NetworkClockProvider.last_sys_drift_ms = property(lambda self: float(getattr(self, '_last_sys_drift_ms', 0.0)))

__all__ = [
    "ClockProvider",
    "LocalClock",
    "NetworkClockProvider",
    "NTPClockProvider",
]
