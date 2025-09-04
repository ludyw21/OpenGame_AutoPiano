#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电子琴页面：对接现有功能（文件选择、播放控制、右侧日志与底部进度）。
根据 controller.current_mode 显示独奏/合奏相关控件（include_ensemble）。
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

try:
    # 优先复用 Router 的 BasePage
    from .. import BasePage  # type: ignore
except Exception:
    class BasePage:  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...


class EPianoPage(BasePage):
    def __init__(self, controller):
        self.controller = controller
        self._mounted = False

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # 左侧：文件选择、播放控制、底部进度
        try:
            # 标题区（显示当前模式）
            header = ttk.Frame(left)
            header.pack(fill=tk.X, pady=(0, 6))
            # 按乐器独立模式（默认 solo）
            inst_mode = None
            try:
                modes = getattr(self.controller, 'instrument_mode', {})
                inst_mode = modes.get('电子琴') if isinstance(modes, dict) else None
            except Exception:
                pass
            mode_text = '合奏' if inst_mode == 'ensemble' else '独奏'
            ttk.Label(header, text=f"电子琴 · {mode_text}",
                      font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)
        except Exception:
            pass

        try:
            # 关键：避免在同一容器既 pack 又 grid —— 创建子容器供组件使用（组件内部可使用 grid）
            content = ttk.Frame(left)
            content.pack(fill=tk.BOTH, expand=True)
            # 自适应：content 作为 grid 容器，列0与行1可扩展
            try:
                content.grid_columnconfigure(0, weight=1)
                # 行0: 文件选择（不扩展）；行1: 播放控制（扩展）；行3: 底部进度（不扩展）
                content.grid_rowconfigure(1, weight=1)
            except Exception:
                pass

            # 将组件都渲染在 content 内，避免与 header 共容器导致的 pack/grid 冲突
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
            pass

        self._mounted = True

    def unmount(self):
        self._mounted = False
