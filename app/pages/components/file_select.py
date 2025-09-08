#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

def create_file_selection(controller, parent_left):
    """构建左侧：文件选择区"""
    target = parent_left
    file_frame = ttk.LabelFrame(target, text="文件选择", padding="12")
    # 使用 pack 布局到父容器，避免与父容器中已使用 pack 的其他组件冲突
    try:
        file_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
    except Exception:
        # 回退：若 pack 不可用则尝试 grid
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(file_frame, text="MIDI文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
    controller.midi_path_var = tk.StringVar()
    # 绑定路径变更钩子（若控制器提供），以便导入后立即计算白键率
    try:
        if hasattr(controller, '_on_midi_path_changed') and callable(controller._on_midi_path_changed):
            controller.midi_path_var.trace_add('write', controller._on_midi_path_changed)
    except Exception:
        pass
    midi_entry = ttk.Entry(file_frame, textvariable=controller.midi_path_var, width=50)
    midi_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
    ttk.Button(file_frame, text="浏览", command=controller._browse_midi).grid(row=0, column=2)

    file_frame.columnconfigure(1, weight=1)
    return file_frame
