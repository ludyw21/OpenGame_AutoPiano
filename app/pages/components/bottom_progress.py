#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

def create_bottom_progress(controller, parent_left):
    """左下角：播放进度"""
    bottom = ttk.Frame(parent_left)
    bottom.grid(row=3, column=0, sticky=(tk.W, tk.E))
    controller.time_pos_var = tk.StringVar(value="00:00")
    ttk.Label(bottom, textvariable=controller.time_pos_var).pack(side=tk.LEFT)
    ttk.Label(bottom, text=" | ").pack(side=tk.LEFT)
    controller.time_total_var = tk.StringVar(value="00:00")
    ttk.Label(bottom, textvariable=controller.time_total_var).pack(side=tk.LEFT)
    return bottom
