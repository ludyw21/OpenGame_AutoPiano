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
        # 顶部标题已移除，让上层分页标签占据顶部
        inst_mode = None
        try:
            modes = getattr(self.controller, 'instrument_mode', {})
            inst_mode = modes.get('电子琴') if isinstance(modes, dict) else None
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

            # 文件选择已移入“控制”分页，由播放控制组件统一渲染
            
        except Exception:
            pass
        try:
            include_ensemble = (inst_mode == 'ensemble')
            self.controller._create_playback_control_component(content, include_ensemble=include_ensemble, instrument='电子琴')
        except Exception:
            pass
        # 已移除底部进度组件，以便页面内容占满并由右侧滚动条统一控制

        # 右侧已移除

        self._mounted = True

    def unmount(self):
        self._mounted = False
