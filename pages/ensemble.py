#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

class EnsemblePage:
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
        # 左侧：纵向滚动容器（仅放合奏相关控件）
        self._left_container = ttk.Frame(left)
        self._left_container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(self._left_container, highlightthickness=0)
        vbar = ttk.Scrollbar(self._left_container, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_inner_config(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass
        inner.bind('<Configure>', _on_inner_config)

        # 右侧：留空简单提示
        self._right_container = ttk.Frame(right)
        self._right_container.pack(fill=tk.BOTH, expand=True)
        tip = ttk.Label(self._right_container, text="合奏页已简化（无复杂右侧面板）", anchor=tk.CENTER, foreground="#666")
        tip.pack(padx=8, pady=8)

        # 通过控制器仅构建合奏相关控件，并隐藏其他页签
        if self.controller:
            try:
                self.controller._create_playback_control_component(parent_left=inner, include_ensemble=True)
                # 隐藏除“合奏”外的所有页签
                nb = getattr(self.controller, '_control_notebook', None)
                if nb is not None:
                    for tab_id in nb.tabs():
                        try:
                            text = nb.tab(tab_id, 'text')
                            if text != '合奏':
                                nb.hide(tab_id)
                        except Exception:
                            pass
            except Exception:
                lf = ttk.Label(inner, text="合奏模式（加载失败占位）", anchor=tk.W)
                lf.pack(anchor=tk.NW, padx=6, pady=6)
                self._widgets = [lf, tip]
        else:
            # 无控制器：使用占位
            lf = ttk.Label(inner, text="合奏模式（占位）", anchor=tk.W)
            lf.pack(anchor=tk.NW, padx=6, pady=6)
            self._widgets = [lf, tip]

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
