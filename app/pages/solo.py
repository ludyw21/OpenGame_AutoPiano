#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

class SoloPage:
    def __init__(self, controller=None):
        self._mounted = False
        self._left = None
        self._right = None
        self._widgets = []
        self.controller = controller
        self._left_container = None
        self._right_container = None

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        self._mounted = True
        self._left, self._right = left, right
        # 容器：便于统一销毁
        self._left_container = ttk.Frame(left)
        self._left_container.pack(fill=tk.BOTH, expand=True)
        self._right_container = ttk.Frame(right)
        self._right_container.pack(fill=tk.BOTH, expand=True)
        # 通过控制器在容器内创建全部主界面组件
        if self.controller:
            try:
                # 左栏
                self.controller._create_file_selection_component(parent_left=self._left_container)
                self.controller._create_playback_control_component(parent_left=self._left_container, include_ensemble=False)
                self.controller._create_bottom_progress(parent_left=self._left_container)
                # 右栏
                self.controller._create_right_pane(parent_right=self._right_container)
            except Exception:
                # 若发生异常，提供最小占位以避免空白
                lf = ttk.Label(self._left_container, text="独奏模式（加载失败占位）", anchor=tk.W)
                lf.pack(anchor=tk.NW, padx=6, pady=6)
                rf = ttk.Label(self._right_container, text="右侧（加载失败占位）", anchor=tk.W)
                rf.pack(anchor=tk.NW, padx=6, pady=6)
                self._widgets = [lf, rf]
        else:
            # 无控制器：使用占位
            lf = ttk.Label(self._left_container, text="独奏模式（占位）", anchor=tk.W)
            lf.pack(anchor=tk.NW, padx=6, pady=6)
            rf = ttk.Label(self._right_container, text="日志/状态（占位）", anchor=tk.W)
            rf.pack(anchor=tk.NW, padx=6, pady=6)
            self._widgets = [lf, rf]

    def unmount(self):
        for w in self._widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._widgets = []
        # 销毁容器以连带清理内部控件
        try:
            if self._left_container:
                self._left_container.destroy()
        except Exception:
            pass
        try:
            if self._right_container:
                self._right_container.destroy()
        except Exception:
            pass
        self._left_container = None
        self._right_container = None
        self._mounted = False
