#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
try:
    # 嵌入右侧解析面板至左侧分页
    from pages.components.right_pane import create_right_pane as create_right_pane_component  # type: ignore
except Exception:
    create_right_pane_component = None  # 回退
try:
    import ttkbootstrap as ttkb  # 颜色友好
except Exception:
    ttkb = None


def _init_button_styles(root: tk.Misc | None = None) -> dict:
    """初始化一套较大尺寸的彩色按钮风格，返回风格名映射。"""
    style = ttk.Style(root)
    # 统一大按钮字体与内边距
    # 调整为适中尺寸（较默认放大，但小于之前的2倍）
    base = dict(font=("Segoe UI", 14, "bold"), padding=(12, 8))
    # 定义自有命名空间，避免与外部样式冲突
    styles = {
        'primary': 'MF.Primary.TButton',
        'success': 'MF.Success.TButton',
        'danger': 'MF.Danger.TButton',
        'warning': 'MF.Warning.TButton',
        'info': 'MF.Info.TButton',
        'secondary': 'MF.Secondary.TButton',
    }
    # 颜色在原生 ttk 下可能不完全生效，但字体/尺寸会生效；ttkbootstrap 下使用主题色
    for key, sname in styles.items():
        style.configure(sname, **base)
    # 背景色（尽力在原生 ttk 下生效；若无效则依赖 ttkbootstrap 或系统主题近似）
    try:
        style.configure('MF.Primary.TButton', foreground='white', background='#0A84FF')
        style.map('MF.Primary.TButton', background=[('active', '#0A6DFF'), ('pressed', '#095EC8')])
        style.configure('MF.Secondary.TButton', foreground='#0A84FF', background='#E6F0FF')
        style.map('MF.Secondary.TButton', background=[('active', '#D9E8FF'), ('pressed', '#C8DCFF')])
    except Exception:
        pass
    # Win11 强调色映射：hover/active/selected 前景变蓝
    try:
        accent = '#0A84FF'
        # 扁平化风格：无描边
        for s in ('MF.Primary.TButton','MF.Secondary.TButton','MF.Success.TButton','MF.Danger.TButton','MF.Warning.TButton','MF.Info.TButton'):
            style.configure(s, relief='flat', borderwidth=0)
        style.map('MF.Primary.TButton', foreground=[('active', accent), ('pressed', accent)])
        style.map('MF.Secondary.TButton', foreground=[('active', accent), ('pressed', accent)])
        style.configure('MF.Success.TButton', background='#22C55E', foreground='white')
        style.map('MF.Success.TButton', background=[('active', '#16A34A'), ('pressed', '#15803D')])
        style.configure('MF.Danger.TButton', background='#EF4444', foreground='white')
        style.map('MF.Danger.TButton', background=[('active', '#DC2626'), ('pressed', '#B91C1C')])
        style.configure('MF.Warning.TButton', background='#F59E0B', foreground='black')
        style.map('MF.Warning.TButton', background=[('active', '#D97706'), ('pressed', '#B45309')])
        style.configure('MF.Info.TButton', background='#38BDF8', foreground='white')
        style.map('MF.Info.TButton', background=[('active', '#0EA5E9'), ('pressed', '#0284C7')])
    except Exception:
        pass
    return styles

