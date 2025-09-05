#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from meowauto.midi import groups  # 复用原有分组数据

def create_right_pane(controller, parent_right, *, show_midi_parse: bool = True, show_events: bool = True, show_logs: bool = True):
    """右侧分页：可配置显示 MIDI解析设置 / 事件表 / 系统日志

    参数：
    - show_midi_parse: 是否显示“解析当前MIDI”按钮与“MIDI解析设置”页签
    - show_events: 是否显示“事件表”页签
    - show_logs: 是否显示“系统日志”页签
    """
    # 顶部工具条：解析按钮（可选）
    top_toolbar = ttk.Frame(parent_right)
    top_toolbar.pack(fill=tk.X, pady=(0, 6))
    if show_midi_parse:
        try:
            parse_btn = ttk.Button(top_toolbar, text="解析当前MIDI", command=controller._analyze_current_midi,
                                    style=controller.ui_manager.accent_button_style)
        except Exception:
            parse_btn = ttk.Button(top_toolbar, text="解析当前MIDI", command=controller._analyze_current_midi)
        parse_btn.pack(side=tk.LEFT, padx=6, pady=4)

    notebook = ttk.Notebook(parent_right)
    notebook.pack(fill=tk.BOTH, expand=True)

    # 动态添加各页签
    tab_settings = ttk.Frame(notebook) if show_midi_parse else None
    tab_events = ttk.Frame(notebook) if show_events else None
    tab_logs = ttk.Frame(notebook) if show_logs else None
    if tab_settings is not None:
        notebook.add(tab_settings, text="MIDI解析设置")
    if tab_events is not None:
        notebook.add(tab_events, text="事件表")
    if tab_logs is not None:
        notebook.add(tab_logs, text="系统日志")

    # ========== 设置页（可滚动），仅暴露 analyzer 支持的设置 ==========
    if tab_settings is not None:
        settings_canvas = tk.Canvas(tab_settings, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(tab_settings, orient=tk.VERTICAL, command=settings_canvas.yview)
        settings_inner = ttk.Frame(settings_canvas)
        settings_inner.bind("<Configure>", lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all")))
        settings_canvas.create_window((0, 0), window=settings_inner, anchor="nw")
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 1) 音高分组筛选（与 meowauto.midi.groups 对接）
    if tab_settings is not None:
        grp_frame = ttk.LabelFrame(settings_inner, text="音高分组选择", padding="8")
        grp_frame.pack(fill=tk.X, padx=6, pady=6)
        controller.pitch_group_vars = {}
        
        # 按低音区、中音区、高音区分组，并为每个音区添加全选功能
        bass_section_frame = ttk.Frame(grp_frame)
        bass_section_frame.grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        controller.bass_section_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bass_section_frame, variable=controller.bass_section_var).pack(side=tk.LEFT, padx=(0,2))
        bass_section = ttk.Label(bass_section_frame, text="低音区", font=('微软雅黑', 8, 'bold'))
        bass_section.pack(side=tk.LEFT)
        
        mid_section_frame = ttk.Frame(grp_frame)
        mid_section_frame.grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)
        controller.mid_section_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(mid_section_frame, variable=controller.mid_section_var).pack(side=tk.LEFT, padx=(0,2))
        mid_section = ttk.Label(mid_section_frame, text="中音区", font=('微软雅黑', 8, 'bold'))
        mid_section.pack(side=tk.LEFT)
        
        treble_section_frame = ttk.Frame(grp_frame)
        treble_section_frame.grid(row=0, column=2, sticky=tk.W, padx=4, pady=2)
        controller.treble_section_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(treble_section_frame, variable=controller.treble_section_var).pack(side=tk.LEFT, padx=(0,2))
        treble_section = ttk.Label(treble_section_frame, text="高音区", font=('微软雅黑', 8, 'bold'))
        treble_section.pack(side=tk.LEFT)
        
        # 低音区: 大字二组、大字一组、大字组
        bass_groups = [name for name in groups.ORDERED_GROUP_NAMES if '大字' in name]
        for i, name in enumerate(bass_groups):
            var = tk.BooleanVar(value=True)
            controller.pitch_group_vars[name] = var
            ttk.Checkbutton(grp_frame, text=name, variable=var).grid(row=i+1, column=0, sticky=tk.W, padx=16, pady=2)  # 增加左内边距
        
        # 中音区: 小字组、小字一组、小字二组
        mid_groups = [name for name in groups.ORDERED_GROUP_NAMES if '小字' in name and ('组' in name or '一组' in name or '二组' in name)]
        mid_groups = [g for g in mid_groups if '三组' not in g and '四组' not in g and '五组' not in g]
        for i, name in enumerate(mid_groups):
            var = tk.BooleanVar(value=True)
            controller.pitch_group_vars[name] = var
            ttk.Checkbutton(grp_frame, text=name, variable=var).grid(row=i+1, column=1, sticky=tk.W, padx=16, pady=2)  # 增加左内边距
        
        # 高音区: 小字三组、小字四组、小字五组
        treble_groups = [name for name in groups.ORDERED_GROUP_NAMES if '小字' in name and ('三组' in name or '四组' in name or '五组' in name)]
        for i, name in enumerate(treble_groups):
            var = tk.BooleanVar(value=True)
            controller.pitch_group_vars[name] = var
            ttk.Checkbutton(grp_frame, text=name, variable=var).grid(row=i+1, column=2, sticky=tk.W, padx=16, pady=2)  # 增加左内边距
        
        # 绑定音区全选复选框的事件处理
        def select_bass_section():
            for name in bass_groups:
                controller.pitch_group_vars[name].set(controller.bass_section_var.get())
        
        def select_mid_section():
            for name in mid_groups:
                controller.pitch_group_vars[name].set(controller.mid_section_var.get())
        
        def select_treble_section():
            for name in treble_groups:
                controller.pitch_group_vars[name].set(controller.treble_section_var.get())
        
        controller.bass_section_var.trace_add('write', lambda *args: select_bass_section())
        controller.mid_section_var.trace_add('write', lambda *args: select_mid_section())
        controller.treble_section_var.trace_add('write', lambda *args: select_treble_section())
        
        # 全选/全不选按钮
        btns = ttk.Frame(grp_frame)
        btns.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=6)
        ttk.Button(btns, text="全选", command=lambda: [
            v.set(True) for v in controller.pitch_group_vars.values()
        ] + [
            controller.bass_section_var.set(True),
            controller.mid_section_var.set(True),
            controller.treble_section_var.set(True)
        ]).pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(btns, text="全不选", command=lambda: [
            v.set(False) for v in controller.pitch_group_vars.values()
        ] + [
            controller.bass_section_var.set(False),
            controller.mid_section_var.set(False),
            controller.treble_section_var.set(False)
        ]).pack(side=tk.LEFT)

    # 2) 主旋律提取（与 analyzer.extract_melody 参数对接）
    if tab_settings is not None:
        mel_frame = ttk.LabelFrame(settings_inner, text="主旋律提取", padding="8")
        mel_frame.pack(fill=tk.X, padx=6, pady=6)
        controller.enable_melody_extract_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(mel_frame, text="启用", variable=controller.enable_melody_extract_var).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Label(mel_frame, text="优先通道:").grid(row=0, column=1, sticky=tk.W, padx=(12, 4))
        controller.melody_channel_var = tk.StringVar(value="自动")
        controller.melody_channel_combo = ttk.Combobox(mel_frame, textvariable=controller.melody_channel_var, state="readonly", width=8, values=["自动"]) 
        controller.melody_channel_combo.grid(row=0, column=2, sticky=tk.W, padx=4)
        ttk.Label(mel_frame, text="模式:").grid(row=0, column=3, sticky=tk.W, padx=(12, 4))
        controller.melody_mode_var = tk.StringVar(value='熵启发')
        ttk.Combobox(mel_frame, textvariable=controller.melody_mode_var, state="readonly", width=8,
                     values=['熵启发','节拍过滤','重复过滤','混合']).grid(row=0, column=4, sticky=tk.W)
        ttk.Label(mel_frame, text="强度").grid(row=1, column=0, sticky=tk.W, padx=4)
        controller.melody_strength_var = tk.DoubleVar(value=0.5)
        ttk.Scale(mel_frame, variable=controller.melody_strength_var, from_=0.0, to=1.0, orient=tk.HORIZONTAL, length=160).grid(row=1, column=1, columnspan=2, sticky=tk.W)
        ttk.Label(mel_frame, text="重复惩罚").grid(row=1, column=3, sticky=tk.W, padx=(12, 4))
        controller.melody_rep_penalty_var = tk.DoubleVar(value=1.0)
        ttk.Scale(mel_frame, variable=controller.melody_rep_penalty_var, from_=0.5, to=2.0, orient=tk.HORIZONTAL, length=160).grid(row=1, column=4, sticky=tk.W)
        ttk.Label(mel_frame, text="熵权重").grid(row=2, column=0, sticky=tk.W, padx=4, pady=(6,2))
        controller.entropy_weight_var = tk.DoubleVar(value=0.5)
        ttk.Scale(mel_frame, variable=controller.entropy_weight_var, from_=0.0, to=1.0, orient=tk.HORIZONTAL, length=160).grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(6,2))
        ttk.Label(mel_frame, text="最小得分").grid(row=2, column=3, sticky=tk.W, padx=(12, 4))
        controller.melody_min_score_var = tk.StringVar(value="0.0")
        ttk.Entry(mel_frame, textvariable=controller.melody_min_score_var, width=10).grid(row=2, column=4, sticky=tk.W)

        for i in range(5):
            mel_frame.columnconfigure(i, weight=1)

    # 3) 预处理：整曲移调（自动/手动） -> app._analyze_current_midi 使用
    if tab_settings is not None:
        pre_frame = ttk.LabelFrame(settings_inner, text="预处理 · 整曲移调", padding="8")
        pre_frame.pack(fill=tk.X, padx=6, pady=6)
        controller.enable_preproc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(pre_frame, text="启用预处理", variable=controller.enable_preproc_var).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        controller.pretranspose_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(pre_frame, text="自动选择白键占比最高", variable=controller.pretranspose_auto_var).grid(row=0, column=1, sticky=tk.W, padx=(12,4))
        ttk.Label(pre_frame, text="手动移调(半音):").grid(row=1, column=0, sticky=tk.W, padx=4)
        controller.pretranspose_semitones_var = tk.IntVar(value=0)
        ttk.Spinbox(pre_frame, from_=-12, to=12, increment=1, width=8, textvariable=controller.pretranspose_semitones_var, state='normal').grid(row=1, column=1, sticky=tk.W)
        ttk.Label(pre_frame, text="白键占比:").grid(row=1, column=2, sticky=tk.E, padx=(12,4))
        controller.pretranspose_white_ratio_var = tk.StringVar(value="-")
        ttk.Label(pre_frame, textvariable=controller.pretranspose_white_ratio_var).grid(row=1, column=3, sticky=tk.W)
        for i in range(4):
            pre_frame.columnconfigure(i, weight=1)

    # 4) 后处理：黑键移调 + 量化窗口 -> app._analyze_current_midi 使用
    if tab_settings is not None:
        post_frame = ttk.LabelFrame(settings_inner, text="后处理 · 黑键移调 / 量化", padding="8")
        post_frame.pack(fill=tk.X, padx=6, pady=6)
        controller.enable_postproc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(post_frame, text="启用后处理", variable=controller.enable_postproc_var).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Label(post_frame, text="黑键移调策略:").grid(row=0, column=1, sticky=tk.E, padx=(12,4))
        controller.black_transpose_strategy_var = tk.StringVar(value="向下")
        ttk.Combobox(post_frame, textvariable=controller.black_transpose_strategy_var, state="readonly", width=8,
                     values=["关闭","向下","就近"]).grid(row=0, column=2, sticky=tk.W)
        ttk.Label(post_frame, text="量化窗口(ms):").grid(row=1, column=1, sticky=tk.E, padx=(12,4))
        controller.quantize_window_var = tk.IntVar(value=30)
        ttk.Spinbox(post_frame, from_=1, to=200, increment=1, width=8, textvariable=controller.quantize_window_var).grid(row=1, column=2, sticky=tk.W)
        for i in range(4):
            post_frame.columnconfigure(i, weight=1)

    # 5) 和弦标注（仅用于事件表标注，不影响回放）
    if tab_settings is not None:
        chord_frame = ttk.LabelFrame(settings_inner, text="和弦标注（事件表）", padding="8")
        chord_frame.pack(fill=tk.X, padx=6, pady=6)
        controller.enable_chord_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(chord_frame, text="检测同窗≥2音并标注声部数", variable=controller.enable_chord_var).pack(anchor=tk.W, padx=4)

    # 6) 回放 · 和弦伴奏（下发至 AutoPlayer）。注意：黑键移调仅在“后处理”中提供。
    if tab_settings is not None:
        play_frame = ttk.LabelFrame(settings_inner, text="回放 · 和弦伴奏", padding="8")
        play_frame.pack(fill=tk.X, padx=6, pady=6)
        # 和弦伴奏
        controller.enable_chord_accomp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(play_frame, text="启用和弦伴奏", variable=controller.enable_chord_accomp_var).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Label(play_frame, text="伴奏模式:").grid(row=0, column=1, sticky=tk.E, padx=(12,4))
        controller.chord_accomp_mode_var = tk.StringVar(value='triad')
        ttk.Combobox(play_frame, textvariable=controller.chord_accomp_mode_var, state='readonly', width=10,
                     values=['triad','triad7','greedy']).grid(row=0, column=2, sticky=tk.W)
        ttk.Label(play_frame, text="伴奏最短持续(ms):").grid(row=1, column=1, sticky=tk.E, padx=(12,4))
        controller.chord_accomp_min_sustain_var = tk.IntVar(value=120)
        ttk.Spinbox(play_frame, from_=30, to=1000, increment=10, width=10, textvariable=controller.chord_accomp_min_sustain_var).grid(row=1, column=2, sticky=tk.W)
        # 新增：用和弦键替代主音键（去根音）
        controller.chord_replace_melody_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(play_frame, text="用和弦键替代主音键（去根音）", variable=controller.chord_replace_melody_var).grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        for i in range(3):
            play_frame.columnconfigure(i, weight=1)

    # 当上述与 AutoPlayer 相关变量变化时，实时应用
    def _apply_player_opts_on_change(*_):
        cb = getattr(controller, '_on_player_options_changed', None)
        if cb:
            try:
                cb()
            except Exception:
                pass
    if tab_settings is not None:
        for v in (
            controller.enable_chord_accomp_var,
            controller.chord_accomp_mode_var,
            controller.chord_accomp_min_sustain_var,
            controller.chord_replace_melody_var,
        ):
            try:
                v.trace_add('write', _apply_player_opts_on_change)
            except Exception:
                pass

    # ========== 事件表 ==========
    if tab_events is not None:
        evt_top = ttk.Frame(tab_events)
        evt_top.pack(fill=tk.BOTH, expand=True)
        columns = ("#", "time", "type", "note", "channel", "group", "end", "dur", "chord")
        tree = ttk.Treeview(evt_top, columns=columns, show='headings', height=12)
        headers = ["序号","时间","事件","音符","通道","分组","结束","时长", ""]  # 隐藏和弦列标题
        widths = [60, 100, 80, 80, 80, 80, 100, 100, 0]  # 和弦列宽度设为 0
        for i, col in enumerate(columns):
            tree.heading(col, text=headers[i])
            tree.column(col, width=widths[i], minwidth=0, stretch=False, anchor=tk.CENTER)
        vbar2 = ttk.Scrollbar(evt_top, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vbar2.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar2.pack(side=tk.RIGHT, fill=tk.Y)
        controller.event_tree = tree
        try:
            tree.bind('<Double-1>', controller._on_event_tree_double_click)
        except Exception:
            pass

    # ========== 系统日志 ==========
    if tab_logs is not None:
        log_container = ttk.Frame(tab_logs)
        log_container.pack(fill=tk.BOTH, expand=True)
        log_text = tk.Text(log_container, height=10, wrap=tk.NONE)
        vbar3 = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=vbar3.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar3.pack(side=tk.RIGHT, fill=tk.Y)
        controller.log_text = log_text

    return notebook
