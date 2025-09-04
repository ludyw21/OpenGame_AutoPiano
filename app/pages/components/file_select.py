#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

def create_file_selection(controller, parent_left):
    """构建左侧：文件选择区"""
    target = parent_left
    file_frame = ttk.LabelFrame(target, text="文件选择", padding="12")
    file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(file_frame, text="MIDI文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
    controller.midi_path_var = tk.StringVar()
    midi_entry = ttk.Entry(file_frame, textvariable=controller.midi_path_var, width=50)
    midi_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
    ttk.Button(file_frame, text="浏览", command=controller._browse_midi).grid(row=0, column=2)

    file_frame.columnconfigure(1, weight=1)
    return file_frame
