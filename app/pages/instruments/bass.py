#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
贝斯页面：复用通用文件选择、播放控制、底部进度与右侧日志面板。
特性：
- 3×7 键位（与钢琴上三排一致），不提供和弦相关项；
- 不展示“合奏”页签；
- 复用分部/分轨识别、播放与导出按钮（已由 playback_controls 组件提供）。
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
try:
    from ...meowauto.core.config import ConfigManager  # 相对导入到核心配置
except Exception:
    ConfigManager = None  # 兜底

try:
    from .. import BasePage  # type: ignore
except Exception:
    class BasePage:  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...


class BassPage(BasePage):
    def __init__(self, controller):
        self.controller = controller
        self._mounted = False
        self._prev_keymap_profile = None

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # 标题区
        try:
            header = ttk.Frame(left)
            header.pack(fill=tk.X, pady=(0, 6))
            ttk.Label(header, text="贝斯 · 独奏", font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)
            ttk.Label(left, text="键位布局：3×7（无和弦键）。此页不展示合奏相关控件。").pack(anchor=tk.W)
        except Exception:
            pass

        # 内容容器：避免 pack/grid 混用冲突
        try:
            content = ttk.Frame(left)
            content.pack(fill=tk.BOTH, expand=True)
            try:
                content.grid_columnconfigure(0, weight=1)
                content.grid_rowconfigure(1, weight=1)
            except Exception:
                pass
        except Exception:
            content = left

        # 左侧：文件选择、播放控制（禁用合奏页签）、底部进度
        try:
            self.controller._create_file_selection_component(content)
        except Exception:
            pass
        try:
            # include_ensemble=False 隐藏“合奏”页签及相关控件
            self.controller._create_playback_control_component(content, include_ensemble=False)
        except Exception:
            pass
        try:
            self.controller._create_bottom_progress(content)
        except Exception:
            pass

        # 切换键位映射到 bass（3×7）。注意：保存并在卸载时恢复。
        try:
            if ConfigManager is not None:
                cfg = ConfigManager()
                self._prev_keymap_profile = str(cfg.get('playback.keymap_profile', 'piano'))
                if self._prev_keymap_profile.lower() != 'bass':
                    cfg.set('playback.keymap_profile', 'bass')
                    cfg.save_config()
        except Exception:
            pass

        # 右侧：仅保留“系统日志”，隐藏“MIDI解析/事件表”
        try:
            self.controller._create_right_pane(right, show_midi_parse=False, show_events=False, show_logs=True)
        except Exception:
            pass

        self._mounted = True

    def unmount(self):
        # 恢复之前的键位映射配置
        try:
            if ConfigManager is not None and self._prev_keymap_profile is not None:
                cfg = ConfigManager()
                cfg.set('playback.keymap_profile', self._prev_keymap_profile)
                cfg.save_config()
        except Exception:
            pass
        self._mounted = False
