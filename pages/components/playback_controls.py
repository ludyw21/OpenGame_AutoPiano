#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

def create_playback_controls(controller, parent_left, include_ensemble: bool = True):
    """左侧：播放控制与相关页签。include_ensemble 控制是否呈现合奏项。"""
    control_frame = ttk.LabelFrame(parent_left, text="播放控制", padding="10")
    control_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=6, pady=(0, 10))
    # 确保父容器的 grid 可扩展（列0与行1）
    try:
        parent_left.grid_columnconfigure(0, weight=1)
        parent_left.grid_rowconfigure(1, weight=1)
    except Exception:
        pass

    # 采用更紧凑的顶部栏和分组，使布局更清晰
    notebook = ttk.Notebook(control_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    controller._control_notebook = notebook

    tab_controls = ttk.Frame(notebook)
    tab_ensemble = ttk.Frame(notebook)
    tab_playlist = ttk.Frame(notebook)
    tab_help = ttk.Frame(notebook)

    notebook.add(tab_controls, text="控制")
    if include_ensemble:
        notebook.add(tab_ensemble, text="合奏")
    notebook.add(tab_playlist, text="播放列表")

    # 播放列表：工具栏
    pl_toolbar = ttk.Frame(tab_playlist)
    pl_toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)
    ttk.Button(pl_toolbar, text="添加文件", command=getattr(controller, '_add_to_playlist', lambda: None)).pack(side=tk.LEFT)
    ttk.Button(pl_toolbar, text="导入文件夹", command=getattr(controller, '_import_folder_to_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="移除所选", command=getattr(controller, '_remove_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="清空", command=getattr(controller, '_clear_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="保存列表", command=getattr(controller, '_save_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))

    # 播放列表：播放控制 + 模式选择
    pl_ctrl = ttk.Frame(tab_playlist)
    pl_ctrl.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0,6))
    ttk.Button(pl_ctrl, text="播放所选", command=getattr(controller, '_play_selected_from_playlist', lambda: None)).pack(side=tk.LEFT)
    ttk.Button(pl_ctrl, text="上一首", command=getattr(controller, '_play_prev_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_ctrl, text="下一首", command=getattr(controller, '_play_next_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Label(pl_ctrl, text="播放模式:").pack(side=tk.LEFT, padx=(16,4))
    controller.playlist_mode_var = tk.StringVar(value='顺序')
    mode_combo = ttk.Combobox(pl_ctrl, textvariable=controller.playlist_mode_var, state='readonly', width=10,
                              values=['单曲','顺序','循环','随机'])
    mode_combo.pack(side=tk.LEFT)
    try:
        controller.playlist_mode_var.trace_add('write', lambda *args: getattr(controller, '_on_playlist_mode_changed', lambda *a, **k: None)())
    except Exception:
        pass

    # 播放列表：树表 + 滚动条
    pl_body = ttk.Frame(tab_playlist)
    pl_body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
    columns = ("序号", "文件名", "类型", "时长", "状态")
    tree = ttk.Treeview(pl_body, columns=columns, show='headings', height=8)
    headers = ["序号", "文件名", "类型", "时长", "状态"]
    widths = [60, 340, 80, 80, 80]
    for i, col in enumerate(columns):
        tree.heading(col, text=headers[i])
        tree.column(col, width=widths[i], anchor=tk.W if i in (1,) else tk.CENTER)
    vbar = ttk.Scrollbar(pl_body, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=vbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 将句柄挂到 controller，供 app 工作流使用
    controller.playlist_tree = tree
    if not hasattr(controller, '_file_paths') or not isinstance(getattr(controller, '_file_paths'), dict):
        controller._file_paths = {}
    # 帮助页签内容
    help_inner = ttk.Frame(tab_help)
    help_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    help_text = (
        "热键说明:\n"
        "• 空格: 开始/暂停/恢复\n"
        "• ESC: 停止\n"
        "• Ctrl+S: 停止自动演奏\n"
        "• Ctrl+Shift+C: 停止所有播放\n"
        "• Ctrl+T: 切换主题\n"
        "• Ctrl+D: 切换控件密度\n\n"
        "使用说明:\n"
        "1. 选择音频文件 → 点击\"音频转MIDI\"\n"
        "2. 选择MIDI文件 → 点击\"解析当前MIDI\"\n"
        "3. 设置演奏模式和参数（回放模式、倒计时、和弦伴奏等）\n"
        "4. 点击\"自动弹琴\"开始演奏；或在播放列表选中后使用\"播放所选/上一首/下一首\"\n"
    )
    ttk.Label(help_inner, text=help_text, justify=tk.LEFT, wraplength=520).pack(anchor=tk.W)
    notebook.add(tab_help, text="帮助")

    # 控制页（简化，委托 controller 原有回调）
    mode_frame = ttk.Frame(tab_controls)
    mode_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 6))
    ttk.Label(mode_frame, text="演奏模式:").pack(side=tk.LEFT, padx=(0, 12))
    controller.playback_mode = tk.StringVar(value="midi")
    ttk.Radiobutton(mode_frame, text="MIDI模式", variable=controller.playback_mode, value="midi", command=controller._on_mode_changed).pack(side=tk.LEFT, padx=(0, 12))

    # 速度（保留倍速控件，删除音量）
    av_frame = ttk.LabelFrame(tab_controls, text="速度设置", padding="8")
    av_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
    ttk.Label(av_frame, text="倍速:").pack(side=tk.LEFT)
    controller.tempo_var = tk.DoubleVar(value=1.0)
    ttk.Spinbox(av_frame, from_=0.25, to=3.0, increment=0.05, textvariable=controller.tempo_var, width=6).pack(side=tk.LEFT, padx=(6, 12))

    button_frame = ttk.LabelFrame(tab_controls, text="操作", padding="8")
    button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
    controller._create_auto_play_controls(button_frame)
    btn_row = ttk.Frame(button_frame)
    btn_row.pack(side=tk.TOP, anchor=tk.W, pady=(6,0))
    ttk.Button(btn_row, text="播放MIDI", command=controller._play_midi).pack(side=tk.LEFT)
    try:
        ttk.Button(btn_row, text="停止", command=controller._stop_playback, style=getattr(controller.ui_manager, 'accent_button_style', 'TButton')).pack(side=tk.LEFT, padx=(8,0))
    except Exception:
        ttk.Button(btn_row, text="停止", command=controller._stop_playback).pack(side=tk.LEFT, padx=(8,0))
    # 快捷键提示
    hint = ttk.Label(button_frame, text="快捷键: 空格=暂停/恢复, ESC=停止, Ctrl+S=停止自动演奏", foreground="#666")
    hint.pack(side=tk.TOP, anchor=tk.W, pady=(6,0))

    # 合奏相关（可选）
    if include_ensemble:
        ensemble_frame = ttk.Frame(tab_controls)
        ensemble_frame.pack(side=tk.TOP, anchor=tk.W, pady=(6, 0))
        controller._ensemble_label = ttk.Label(ensemble_frame, text="合奏模式:")
        controller._ensemble_label.pack(side=tk.LEFT)
        controller.ensemble_mode_var = tk.StringVar(value='ensemble')
        ttk.Radiobutton(ensemble_frame, text="大合奏", variable=controller.ensemble_mode_var, value='ensemble').pack(side=tk.LEFT, padx=(6, 0))
        ttk.Radiobutton(ensemble_frame, text="独奏", variable=controller.ensemble_mode_var, value='solo').pack(side=tk.LEFT, padx=(6, 12))
        controller._role_label = ttk.Label(ensemble_frame, text="我的角色:")
        controller._role_label.pack(side=tk.LEFT)
        controller.my_role_var = tk.StringVar(value='melody')
        controller.my_role_display_var = tk.StringVar(value='旋律')
        controller._role_cn2en = {"旋律": "melody", "吉他": "guitar", "贝斯": "bass", "鼓": "drums"}
        controller._role_en2cn = {v: k for k, v in controller._role_cn2en.items()}
        controller._my_role_combo = ttk.Combobox(ensemble_frame, textvariable=controller.my_role_display_var, state="readonly", width=8,
                                               values=list(controller._role_cn2en.keys()))
        def _on_my_role_select(event=None):
            try:
                cn = controller.my_role_display_var.get()
                en = controller._role_cn2en.get(cn, 'melody')
                controller.my_role_var.set(en)
            except Exception:
                pass
        controller._my_role_combo.bind('<<ComboboxSelected>>', _on_my_role_select)
        controller._my_role_combo.pack(side=tk.LEFT)
        try:
            controller.ensemble_mode_var.trace_add("write", lambda *args: controller._on_ensemble_mode_changed())
        except Exception:
            pass
        controller._ensemble_controls_row = ensemble_frame

        # 保存合奏页签引用，便于外部显隐
        controller._tab_ensemble = tab_ensemble

        # 在“合奏”页签中添加三块功能：计划 / 对时 / 统一开始
        # 1) 计划开始
        plan_frame = ttk.LabelFrame(tab_ensemble, text="计划开始", padding="8")
        plan_frame.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Label(plan_frame, text="延时(秒):").grid(row=0, column=0, sticky=tk.W)
        controller.ensemble_delay_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(plan_frame, from_=0.0, to=600.0, increment=0.5, textvariable=controller.ensemble_delay_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=(6, 12))
        ttk.Button(plan_frame, text="计划开始", command=lambda: getattr(controller, '_ensemble_plan_start', lambda: None)()).grid(row=0, column=2, sticky=tk.W)
        for i in range(3):
            plan_frame.columnconfigure(i, weight=1)

        # 2) 对时
        sync_frame = ttk.LabelFrame(tab_ensemble, text="对时", padding="8")
        sync_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(sync_frame, text="启用公网对时", command=lambda: getattr(controller, '_enable_network_clock', lambda: None)()).grid(row=0, column=0, sticky=tk.W)
        ttk.Button(sync_frame, text="手动对时", command=lambda: getattr(controller, '_sync_network_clock', lambda: None)()).grid(row=0, column=1, sticky=tk.W, padx=(12, 0))
        ttk.Button(sync_frame, text="切回本地时钟", command=lambda: getattr(controller, '_use_local_clock', lambda: None)()).grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        for i in range(3):
            sync_frame.columnconfigure(i, weight=1)

        # 3) 统一开始
        start_frame = ttk.LabelFrame(tab_ensemble, text="统一开始", padding="8")
        start_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(start_frame, text="倒计时(秒):").grid(row=0, column=0, sticky=tk.W)
        controller.ensemble_countdown_var = tk.IntVar(value=3)
        ttk.Spinbox(start_frame, from_=0, to=30, textvariable=controller.ensemble_countdown_var, width=6).grid(row=0, column=1, sticky=tk.W, padx=(6, 12))
        controller.ensemble_use_analyzed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(start_frame, text="使用右侧解析事件", variable=controller.ensemble_use_analyzed_var).grid(row=0, column=2, sticky=tk.W)
        ttk.Button(start_frame, text="统一开始", command=lambda: getattr(controller, '_ensemble_unified_start', lambda: None)()).grid(row=0, column=3, sticky=tk.W, padx=(12,0))
        for i in range(4):
            start_frame.columnconfigure(i, weight=1)

    return notebook
