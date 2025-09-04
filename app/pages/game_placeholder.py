#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

class GamePlaceholderPage:
    def __init__(self, game_name: str):
        self.game_name = game_name
        self._mounted = False
        self._widgets = []

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        self._mounted = True
        title = ttk.Label(left, text=f"{self.game_name}（占位）", font=("Microsoft YaHei", 14, "bold"))
        title.pack(anchor=tk.NW, padx=10, pady=10)
        desc = ttk.Label(left, text="此处为游戏专属页面的占位，后续将提供键位、适配与说明等。", anchor=tk.W)
        desc.pack(anchor=tk.NW, padx=10, pady=(0, 10))
        self._widgets = [title, desc]

    def unmount(self):
        for w in self._widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._widgets = []
        self._mounted = False
