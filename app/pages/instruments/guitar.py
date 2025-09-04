#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
吉他页面：复用电子琴的功能组件与流程
- 左侧：文件选择、播放控制、底部进度
- 右侧：日志/状态分页
- 根据 controller.instrument_mode['吉他'] 显示独奏/合奏
- 复用现有控制器方法与设置项，MIDI 解析流程与电子琴一致
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

try:
    from .. import BasePage  # type: ignore
except Exception:
    class BasePage:  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...


class GuitarPage(BasePage):
    def __init__(self, controller):
        self.controller = controller
        self._mounted = False

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # 左侧：标题（独奏/合奏）
        try:
            header = ttk.Frame(left)
            header.pack(fill=tk.X, pady=(0, 6))
            inst_mode = None
            try:
                modes = getattr(self.controller, 'instrument_mode', {})
                inst_mode = modes.get('吉他') if isinstance(modes, dict) else None
            except Exception:
                pass
            mode_text = '合奏' if inst_mode == 'ensemble' else '独奏'
            ttk.Label(header, text=f"吉他 · {mode_text}",
                      font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)
        except Exception:
            pass

        # 内容容器：避免与 header 同容器引起 pack/grid 冲突
        try:
            content = ttk.Frame(left)
            content.pack(fill=tk.BOTH, expand=True)
            try:
                content.grid_columnconfigure(0, weight=1)
                content.grid_rowconfigure(1, weight=1)
            except Exception:
                pass
            # 复用与电子琴一致的组件
            self.controller._create_file_selection_component(content)
        except Exception:
            pass
        try:
            include_ensemble = (inst_mode == 'ensemble')
            self.controller._create_playback_control_component(content, include_ensemble=include_ensemble)
        except Exception:
            pass
        try:
            self.controller._create_bottom_progress(content)
        except Exception:
            pass

        # 右侧：日志/状态分页
        try:
            self.controller._create_right_pane(right)
        except Exception:
            ttk.Label(right, text="日志/状态区（预留）").pack(anchor=tk.NW, padx=6, pady=6)

        self._mounted = True

    def unmount(self):
        self._mounted = False
