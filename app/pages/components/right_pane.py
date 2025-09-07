#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from meowauto.midi import groups  # 复用原有分组数据

def create_right_pane_component(controller, parent_right, *, show_midi_parse: bool = True, show_events: bool = True, show_logs: bool = True, instrument: str = None):
    """右侧分页：可配置显示 MIDI解析设置 / 事件表 / 系统日志

    参数：
    - show_midi_parse: 是否显示“解析当前MIDI”按钮与“MIDI解析设置”页签
    - show_events: 是否显示“事件表”页签
    - show_logs: 是否显示“系统日志”页签
    - instrument: 乐器类型（可选）
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

    # ========== 设置页（受主页面滚动条控制），仅暴露 analyzer 支持的设置 ==========
    if tab_settings is not None:
        settings_inner = ttk.Frame(tab_settings)
        settings_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 1) 音高分组选择功能已移除，初始化默认值
    if tab_settings is not None:
        controller.pitch_group_vars = {}
        # 为所有分组设置默认值为 True（全选）
        for name in groups.ORDERED_GROUP_NAMES:
            var = tk.BooleanVar(value=True)
            controller.pitch_group_vars[name] = var

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

    # 5) 和弦标注功能已移除，避免混淆
    if tab_settings is not None:
        # 为所有乐器设置默认禁用值
        controller.enable_chord_var = tk.BooleanVar(value=False)

    # 6) 回放 · 和弦伴奏（下发至 AutoPlayer）。注意：黑键移调仅在"后处理"中提供。
    # 仅架子鼓禁用和弦功能；其他乐器可用
    current_instrument = (instrument or '').strip()
    show_chord_accomp = current_instrument not in ('架子鼓',)
    if tab_settings is not None and show_chord_accomp:
        play_frame = ttk.LabelFrame(settings_inner, text="回放 · 和弦伴奏", padding="8")
        play_frame.pack(fill=tk.X, padx=6, pady=6)
        # 和弦伴奏
        controller.enable_chord_accomp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(play_frame, text="启用和弦伴奏", variable=controller.enable_chord_accomp_var).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Label(play_frame, text="和弦最短持续(ms):").grid(row=1, column=1, sticky=tk.E, padx=(12,4))
        controller.chord_min_sustain_ms_var = tk.IntVar(value=1500)
        ttk.Spinbox(play_frame, from_=100, to=5000, increment=50, width=10, textvariable=controller.chord_min_sustain_ms_var).grid(row=1, column=2, sticky=tk.W)
        ttk.Label(play_frame, text="块和弦窗口(ms):").grid(row=2, column=2, sticky=tk.E, padx=(12,4))
        controller.chord_block_window_ms_var = tk.IntVar(value=50)
        ttk.Spinbox(play_frame, from_=0, to=200, increment=5, width=10, textvariable=controller.chord_block_window_ms_var).grid(row=2, column=3, sticky=tk.W)
        controller.chord_replace_melody_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(play_frame, text="用和弦键替代主音键（去根音）", variable=controller.chord_replace_melody_var).grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        for i in range(4):
            play_frame.columnconfigure(i, weight=1)

    # 7) 架子鼓禁用和弦（兜底设置）
    if tab_settings is not None and not show_chord_accomp:
        # 为贝斯和架子鼓设置默认值（禁用和弦）
        controller.chord_min_sustain_ms_var = tk.IntVar(value=1500)
        controller.chord_replace_melody_var = tk.BooleanVar(value=False)
        controller.chord_block_window_ms_var = tk.IntVar(value=50)

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
            controller.chord_min_sustain_ms_var,
            controller.chord_replace_melody_var,
            controller.chord_block_window_ms_var,
        ):
            try:
                v.trace_add('write', _apply_player_opts_on_change)
            except Exception:
                pass
        # 多键相关设置已从“MIDI解析设置”中移除

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
