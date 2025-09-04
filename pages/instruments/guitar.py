#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
吉他页面（占位）：后续补充实际功能与控件。
当前仅搭建左右区域的基本结构，确保可安全装载/卸载。
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
        # 左侧占位
        header = ttk.Frame(left)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="吉他 · 占位页面", font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)
        ttk.Label(left, text="此板块功能尚未实现，后续将逐步补充。").pack(anchor=tk.W)

        # 右侧：统一使用控制器提供的右侧分页
        try:
            self.controller._create_right_pane(right)
        except Exception:
            ttk.Label(right, text="日志/状态区（预留）").pack(anchor=tk.NW, padx=6, pady=6)
        self._mounted = True

    def unmount(self):
        self._mounted = False
