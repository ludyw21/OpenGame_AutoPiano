#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
架子鼓页面：提供文件选择、速度倍率、播放控制（开始/暂停/继续/停止）。
调用 DrumsController 接口执行鼓专用MIDI播放。
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

try:
    from .. import BasePage  # type: ignore
except Exception:
    class BasePage:  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...


class DrumsPage(BasePage):
    def __init__(self, controller, app_ref=None):
        self.controller = controller
        self.app_ref = app_ref  # 可选：用于复用电子琴的播放列表/文件选择组件
        self._mounted = False
        # UI state
        self.var_path = tk.StringVar(value="")
        self.var_tempo = tk.DoubleVar(value=1.0)
        # 使用 Optional 以兼容 Python 3.8/3.9 环境
        from typing import Optional
        self.btn_start: Optional[ttk.Button] = None
        self.btn_pause: Optional[ttk.Button] = None
        self.btn_resume: Optional[ttk.Button] = None
        self.btn_stop: Optional[ttk.Button] = None
        # 右侧日志
        self._right = None
        self._log_text: Optional[tk.Text] = None

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # Header
        header = ttk.Frame(left)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="架子鼓", font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)

        # Content 容器
        content = ttk.Frame(left)
        content.pack(fill=tk.BOTH, expand=True)
        # 为复用组件单独准备子容器（组件内部可用 grid），避免与本页 pack 冲突
        fs_container = ttk.Frame(content)
        fs_container.pack(fill=tk.X, pady=(0, 4))

        # 尝试复用电子琴的文件选择/播放列表组件（同款播放列表）
        used_playlist = False
        try:
            host = self.app_ref or self.controller
            if host and hasattr(host, '_create_file_selection_component'):
                host._create_file_selection_component(fs_container)
                used_playlist = True
        except Exception:
            used_playlist = False

        # 若不可用，则回退到本页的简单文件选择器
        if not used_playlist:
            row_file = ttk.Frame(fs_container)
            row_file.pack(fill=tk.X, pady=4)
            ttk.Label(row_file, text="鼓MIDI文件:").pack(side=tk.LEFT)
            entry = ttk.Entry(row_file, textvariable=self.var_path)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            ttk.Button(row_file, text="浏览…", command=self._on_browse).pack(side=tk.LEFT)

        # Tempo control（放入 content，避免被上方内容区 expand 占满后导致不可见）
        row_tempo = ttk.Frame(content)
        row_tempo.pack(fill=tk.X, pady=4)
        ttk.Label(row_tempo, text="速度倍率:").pack(side=tk.LEFT)
        scale = ttk.Scale(row_tempo, from_=0.5, to=2.0, orient=tk.HORIZONTAL, variable=self.var_tempo, command=self._on_tempo_change)
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Label(row_tempo, textvariable=tk.StringVar(value="0.5x … 2.0x"), foreground="#666").pack(side=tk.LEFT)

        # Controls
        row_ctrl = ttk.Frame(content)
        row_ctrl.pack(fill=tk.X, pady=8)
        self.btn_start = ttk.Button(row_ctrl, text="开始", command=self._on_start)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_pause = ttk.Button(row_ctrl, text="暂停", command=self._on_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=3)
        self.btn_resume = ttk.Button(row_ctrl, text="继续", command=self._on_resume)
        self.btn_resume.pack(side=tk.LEFT, padx=3)
        self.btn_stop = ttk.Button(row_ctrl, text="停止", command=self._on_stop)
        self.btn_stop.pack(side=tk.LEFT, padx=3)

        # Right pane: 日志/状态区
        self._right = right
        for w in list(right.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        ttk.Label(right, text="架子鼓回放状态", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.NW, padx=6, pady=(6, 0))
        ttk.Label(right, text="右侧显示倒计时、开始/暂停/停止以及解析与映射日志。", foreground="#666").pack(anchor=tk.NW, padx=6)
        # 滚动日志
        log_frame = ttk.Frame(right)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        yscroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL)
        txt = tk.Text(log_frame, height=12, wrap=tk.WORD, yscrollcommand=yscroll.set)
        yscroll.config(command=txt.yview)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text = txt

        self._mounted = True

    def unmount(self):
        self._mounted = False

    # ===== UI Callbacks =====
    def _on_browse(self):
        path = filedialog.askopenfilename(title="选择鼓MIDI文件", filetypes=[('MIDI Files', '*.mid *.midi'), ('All Files', '*.*')])
        if path:
            self.var_path.set(path)

    def _on_tempo_change(self, _evt=None):
        try:
            tempo = float(self.var_tempo.get())
            if hasattr(self.controller, 'apply_settings'):
                self.controller.apply_settings({'tempo': tempo})
        except Exception:
            pass

    def _on_start(self):
        path = self.var_path.get().strip()
        if not path:
            # 尝试从共享播放列表变量读取
            try:
                host = self.app_ref or self.controller
                if host is not None and hasattr(host, 'midi_path_var'):
                    p = host.midi_path_var.get()
                    if isinstance(p, str) and p.strip():
                        path = p.strip()
            except Exception:
                pass
        if not path:
            messagebox.showwarning("提示", "请先选择鼓MIDI文件或从左侧播放列表选择")
            self._log("未选择文件，无法开始")
            return
        # validate existence (support relative path to project root)
        if not os.path.isabs(path):
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            cand = os.path.abspath(os.path.join(base, path))
            if os.path.exists(cand):
                path = cand
        if not os.path.exists(path):
            messagebox.showerror("错误", f"文件不存在:\n{path}")
            self._log(f"文件不存在: {path}")
            return
        tempo = float(self.var_tempo.get())
        self._log(f"将以速度倍率 {tempo:.2f}x 播放: {os.path.basename(path)}")
        # 倒计时并开始
        self._set_buttons_state(disabled=True)
        self._start_with_countdown(path, tempo, seconds=3)

    def _on_pause(self):
        try:
            if hasattr(self.controller, 'pause'):
                self.controller.pause()
                self._log("已暂停")
        except Exception:
            pass

    def _on_resume(self):
        try:
            if hasattr(self.controller, 'resume'):
                self.controller.resume()
                self._log("已继续")
        except Exception:
            pass

    def _on_stop(self):
        try:
            if hasattr(self.controller, 'stop'):
                self.controller.stop()
                self._log("已停止")
        except Exception:
            pass

    # ===== Helpers =====
    def _log(self, msg: str):
        try:
            if self._log_text is None:
                return
            from time import strftime, localtime
            ts = strftime('%H:%M:%S', localtime())
            self._log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self._log_text.see(tk.END)
        except Exception:
            pass

    def _set_buttons_state(self, disabled: bool):
        try:
            state = tk.DISABLED if disabled else tk.NORMAL
            for b in (self.btn_start, self.btn_pause, self.btn_resume, self.btn_stop):
                if b is not None:
                    b.config(state=state)
        except Exception:
            pass

    def _start_with_countdown(self, path: str, tempo: float, seconds: int = 3):
        # 使用 after 实现倒计时，避免阻塞 UI
        if seconds <= 0:
            self._log("开始播放")
            ok = False
            try:
                if hasattr(self.controller, 'start_from_file'):
                    ok = bool(self.controller.start_from_file(path, tempo=tempo))
            except Exception:
                ok = False
            if not ok:
                message = (
                    "无法开始播放。\n\n"
                    "可能原因：\n"
                    "- 未安装 mido：请安装 mido 后重试\n"
                    "- MIDI 不含鼓事件（通道10或35-81打击乐音高）\n"
                    "- 键位映射缺失或异常\n\n"
                    "建议：\n"
                    "1) 在命令行安装 mido：pip install mido\n"
                    "2) 更换一个鼓 MIDI 文件测试（如 SERBEAT2.mid）\n"
                    "3) 重启应用后重试"
                )
                messagebox.showerror("错误", message)
                self._log("开始失败")
            else:
                self._log("已开始")
            self._set_buttons_state(disabled=False)
            return

        self._log(f"{seconds}…")
        widget = self._right if self._right is not None else None
        try:
            target = widget or (self._log_text if self._log_text is not None else None)
            base = target if target is not None else None
            # Fallback to any widget for after
            if base is None:
                base = tk._get_default_root()  # type: ignore
            base.after(1000, lambda: self._start_with_countdown(path, tempo, seconds-1))
        except Exception:
            # 若 after 不可用，直接开始
            self._start_with_countdown(path, tempo, 0)