def create_playback_controls(controller, parent_left, include_ensemble: bool = True, instrument: str | None = None):
    """左侧：顶部为横向大按钮切换分页，下面为对应内容区域（整页滚动）。
    注意：使用 pack 作为最外层布局，避免与父容器 pack 混用冲突。
    """

    styles = _init_button_styles(getattr(controller, 'root', None))

    # 顶部：横向大按钮作为分页切换
    tabbar = ttk.Frame(parent_left)
    tabbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))
    # 三列：左右为弹性空白，中间居中放按钮
    try:
        tabbar.grid_columnconfigure(0, weight=1)
        tabbar.grid_columnconfigure(1, weight=0)
        tabbar.grid_columnconfigure(2, weight=1)
    except Exception:
        pass
    center_bar = ttk.Frame(tabbar)
    center_bar.grid(row=0, column=1)
    # 内容容器：放入单一滚动外壳（整页滚动，顶部按钮固定）
    scroll_shell = ttk.Frame(parent_left)
    scroll_shell.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    vbar = ttk.Scrollbar(scroll_shell, orient=tk.VERTICAL)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas = tk.Canvas(scroll_shell, highlightthickness=0, bg='white')
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.configure(command=canvas.yview)
    content_host = ttk.Frame(canvas, padding=(10, 10))
    content_window = canvas.create_window((0, 0), window=content_host, anchor='nw')
    try:
        # 先执行一次布局计算，确保初始宽高非零
        canvas.update_idletasks()
        w = max(1, canvas.winfo_width())
        canvas.itemconfigure(content_window, width=w)
        bbox = canvas.bbox('all')
        if bbox:
            canvas.configure(scrollregion=bbox)
    except Exception:
        pass
    def _on_content_configure(event=None):
        try:
            bbox = canvas.bbox('all')
            if bbox:
                canvas.configure(scrollregion=bbox)
        except Exception:
            pass
    def _on_shell_configure(event=None):
        try:
            w = canvas.winfo_width()
            canvas.itemconfigure(content_window, width=w)
        except Exception:
            pass
    content_host.bind('<Configure>', _on_content_configure)
    canvas.bind('<Configure>', _on_shell_configure)
    try:
        # 立即触发一次宽度同步，避免初次渲染时内容区域宽度为0导致不可见
        if hasattr(controller, 'root') and controller.root:
            controller.root.after(0, _on_shell_configure)
    except Exception:
        pass
    # 鼠标滚轮控制整页滚动（Windows）
    def _on_mouse_wheel(event):
        try:
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, 'units')
        except Exception:
            pass
    canvas.bind_all('<MouseWheel>', _on_mouse_wheel)

    # 定义各分页内容帧（解析/事件/日志 拆分为三个独立分页）
    tab_controls = ttk.Frame(content_host)
    tab_ensemble = ttk.Frame(content_host)
    tab_playlist = ttk.Frame(content_host)
    tab_parse = ttk.Frame(content_host)
    tab_events = ttk.Frame(content_host)
    tab_logs = ttk.Frame(content_host)
    tab_help = ttk.Frame(content_host)

    # 先切换到“控制”以确保初次就有内容显示
    # 实际子内容稍后添加
    try:
        tab_controls.pack(fill=tk.BOTH, expand=True)
    except Exception:
        pass

    # 工具函数：切换显示帧
    def switch_tab(name: str):
        for f in (tab_controls, tab_ensemble, tab_playlist, tab_parse, tab_events, tab_logs, tab_help):
            f.pack_forget()
        if name == 'controls':
            tab_controls.pack(fill=tk.BOTH, expand=True)
        elif name == 'ensemble' and include_ensemble:
            tab_ensemble.pack(fill=tk.BOTH, expand=True)
        elif name == 'playlist':
            tab_playlist.pack(fill=tk.BOTH, expand=True)
        elif name == 'parse':
            tab_parse.pack(fill=tk.BOTH, expand=True)
        elif name == 'events':
            tab_events.pack(fill=tk.BOTH, expand=True)
        elif name == 'logs':
            tab_logs.pack(fill=tk.BOTH, expand=True)
        elif name == 'help':
            tab_help.pack(fill=tk.BOTH, expand=True)
        # 更新按钮激活样式（简化为 primary 表示激活）
        btn_map = {
            'controls': btn_controls,
            'ensemble': btn_ensemble if include_ensemble else None,
            'playlist': btn_playlist,
            'parse': btn_parse_btn,
            'events': btn_events_btn,
            'logs': btn_logs_btn,
            'help': btn_help,
        }
        for key, btn in btn_map.items():
            if not btn:
                continue
            btn.configure(style=styles['primary'] if key == name else styles['secondary'])

    # 创建按钮
    btn_controls = ttk.Button(center_bar, text="控制", style=styles['primary'], command=lambda: switch_tab('controls'))
    btn_controls.pack(side=tk.LEFT, padx=(0, 12))
    if include_ensemble:
        btn_ensemble = ttk.Button(center_bar, text="合奏", style=styles['secondary'], command=lambda: switch_tab('ensemble'))
        btn_ensemble.pack(side=tk.LEFT, padx=(0, 12))
    btn_playlist = ttk.Button(center_bar, text="播放列表", style=styles['secondary'], command=lambda: switch_tab('playlist'))
    btn_playlist.pack(side=tk.LEFT, padx=(0, 12))
    btn_parse_btn = ttk.Button(center_bar, text="解析", style=styles['secondary'], command=lambda: switch_tab('parse'))
    btn_parse_btn.pack(side=tk.LEFT, padx=(0, 12))
    btn_events_btn = ttk.Button(center_bar, text="事件表", style=styles['secondary'], command=lambda: switch_tab('events'))
    btn_events_btn.pack(side=tk.LEFT, padx=(0, 12))
    btn_logs_btn = ttk.Button(center_bar, text="日志", style=styles['secondary'], command=lambda: switch_tab('logs'))
    btn_logs_btn.pack(side=tk.LEFT, padx=(0, 12))
    btn_help = ttk.Button(center_bar, text="帮助", style=styles['secondary'], command=lambda: switch_tab('help'))
    btn_help.pack(side=tk.LEFT, padx=(0, 12))

    # 播放列表：工具栏（大按钮 + 颜色）
    pl_toolbar = ttk.Frame(tab_playlist)
    pl_toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)
    ttk.Button(pl_toolbar, text="添加文件", style=styles['primary'], command=getattr(controller, '_add_to_playlist', lambda: None)).pack(side=tk.LEFT)
    ttk.Button(pl_toolbar, text="导入文件夹", style=styles['info'], command=getattr(controller, '_import_folder_to_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="移除所选", style=styles['warning'], command=getattr(controller, '_remove_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="清空", style=styles['danger'], command=getattr(controller, '_clear_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_toolbar, text="保存列表", style=styles['secondary'], command=getattr(controller, '_save_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))

    # 播放列表：播放控制 + 模式选择
    pl_ctrl = ttk.Frame(tab_playlist)
    pl_ctrl.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0,6))
    ttk.Button(pl_ctrl, text="播放所选", style=styles['success'], command=getattr(controller, '_play_selected_from_playlist', lambda: None)).pack(side=tk.LEFT)
    ttk.Button(pl_ctrl, text="上一首", style=styles['secondary'], command=getattr(controller, '_play_prev_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(pl_ctrl, text="下一首", style=styles['secondary'], command=getattr(controller, '_play_next_from_playlist', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
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
    # 在“解析/事件/日志”三页中分别嵌入原组件的对应部分
    try:
        from pages.components.right_pane import create_right_pane_component
        if create_right_pane_component:
            # 解析页：仅MIDI解析设置，传递乐器类型
            create_right_pane_component(controller, tab_parse, show_midi_parse=True, show_events=False, show_logs=False, instrument=instrument)
            # 事件表页：仅事件表，传递乐器类型
            create_right_pane_component(controller, tab_events, show_midi_parse=False, show_events=True, show_logs=False, instrument=instrument)
            # 日志页：仅日志
            create_right_pane_component(controller, tab_logs, show_midi_parse=False, show_events=False, show_logs=True, instrument=instrument)
    except Exception:
        pass

    # 统一解析设置（自动移调/手动半音/最短音长阈值）—— 强制绑定到 PlaybackService
    try:
        parse_settings = ttk.LabelFrame(tab_parse, text="解析设置（统一管线）", padding="10")
        parse_settings.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 10))

        # 变量定义并挂到 controller（便于外部读取）
        controller.auto_transpose_enabled_var = tk.BooleanVar(value=True)
        controller.manual_transpose_semi_var = tk.IntVar(value=0)
        controller.min_note_duration_ms_var = tk.IntVar(value=25)

        # 自动移调
        ttk.Checkbutton(parse_settings, text="自动选择白键率最高的整体移调", variable=controller.auto_transpose_enabled_var).grid(row=0, column=0, sticky=tk.W, columnspan=3)

        # 手动移调半音（当自动关闭时才生效）
        ttk.Label(parse_settings, text="手动移调(半音):").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        spin_manual = ttk.Spinbox(parse_settings, from_=-12, to=12, increment=1, textvariable=controller.manual_transpose_semi_var, width=8)
        spin_manual.grid(row=1, column=1, sticky=tk.W, padx=(6, 16), pady=(6,0))
        # 最短音长阈值
        ttk.Label(parse_settings, text="最短音长阈值(ms): 小于该值的音符将被丢弃").grid(row=1, column=2, sticky=tk.W, pady=(6,0))
        spin_minms = ttk.Spinbox(parse_settings, from_=0, to=2000, increment=10, textvariable=controller.min_note_duration_ms_var, width=8)
        spin_minms.grid(row=1, column=3, sticky=tk.W, padx=(6, 0), pady=(6,0))

        # 白键率显示与计算
        controller.transpose_k_var = tk.StringVar(value="k: 0")
        controller.white_rate_var = tk.StringVar(value="白键率: -")
        k_label = ttk.Label(parse_settings, textvariable=controller.transpose_k_var)
        k_label.grid(row=2, column=0, sticky=tk.W, pady=(8,0))
        rate_label = ttk.Label(parse_settings, textvariable=controller.white_rate_var)
        rate_label.grid(row=2, column=1, sticky=tk.W, pady=(8,0))

        def _refresh_white_rate_from_service():
            try:
                ps = getattr(controller, 'playback_service', None)
                if not ps or not hasattr(ps, 'get_last_analysis_stats'):
                    return
                st = ps.get_last_analysis_stats() or {}
                k = int(st.get('k') or 0)
                rate = st.get('white_rate')
                controller.transpose_k_var.set(f"k: {k:+d}")
                controller.white_rate_var.set(f"白键率: {rate:.3f}" if isinstance(rate, (int, float)) else "白键率: -")
            except Exception:
                pass

        # 计算作业ID用于防抖
        controller._calc_white_rate_job = None

        def _compute_white_rate_now():
            """立即基于当前文件与设置计算白键率（不启动播放）。"""
            try:
                from meowauto.midi import analyzer as _an
                ps = getattr(controller, 'playback_service', None)
                if not ps:
                    return
                # 读取当前文件
                midi_path = getattr(controller, 'midi_path_var', None).get() if hasattr(controller, 'midi_path_var') else ''
                if not midi_path:
                    return
                res = _an.parse_midi(midi_path)
                if not isinstance(res, dict) or not res.get('ok'):
                    return
                notes = res.get('notes') or []
                # 若存在分部选择，则按所选分部进行事件级过滤（不绕过统一流程）
                try:
                    sel = getattr(controller, '_selected_part_names', set()) or set()
                    parts = getattr(controller, '_last_split_parts', {}) or {}
                    if sel and parts and notes:
                        # 收集选中分部的 (track, channel) 组合（program 作为加权条件）
                        sel_keys = set()
                        prog_map = {}
                        for name in sel:
                            sec = parts.get(name)
                            if not sec:
                                continue
                            meta = getattr(sec, 'meta', {}) if hasattr(sec, 'meta') else (sec.get('meta', {}) if isinstance(sec, dict) else {})
                            tr = meta.get('track'); ch = meta.get('channel'); pg = meta.get('program')
                            if tr is None or ch is None:
                                continue
                            sel_keys.add((int(tr), int(ch)))
                            if pg is not None:
                                prog_map[(int(tr), int(ch))] = int(pg)
                        if sel_keys:
                            def _keep(n):
                                try:
                                    t = int(n.get('track'))
                                    c = int(n.get('channel'))
                                    if (t, c) not in sel_keys:
                                        return False
                                    p_need = prog_map.get((t, c))
                                    if p_need is None:
                                        return True
                                    p_has = n.get('program')
                                    return (p_has is None) or int(p_has) == int(p_need)
                                except Exception:
                                    return False
                            filtered = [n for n in notes if _keep(n)]
                            # 若过滤后为空，为避免“无声”误伤，回退为原notes；同时打印提示
                            if filtered:
                                notes = filtered
                                try:
                                    controller._log_message(f"[DEBUG] 分部过滤: 选择{len(sel)}个分部，保留事件 {len(notes)} 条", "DEBUG")
                                except Exception:
                                    pass
                            else:
                                try:
                                    controller._log_message("[DEBUG] 分部过滤结果为空，回退为全曲事件", "WARN")
                                except Exception:
                                    pass
                except Exception:
                    pass
                # 应用当前设置（调用服务内部预处理计算统计）
                if hasattr(ps, '_apply_pre_filters_and_transpose'):
                    processed = ps._apply_pre_filters_and_transpose(notes)  # 计算并更新 last_analysis_stats
                    # 将预处理后的事件缓存到控制器，供“使用已解析结果播放”直接命中
                    try:
                        controller.analysis_notes = list(processed)
                        controller.analysis_file = midi_path
                        controller._log_message(f"[DEBUG] 已缓存解析事件: {len(controller.analysis_notes)} 条", "DEBUG")
                    except Exception:
                        pass
                _refresh_white_rate_from_service()
            except Exception:
                pass

        def _schedule_compute_white_rate(delay_ms: int = 300):
            """防抖调度白键率计算，避免频繁重算。"""
            try:
                if hasattr(controller, 'root') and getattr(controller, 'root', None):
                    if getattr(controller, '_calc_white_rate_job', None):
                        try:
                            controller.root.after_cancel(controller._calc_white_rate_job)
                        except Exception:
                            pass
                    controller._calc_white_rate_job = controller.root.after(delay_ms, _compute_white_rate_now)
                else:
                    _compute_white_rate_now()
            except Exception:
                pass

        # 暴露给 controller，供其他组件安全调用
        try:
            controller._compute_white_rate_now = _compute_white_rate_now
            controller._schedule_compute_white_rate = _schedule_compute_white_rate
        except Exception:
            pass

        ttk.Button(parse_settings, text="计算白键率", command=_compute_white_rate_now).grid(row=2, column=2, sticky=tk.W, pady=(8,0))

        for c in range(4):
            try:
                parse_settings.grid_columnconfigure(c, weight=1)
            except Exception:
                pass

        # 解析引擎选择（自动/pretty_midi/miditoolkit）
        try:
            ttk.Label(parse_settings, text="解析引擎:").grid(row=3, column=0, sticky=tk.W, pady=(8,0))
            controller._engine_label_to_value = {'自动': 'auto', 'pretty_midi': 'pretty_midi', 'miditoolkit': 'miditoolkit'}
            controller._engine_value_to_label = {v: k for k, v in controller._engine_label_to_value.items()}
            controller.parser_engine_var = tk.StringVar(value='miditoolkit')
            engine_combo = ttk.Combobox(parse_settings, textvariable=controller.parser_engine_var, state='readonly', width=14,
                                        values=list(controller._engine_label_to_value.keys()))
            engine_combo.grid(row=3, column=1, sticky=tk.W)

            def _on_engine_changed(*args):
                try:
                    from meowauto.midi import analyzer as _an
                    label = controller.parser_engine_var.get()
                    value = controller._engine_label_to_value.get(label, 'miditoolkit')
                    if hasattr(_an, 'set_default_engine'):
                        _an.set_default_engine(value)
                    # 记录日志
                    try:
                        controller._log_message(f"解析引擎已切换为: {label} ({value})", "INFO")
                    except Exception:
                        pass
                    # 引擎改变后，重新计算白键率
                    try:
                        (getattr(controller, '_schedule_compute_white_rate', None) or _schedule_compute_white_rate)(100)
                    except Exception:
                        _schedule_compute_white_rate(100)
                except Exception:
                    pass

            controller.parser_engine_var.trace_add('write', _on_engine_changed)
            # 初始化执行一次，确保默认引擎生效
            _on_engine_changed()
        except Exception:
            pass

        def _sync_analysis_settings(*args, **kwargs):
            try:
                ps = getattr(controller, 'playback_service', None)
                if ps and hasattr(ps, 'configure_analysis_settings'):
                    ps.configure_analysis_settings(
                        auto_transpose=bool(controller.auto_transpose_enabled_var.get()),
                        manual_semitones=int(controller.manual_transpose_semi_var.get()),
                        min_note_duration_ms=int(controller.min_note_duration_ms_var.get()),
                    )
                # 自动模式下禁用手动输入
                try:
                    if bool(controller.auto_transpose_enabled_var.get()):
                        spin_manual.configure(state='disabled')
                    else:
                        spin_manual.configure(state='normal')
                except Exception:
                    pass
                # 自动触发一次“白键率计算”（防抖），做到每次设置变更即计算并刷新显示
                try:
                    (getattr(controller, '_schedule_compute_white_rate', None) or _schedule_compute_white_rate)(300)
                except Exception:
                    _schedule_compute_white_rate(300)
            except Exception:
                pass

        # 绑定变化事件（即改即生效）
        try:
            controller.auto_transpose_enabled_var.trace_add('write', lambda *a, **k: _sync_analysis_settings())
            controller.manual_transpose_semi_var.trace_add('write', lambda *a, **k: _sync_analysis_settings())
            controller.min_note_duration_ms_var.trace_add('write', lambda *a, **k: _sync_analysis_settings())
        except Exception:
            pass

        # 初始化一次
        _sync_analysis_settings()

        # 若有当前文件路径变量，变化时也自动重新计算白键率
        try:
            # 定义控制器级别的钩子，供 file_select 等组件复用
            def _on_midi_path_changed(*a, **k):
                try:
                    path = controller.midi_path_var.get() if hasattr(controller, 'midi_path_var') else ''
                except Exception:
                    path = ''
                try:
                    controller._log_message(f"[DEBUG] 文件路径变更: {path}", "DEBUG")
                except Exception:
                    pass
                # 立即计算一次，确保UI即时显示白键率/k
                try:
                    (getattr(controller, '_compute_white_rate_now', None) or _compute_white_rate_now)()
                except Exception:
                    _compute_white_rate_now()
                # 再调度一次，兜底刷新
                try:
                    (getattr(controller, '_schedule_compute_white_rate', None) or _schedule_compute_white_rate)(200)
                except Exception:
                    _schedule_compute_white_rate(200)

            # 绑定到 controller，便于其他文件调用
            controller._on_midi_path_changed = _on_midi_path_changed

            # 若变量已存在，直接注册 trace；如果稍后创建，file_select 中会调用该钩子
            if hasattr(controller, 'midi_path_var') and controller.midi_path_var:
                controller.midi_path_var.trace_add('write', _on_midi_path_changed)
        except Exception:
            pass

        # —— 扫弦/聚合设置 ——
        try:
            strum_frame = ttk.LabelFrame(tab_parse, text="扫弦/聚合设置", padding="10")
            strum_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
            ttk.Label(strum_frame, text="扫弦模式:").grid(row=0, column=0, sticky=tk.W)
            # 中文标签与内部值映射
            controller._strum_label_to_value = {'合并': 'merge', '扫弦': 'arpeggio', '原始': 'original'}
            controller._strum_value_to_label = {v: k for k, v in controller._strum_label_to_value.items()}
            controller.multi_key_cluster_mode_var = tk.StringVar(value='合并')
            mode_combo = ttk.Combobox(strum_frame, textvariable=controller.multi_key_cluster_mode_var, state='readonly', width=10,
                                      values=list(controller._strum_label_to_value.keys()))
            mode_combo.grid(row=0, column=1, sticky=tk.W, padx=(6, 16))
            ttk.Label(strum_frame, text="聚合窗口(ms):").grid(row=0, column=2, sticky=tk.W)
            controller.multi_key_cluster_window_ms_var = tk.IntVar(value=240)
            ttk.Spinbox(strum_frame, from_=0, to=500, increment=1, textvariable=controller.multi_key_cluster_window_ms_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=(6,0))

            def _sync_strum_settings(*args, **kwargs):
                try:
                    ps = getattr(controller, 'playback_service', None)
                    if ps and hasattr(ps, 'configure_auto_player'):
                        label = controller.multi_key_cluster_mode_var.get()
                        mode_val = controller._strum_label_to_value.get(label, 'merge')
                        ps.configure_auto_player(options=dict(
                            multi_key_cluster_mode=mode_val,
                            multi_key_cluster_window_ms=int(controller.multi_key_cluster_window_ms_var.get()),
                        ))
                except Exception:
                    pass
            controller.multi_key_cluster_mode_var.trace_add('write', lambda *a, **k: _sync_strum_settings())
            controller.multi_key_cluster_window_ms_var.trace_add('write', lambda *a, **k: _sync_strum_settings())
            _sync_strum_settings()
        except Exception:
            pass

        # 架子鼓禁用解析设置（直通）
        try:
            if (instrument or '').strip() == '架子鼓':
                for w in parse_settings.winfo_children():
                    try:
                        w.configure(state='disabled')
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass

    # 默认显示“控制”页（再次调用确保初始渲染）
    switch_tab('controls')
    try:
        # 记录一次可见性统计，辅助排查
        cnt = len(tab_controls.winfo_children())
        controller._log_message(f"控制分页子控件个数: {cnt}", "INFO")
    except Exception:
        pass

    # —— 全局热键：仅保留 Ctrl+Shift+C 停止所有播放 ——
    try:
        if hasattr(controller, 'root') and controller.root:
            # 解绑可能存在的旧热键（容错处理，不抛错）
            for seq in ('<space>', '<Space>', '<Escape>', '<ESC>', '<Control-s>', '<Control-S>'):
                try:
                    controller.root.unbind_all(seq)
                except Exception:
                    pass
            # 绑定 Ctrl+Shift+C 停止
            def _stop_all_hotkey(event=None):
                try:
                    if hasattr(controller, '_stop_playback'):
                        controller._stop_playback()
                except Exception:
                    pass
            controller.root.bind_all('<Control-Shift-C>', _stop_all_hotkey)
            controller._log_message('已注册热键 Ctrl+Shift+C 用于停止所有播放（已移除其他热键）', 'INFO')
    except Exception:
        pass

    # 帮助页签内容
    help_inner = ttk.Frame(tab_help)
    help_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    help_text = (
        "热键说明:\n"
        "• Ctrl+Shift+C: 停止所有播放\n"
        "\n使用说明:\n"
        "1. 选择音频文件 → 音频转MIDI\n"
        "2. 选择MIDI → 解析/事件/日志 中查看与设置\n"
        "3. 设置演奏参数 → 控制 中操作\n"
    )
    ttk.Label(help_inner, text=help_text, justify=tk.LEFT, wraplength=520).pack(anchor=tk.W)

    # 控制页：直接使用容器帧（不使用内层滚动条），避免双滚动条
    ctrl_inner = ttk.Frame(tab_controls)
    ctrl_inner.pack(fill=tk.BOTH, expand=True)

    # 顶部当前乐器提示（仅提示，不改变布局逻辑）
    try:
        if instrument:
            banner = ttk.Label(ctrl_inner, text=f"当前乐器: {instrument}", foreground="#0A84FF")
            banner.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=(8, 0))
    except Exception:
        pass

    # 文件选择（移入“控制”分页顶部）
    try:
        fs_wrap = ttk.Frame(ctrl_inner)
        fs_wrap.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 8))
        controller._create_file_selection_component(parent_left=fs_wrap)
    except Exception as e:
        try:
            controller._log_message(f"文件选择组件创建失败: {e}", "ERROR")
        except Exception:
            pass

    # 控制页（根据乐器类型提供专属设置）
    try:
        # 电子琴和吉他：显示通用演奏模式
        if (instrument or '').strip() in ('电子琴', '吉他', ''):
            mode_frame = ttk.Frame(ctrl_inner)
            mode_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(4, 8))
            ttk.Label(mode_frame, text="演奏模式:").pack(side=tk.LEFT, padx=(0, 16))
            controller.playback_mode = tk.StringVar(value="midi")
            ttk.Radiobutton(mode_frame, text="MIDI模式", variable=controller.playback_mode, value="midi", command=controller._on_mode_changed).pack(side=tk.LEFT, padx=(0, 16))
        
        # 贝斯：简化设置，无和弦功能
        elif (instrument or '').strip() == '贝斯':
            bass_info = ttk.LabelFrame(ctrl_inner, text="贝斯设置", padding="8")
            bass_info.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(4, 8))
            ttk.Label(bass_info, text="键位：3×7布局（与钢琴上三行一致）", foreground="#666").pack(anchor=tk.W)
            ttk.Label(bass_info, text="注意：贝斯无和弦功能，解析时将禁用和弦相关选项", foreground="#B00020").pack(anchor=tk.W)
        
        # 架子鼓：专属设置（直接播放，不走解析流程）
        elif (instrument or '').strip() == '架子鼓':
            drums_info = ttk.LabelFrame(ctrl_inner, text="架子鼓设置", padding="8")
            drums_info.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(4, 8))
            ttk.Label(drums_info, text="键位：专用鼓键映射（1QW2345TER等）", foreground="#666").pack(anchor=tk.W)
            ttk.Label(drums_info, text="模式：直接播放鼓MIDI，无需解析设置", foreground="#0A84FF").pack(anchor=tk.W)
            ttk.Label(drums_info, text="注意：架子鼓不使用解析栏设置，直接读取MIDI文件播放", foreground="#B00020").pack(anchor=tk.W)

        # 速度（保留倍速控件）
        av_frame = ttk.LabelFrame(ctrl_inner, text="速度设置", padding="10")
        av_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(av_frame, text="倍速:").pack(side=tk.LEFT)
        controller.tempo_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(av_frame, from_=0.25, to=3.0, increment=0.05, textvariable=controller.tempo_var, width=8).pack(side=tk.LEFT, padx=(10, 16))

        button_frame = ttk.LabelFrame(ctrl_inner, text="操作", padding="10")
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        controller._create_auto_play_controls(button_frame)
        btn_row = ttk.Frame(button_frame)
        btn_row.pack(side=tk.TOP, anchor=tk.W, pady=(10,0))
        ttk.Button(btn_row, text="播放MIDI", style=styles['success'], command=controller._play_midi).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="停止", style=styles['danger'], command=controller._stop_playback).pack(side=tk.LEFT, padx=(12,0))
        # 快捷键提示
        hint = ttk.Label(button_frame, text="快捷键: Ctrl+Shift+C=停止所有播放", foreground="#666")
        hint.pack(side=tk.TOP, anchor=tk.W, pady=(10,0))
    except Exception as e:
        # 加载失败兜底
        try:
            controller._log_message(f"控制区创建失败: {e}", "ERROR")
        except Exception:
            pass
        ttk.Label(ctrl_inner, text="播放控制加载失败", foreground="#B00020").pack(anchor=tk.W, padx=12, pady=12)

    # 分部识别与选择（内嵌，不使用弹窗）
    part_frame = ttk.LabelFrame(ctrl_inner, text="分部识别与选择", padding="8")
    part_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    # 工具栏：识别 + 批量选择 + 拆分模式
    part_toolbar = ttk.Frame(part_frame)
    part_toolbar.pack(side=tk.TOP, fill=tk.X)
    # 内置识别分部：按 轨/通道/音色 分离，并自动填充表格
    def _identify_parts():
        try:
            # 使用 PlaybackController 的 split 能力
            pc = getattr(controller, 'playback_controller', None)
            midi_path = getattr(controller, 'midi_path_var', None).get() if hasattr(controller, 'midi_path_var') else ''
            if not pc or not midi_path:
                return
            parts = pc.split_midi_by_track_channel(midi_path)
            controller._last_split_parts = parts or {}
            # 自动根据乐器偏好勾选（非鼓勾选非 ch9；鼓勾选 ch9）
            controller._selected_part_names = set()
            _refresh_parts_tree()
            _auto_select_parts()
            _refresh_parts_tree()
            # 将当前选择推送到服务层过滤器
            try:
                ps = getattr(controller, 'playback_service', None)
                if ps and hasattr(ps, 'set_selected_parts_filter'):
                    sel = list(getattr(controller, '_selected_part_names', set()) or [])
                    ps.set_selected_parts_filter(getattr(controller, '_last_split_parts', {}) or {}, sel)
            except Exception:
                pass
            try:
                controller._log_message(f"分部识别完成: {len(parts)} 个", "INFO")
            except Exception:
                pass
        except Exception:
            pass
    ttk.Button(part_toolbar, text="识别分部", style=styles['info'], command=_identify_parts).pack(side=tk.LEFT)
    ttk.Button(part_toolbar, text="全选", style=styles['primary'], command=getattr(controller, '_ui_parts_select_all', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(part_toolbar, text="全不选", style=styles['warning'], command=getattr(controller, '_ui_parts_select_none', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(part_toolbar, text="反选", style=styles['secondary'], command=getattr(controller, '_ui_parts_select_invert', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    # 拆分模式选择
    ttk.Label(part_toolbar, text="拆分模式:").pack(side=tk.LEFT, padx=(16,4))
    controller.partition_split_mode_var = tk.StringVar(value='仅通道')
    ttk.Combobox(part_toolbar, textvariable=controller.partition_split_mode_var, state='readonly', width=14,
                 values=['仅通道','智能聚类']).pack(side=tk.LEFT)

    # Treeview：展示分部
    part_body = ttk.Frame(part_frame)
    part_body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(6, 6))
    # 勾选列 + 数据列
    columns = ("选择", "分部", "计数", "说明")
    parts_tree = ttk.Treeview(part_body, columns=columns, show='headings', selectmode='none', height=8)
    heads = ["选择", "分部", "计数", "说明"]
    widths = [60, 240, 80, 300]
    for i, col in enumerate(columns):
        parts_tree.heading(col, text=heads[i])
        if i == 0:
            parts_tree.column(col, width=widths[i], anchor=tk.CENTER)
        elif i == 2:
            parts_tree.column(col, width=widths[i], anchor=tk.CENTER)
        else:
            parts_tree.column(col, width=widths[i], anchor=tk.W)
    vbar2 = ttk.Scrollbar(part_body, orient=tk.VERTICAL, command=parts_tree.yview)
    parts_tree.configure(yscrollcommand=vbar2.set)
    parts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar2.pack(side=tk.RIGHT, fill=tk.Y)
    # 对外暴露句柄
    controller._parts_tree = parts_tree
    # 勾选状态存储：name -> bool
    controller._parts_checked = {}

    def _on_parts_tree_click(event=None):
        try:
            region = parts_tree.identify('region', event.x, event.y)
            if region != 'cell':
                return
            col = parts_tree.identify_column(event.x)
            if col != '#1':  # 仅在“选择”列点按时切换
                return
            row = parts_tree.identify_row(event.y)
            if not row:
                return
            vals = list(parts_tree.item(row, 'values'))
            if not vals or len(vals) < 2:
                return
            name = vals[1]
            sel = getattr(controller, '_selected_part_names', set()) or set()
            if name in sel:
                sel.remove(name)
                vals[0] = '□'
            else:
                sel.add(name)
                vals[0] = '■'
            controller._selected_part_names = sel
            parts_tree.item(row, values=vals)
            # 将选择推送到服务层过滤器（空集合将清除过滤）
            try:
                ps = getattr(controller, 'playback_service', None)
                if ps and hasattr(ps, 'set_selected_parts_filter'):
                    ps.set_selected_parts_filter(getattr(controller, '_last_split_parts', {}) or {}, list(sel))
            except Exception:
                pass
            # 勾选变化后，立即重新计算白键率缓存（不播放）
            _schedule_compute_white_rate(100)
        except Exception:
            pass
    parts_tree.bind('<Button-1>', _on_parts_tree_click)

    # 操作行：应用所选并解析 / 播放 / 导出
    act_row = ttk.Frame(part_frame)
    act_row.pack(side=tk.TOP, anchor=tk.W)
    ttk.Button(act_row, text="应用所选分部并解析", style=styles['primary'], command=getattr(controller, '_ui_apply_selected_parts_and_analyze', lambda: None)).pack(side=tk.LEFT)
    ttk.Button(act_row, text="播放所选分部", style=styles['success'], command=getattr(controller, '_ui_play_selected_partitions', lambda: None)).pack(side=tk.LEFT, padx=(8,0))
    ttk.Button(act_row, text="导出所选分部", style=styles['secondary'], command=getattr(controller, '_ui_export_selected_partitions', lambda: None)).pack(side=tk.LEFT, padx=(8,0))

    # 合奏相关（可选）
    if include_ensemble:
        ensemble_frame = ttk.Frame(ctrl_inner)
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

    # 不返回未定义的 notebook，避免 NameError
    return None
