#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
架子鼓页面：独立完整的架子鼓演奏界面
包含分部解析、播放控制、播放列表、事件表、日志等完整功能
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from typing import Optional, Dict, List, Any

try:
    from .. import BasePage
except Exception:
    class BasePage:
        def mount(self, left, right): ...
        def unmount(self): ...


class DrumsPage(BasePage):
    def __init__(self, controller, app_ref=None):
        self.controller = controller
        self.app_ref = app_ref
        self._mounted = False
        
        # 设置当前乐器，以便播放控制器能够识别
        if self.app_ref:
            self.app_ref.current_instrument = "架子鼓"
            # 为播放服务添加必要的属性
            self.app_ref.analysis_notes = None
            self.app_ref.analysis_file = ""
        
        # 状态变量
        # midi_path_var将在_create_file_section中定义在app_ref上
        self.current_midi_file = ""
        self.analysis_notes = None
        self.analysis_file = ""
        
        # UI组件引用
        self.partition_listbox: Optional[tk.Listbox] = None
        self.event_tree: Optional[ttk.Treeview] = None
        self.playlist_tree: Optional[ttk.Treeview] = None
        self.log_text: Optional[tk.Text] = None
        
        # 播放控制按钮
        self.btn_play: Optional[ttk.Button] = None
        self.btn_pause: Optional[ttk.Button] = None
        self.btn_stop: Optional[ttk.Button] = None
        
        # 分部解析相关
        self.partitions_data = []
        self.selected_partitions = []
        # 播放列表与模式
        self._playlist_paths: Dict[str, str] = {}
        self.playlist_mode_var = tk.StringVar(value='顺序')  # 顺序/循环/单曲
        self._current_playing_iid: Optional[str] = None

        # 定时和对时相关
        self._current_schedule_id: Optional[str] = None

    def mount(self, left: ttk.Frame, right: ttk.Frame):
        """挂载架子鼓页面"""
        self._create_left_panel(left)
        self._create_right_panel(right)
        self._mounted = True

    def unmount(self):
        """卸载页面"""
        self._mounted = False

    def _create_left_panel(self, parent):
        """创建左侧面板"""
        # 创建滚动容器
        canvas = tk.Canvas(parent, highlightthickness=0, bg='white')
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # 配置滚动
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 布局滚动容器
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # 主容器（在滚动框架内）
        main_frame = ttk.Frame(scrollable_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 文件选择区域
        self._create_file_section(main_frame)
        
        # 分部解析区域
        self._create_partition_section(main_frame)
        
        # 播放控制区域
        self._create_control_section(main_frame)
        
        # 定时和对时功能区域
        self._create_timing_section(main_frame)
        
        # 播放列表区域
        self._create_playlist_section(main_frame)

    def _create_file_section(self, parent):
        """创建文件选择区域"""
        file_frame = ttk.LabelFrame(parent, text="MIDI文件选择", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 文件路径
        path_frame = ttk.Frame(file_frame)
        path_frame.pack(fill=tk.X)
        
        # 将midi_path_var定义在app_ref上，以便播放服务能够访问
        if self.app_ref:
            self.app_ref.midi_path_var = tk.StringVar(value="")
        else:
            self.midi_path_var = tk.StringVar(value="")
        
        midi_path_var = self.app_ref.midi_path_var if self.app_ref else self.midi_path_var
        ttk.Label(path_frame, text="文件:").pack(side=tk.LEFT)
        path_entry = ttk.Entry(path_frame, textvariable=midi_path_var, width=40)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        browse_btn = ttk.Button(path_frame, text="浏览", command=self._browse_file,
                               style='MF.Primary.TButton')
        browse_btn.pack(side=tk.RIGHT)
        
        # 速度控制
        tempo_frame = ttk.Frame(file_frame)
        tempo_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 将tempo_var定义在app_ref上，以便播放控制器能够访问
        if self.app_ref:
            self.app_ref.tempo_var = tk.DoubleVar(value=1.0)
        else:
            self.tempo_var = tk.DoubleVar(value=1.0)
        
        tempo_var = self.app_ref.tempo_var if self.app_ref else self.tempo_var
        ttk.Label(tempo_frame, text="速度倍率:").pack(side=tk.LEFT)
        tempo_spin = ttk.Spinbox(tempo_frame, from_=0.1, to=3.0, increment=0.1,
                                textvariable=tempo_var, width=10)
        tempo_spin.pack(side=tk.LEFT, padx=(5, 0))

    def _create_partition_section(self, parent):
        """创建分部解析区域"""
        partition_frame = ttk.LabelFrame(parent, text="分部解析", padding="10")
        partition_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 按钮区域
        btn_frame = ttk.Frame(partition_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(btn_frame, text="识别分部", command=self._identify_partitions,
                  style='MF.Secondary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="全选", command=self._select_all_partitions,
                  style='MF.Secondary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="应用解析", command=self._apply_analysis,
                  style='MF.Primary.TButton').pack(side=tk.LEFT)
        
        # 分部列表
        list_frame = ttk.Frame(partition_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.partition_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, height=6)
        partition_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, 
                                       command=self.partition_listbox.yview)
        self.partition_listbox.configure(yscrollcommand=partition_scroll.set)
        
        self.partition_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        partition_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_control_section(self, parent):
        """创建播放控制区域"""
        control_frame = ttk.LabelFrame(parent, text="播放控制", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack()
        
        self.btn_play = ttk.Button(btn_frame, text="开始播放", command=self._start_play,
                                  style='MF.Success.TButton')
        self.btn_play.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_pause = ttk.Button(btn_frame, text="暂停", command=self._pause_play,
                                   style='MF.Warning.TButton')
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_stop = ttk.Button(btn_frame, text="停止", command=self._stop_play,
                                  style='MF.Danger.TButton')
        self.btn_stop.pack(side=tk.LEFT)

        # 倒计时设置与显示
        cfg = ttk.Frame(control_frame)
        cfg.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(cfg, text="开始前倒计时:").pack(side=tk.LEFT)
        self.enable_countdown_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, variable=self.enable_countdown_var).pack(side=tk.LEFT, padx=(6, 6))
        self.countdown_seconds_var = tk.IntVar(value=3)
        ttk.Spinbox(cfg, from_=0, to=30, increment=1, width=6, textvariable=self.countdown_seconds_var).pack(side=tk.LEFT)
        ttk.Label(cfg, text="秒").pack(side=tk.LEFT, padx=(6,0))
        self.countdown_label = ttk.Label(control_frame, text="")
        self.countdown_label.pack(anchor=tk.W, pady=(4,0))
        
        # 键位说明
        keymap_frame = ttk.Frame(control_frame)
        keymap_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(keymap_frame, text="架子鼓键位映射:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        keymap_text = """1-踩镲闭  Q-踩镲开  2-高音吊镲  3-一嗵鼓  4-二嗵鼓  5-叮叮镲
T-中音吊镲  W-军鼓  E-底鼓  R-落地嗵鼓"""
        
        ttk.Label(keymap_frame, text=keymap_text, font=("Consolas", 8), 
                 foreground="#666666").pack(anchor=tk.W, padx=(10, 0))

    def _create_timing_section(self, parent):
        """创建定时和对时功能区域"""
        timing_frame = ttk.LabelFrame(parent, text="定时触发（单次·NTP对时+延迟/补偿）", padding="10")
        timing_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 时间输入：HH:MM:SS.mmm
        ttk.Label(timing_frame, text="目标时间(24h):").grid(row=0, column=0, sticky=tk.W)
        # 将时间变量定义在app_ref上，以便播放控制器能够访问
        if self.app_ref:
            self.app_ref.timing_hh_var = tk.IntVar(value=17)
            self.app_ref.timing_mm_var = tk.IntVar(value=0)
            self.app_ref.timing_ss_var = tk.IntVar(value=0)
            self.app_ref.timing_ms_var = tk.IntVar(value=0)
        else:
            # 备用方案：如果app_ref不可用，仍然定义在self上
            self.timing_hh_var = tk.IntVar(value=17)
            self.timing_mm_var = tk.IntVar(value=0)
            self.timing_ss_var = tk.IntVar(value=0)
            self.timing_ms_var = tk.IntVar(value=0)
        # 使用正确的变量引用
        hh_var = self.app_ref.timing_hh_var if self.app_ref else self.timing_hh_var
        mm_var = self.app_ref.timing_mm_var if self.app_ref else self.timing_mm_var
        ss_var = self.app_ref.timing_ss_var if self.app_ref else self.timing_ss_var
        ms_var = self.app_ref.timing_ms_var if self.app_ref else self.timing_ms_var
        
        ttk.Spinbox(timing_frame, from_=0, to=23, width=4, textvariable=hh_var).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(timing_frame, text=":").grid(row=0, column=2, sticky=tk.W)
        ttk.Spinbox(timing_frame, from_=0, to=59, width=4, textvariable=mm_var).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(timing_frame, text=":").grid(row=0, column=4, sticky=tk.W)
        ttk.Spinbox(timing_frame, from_=0, to=59, width=4, textvariable=ss_var).grid(row=0, column=5, sticky=tk.W)
        ttk.Label(timing_frame, text=".").grid(row=0, column=6, sticky=tk.W)
        ttk.Spinbox(timing_frame, from_=0, to=999, width=6, textvariable=ms_var).grid(row=0, column=7, sticky=tk.W)

        # 对时控制（执行后刷新状态）
        def _btn_enable_net():
            self._timing_enable_network_clock()
            self._refresh_timing_status(delay_ms=50)
        def _btn_sync_now():
            self._timing_sync_now()
            self._refresh_timing_status(delay_ms=50)
        def _btn_use_local():
            self._timing_use_local()
            self._refresh_timing_status(delay_ms=50)
        ttk.Button(timing_frame, text="启用公网对时", command=_btn_enable_net).grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        ttk.Button(timing_frame, text="手动对时", command=_btn_sync_now).grid(row=1, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
        ttk.Button(timing_frame, text="切回本地时钟", command=_btn_use_local).grid(row=1, column=2, sticky=tk.W, padx=(6,0), pady=(6,0))

        # NTP 服务器选择/关闭
        ttk.Label(timing_frame, text="NTP服务器(逗号分隔):").grid(row=4, column=0, sticky=tk.W, pady=(6,0))
        try:
            default_servers = "ntp.ntsc.ac.cn,time1.cloud.tencent.com,time2.cloud.tencent.com"
            self.timing_servers_var = tk.StringVar(value=default_servers)
        except Exception:
            pass
        server_entry = ttk.Entry(timing_frame, textvariable=self.timing_servers_var, width=48)
        server_entry.grid(row=4, column=1, columnspan=4, sticky=tk.W+tk.E, padx=(6,0), pady=(6,0))
        def _apply_servers():
            self._timing_apply_servers()
            self._refresh_timing_status(delay_ms=100)
        ttk.Button(timing_frame, text="应用服务器", command=_apply_servers).grid(row=4, column=5, sticky=tk.W, padx=(6,0), pady=(6,0))
        self.ntp_enabled_var = tk.BooleanVar(value=True)
        def _toggle_ntp():
            self._timing_toggle_ntp(self.ntp_enabled_var.get())
            self._refresh_timing_status(delay_ms=100)
        ttk.Checkbutton(timing_frame, text="启用NTP", variable=self.ntp_enabled_var, command=_toggle_ntp).grid(row=4, column=6, sticky=tk.W, padx=(12,0), pady=(6,0))

        # 对时参数：间隔与重排阈值
        ttk.Label(timing_frame, text="对时间隔(s):").grid(row=5, column=0, sticky=tk.W, pady=(6,0))
        self.timing_resync_interval_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(timing_frame, from_=0.2, to=10.0, increment=0.2, width=8, textvariable=self.timing_resync_interval_var).grid(row=5, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
        ttk.Label(timing_frame, text="重排阈值(ms):").grid(row=5, column=2, sticky=tk.W, pady=(6,0))
        self.timing_adjust_threshold_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(timing_frame, from_=1.0, to=1000.0, increment=1.0, width=10, textvariable=self.timing_adjust_threshold_var).grid(row=5, column=3, sticky=tk.W, pady=(6,0))
        def _apply_resync_params():
            try:
                interval = float(self.timing_resync_interval_var.get())
            except Exception:
                interval = None
            try:
                thr = float(self.timing_adjust_threshold_var.get())
            except Exception:
                thr = None
            self._timing_set_resync_settings(interval, thr)
            self._refresh_timing_status(delay_ms=100)
        ttk.Button(timing_frame, text="应用对时参数", command=_apply_resync_params).grid(row=5, column=4, sticky=tk.W, padx=(6,0), pady=(6,0))

        # 手动补偿与状态
        ttk.Label(timing_frame, text="手动补偿(ms):").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
        # 将手动补偿变量也定义在app_ref上
        if self.app_ref:
            self.app_ref.timing_manual_ms_var = tk.IntVar(value=0)
        else:
            self.timing_manual_ms_var = tk.IntVar(value=0)
        
        manual_var = self.app_ref.timing_manual_ms_var if self.app_ref else self.timing_manual_ms_var
        ttk.Spinbox(timing_frame, from_=-2000, to=2000, increment=1, width=8, textvariable=manual_var).grid(row=2, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
        self.timing_status_var = tk.StringVar(value="状态: 未对时")
        ttk.Label(timing_frame, textvariable=self.timing_status_var, foreground="#666").grid(row=2, column=2, columnspan=6, sticky=tk.W, padx=(12,0), pady=(6,0))

        # 操作按钮
        def _btn_schedule():
            self._timing_schedule_for_current_instrument()
            # 计划创建后立即刷新一次，便于看到"实时对时/延迟"
            self._refresh_timing_status(delay_ms=50)
        def _btn_cancel():
            self._timing_cancel_schedule()
            self._refresh_timing_status(delay_ms=50)
        def _btn_test_now():
            self._timing_test_now()
            self._refresh_timing_status(delay_ms=50)
        ttk.Button(timing_frame, text="创建计划", command=_btn_schedule).grid(row=3, column=0, sticky=tk.W, pady=(8,0))
        ttk.Button(timing_frame, text="取消计划", command=_btn_cancel).grid(row=3, column=1, sticky=tk.W, padx=(6,0), pady=(8,0))
        ttk.Button(timing_frame, text="立即按计划测试一次", command=_btn_test_now).grid(row=3, column=2, sticky=tk.W, padx=(6,0), pady=(8,0))
        for c in range(8):
            try:
                timing_frame.grid_columnconfigure(c, weight=1)
            except Exception:
                pass

        # 首次进入时刷新一次，并开启定时刷新
        self._refresh_timing_status(delay_ms=10)
        # 页面初始化时若启用了 NTP，则确保后台对时线程已启动，并应用当前对时参数
        def _bootstrap_timing():
            try:
                if self.ntp_enabled_var.get():
                    _apply_servers()
                    _apply_resync_params()
            except Exception:
                pass
        try:
            if hasattr(self, 'app_ref') and self.app_ref and hasattr(self.app_ref, 'root'):
                self.app_ref.root.after(50, _bootstrap_timing)
            else:
                _bootstrap_timing()
        except Exception:
            _bootstrap_timing()
        # 循环将在 _do 中自行重排 next after

    def _create_playlist_section(self, parent):
        """创建播放列表区域"""
        playlist_frame = ttk.LabelFrame(parent, text="播放列表", padding="10")
        playlist_frame.pack(fill=tk.BOTH, expand=True)
        
        # 播放列表树形控件
        tree_frame = ttk.Frame(playlist_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.playlist_tree = ttk.Treeview(tree_frame, columns=("type", "status"), 
                                         show="tree headings", height=4)
        self.playlist_tree.heading("#0", text="文件名", anchor=tk.W)
        self.playlist_tree.heading("type", text="类型", anchor=tk.W)
        self.playlist_tree.heading("status", text="状态", anchor=tk.W)
        
        self.playlist_tree.column("#0", width=200)
        self.playlist_tree.column("type", width=80)
        self.playlist_tree.column("status", width=80)
        
        playlist_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                       command=self.playlist_tree.yview)
        self.playlist_tree.configure(yscrollcommand=playlist_scroll.set)
        
        self.playlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        playlist_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 工具栏：添加/移除/清空 + 播放控制 + 模式
        toolbar = ttk.Frame(playlist_frame)
        toolbar.pack(fill=tk.X, pady=(6,0))
        ttk.Button(toolbar, text="添加文件", command=self._browse_file).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="移除所选", command=self._remove_selected_from_playlist).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(toolbar, text="清空", command=self._clear_playlist).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(toolbar, text="播放所选", command=self._play_selected_from_playlist).pack(side=tk.LEFT, padx=(12,0))
        ttk.Button(toolbar, text="上一首", command=self._play_prev_from_playlist).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(toolbar, text="下一首", command=self._play_next_from_playlist).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(toolbar, text="播放模式:").pack(side=tk.LEFT, padx=(16,4))
        mode_combo = ttk.Combobox(toolbar, textvariable=self.playlist_mode_var, state='readonly', width=10,
                                  values=['单曲','顺序','循环'])
        mode_combo.pack(side=tk.LEFT)

    def _create_right_panel(self, parent):
        """创建右侧面板"""
        # 创建笔记本控件用于标签页
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 事件表标签页
        event_frame = ttk.Frame(notebook)
        notebook.add(event_frame, text="事件表")
        self._create_event_table(event_frame)
        
        # 日志标签页
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="日志")
        self._create_log_panel(log_frame)

    def _create_event_table(self, parent):
        """创建事件表"""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.event_tree = ttk.Treeview(tree_frame, columns=("time", "type", "note", "velocity"),
                                      show="headings")
        
        self.event_tree.heading("time", text="时间", anchor=tk.W)
        self.event_tree.heading("type", text="类型", anchor=tk.W)
        self.event_tree.heading("note", text="音符", anchor=tk.W)
        self.event_tree.heading("velocity", text="力度", anchor=tk.W)
        
        self.event_tree.column("time", width=80)
        self.event_tree.column("type", width=60)
        self.event_tree.column("note", width=80)
        self.event_tree.column("velocity", width=60)
        
        event_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                    command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=event_scroll.set)
        
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        event_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_log_panel(self, parent):
        """创建日志面板"""
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=15)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 初始日志
        self._log_message("架子鼓模式已加载")
        self._log_message("支持单轨道和多轨道MIDI文件的第10轨道（通道9）")

    # ===== 事件处理方法 =====
    
    def _browse_file(self):
        """浏览选择MIDI文件"""
        file_path = filedialog.askopenfilename(
            title="选择架子鼓MIDI文件",
            filetypes=[('MIDI Files', '*.mid *.midi'), ('All Files', '*.*')]
        )
        if file_path:
            midi_path_var = self.app_ref.midi_path_var if self.app_ref else self.midi_path_var
            midi_path_var.set(file_path)
            self.current_midi_file = file_path
            self._log_message(f"已选择文件: {os.path.basename(file_path)}")
            self._add_to_playlist(file_path)

    def _identify_partitions(self):
        """识别MIDI分部"""
        if not self.current_midi_file:
            messagebox.showwarning("提示", "请先选择MIDI文件")
            return
            
        try:
            self._log_message("正在识别分部...")
            
            # 调用架子鼓解析器识别分部
            if hasattr(self.app_ref, 'drums_parser'):
                parser = self.app_ref.drums_parser
                partitions = parser.identify_partitions(self.current_midi_file)
                
                self.partitions_data = partitions
                self._update_partition_list()
                self._log_message(f"识别到 {len(partitions)} 个分部")
            else:
                # 简化版本：假设架子鼓在第10轨道
                self.partitions_data = [
                    {"track": 9, "channel": 9, "name": "架子鼓", "notes": 0}
                ]
                self._update_partition_list()
                self._log_message("使用默认架子鼓分部（轨道10，通道9）")
                
        except Exception as e:
            self._log_message(f"分部识别失败: {e}", "ERROR")

    def _update_partition_list(self):
        """更新分部列表显示"""
        if not self.partition_listbox:
            return
            
        self.partition_listbox.delete(0, tk.END)
        for i, partition in enumerate(self.partitions_data):
            name = partition.get("name", f"分部{i+1}")
            track = partition.get("track", 0)
            channel = partition.get("channel", 0)
            notes = partition.get("notes", 0)
            
            display_text = f"{name} (轨道{track+1}, 通道{channel+1}, {notes}音符)"
            self.partition_listbox.insert(tk.END, display_text)

    def _select_all_partitions(self):
        """全选所有分部"""
        if not self.partition_listbox:
            return
            
        self.partition_listbox.select_set(0, tk.END)
        self._log_message("已全选所有分部")

    def _apply_analysis(self):
        """应用分部解析"""
        if not self.partitions_data:
            messagebox.showwarning("提示", "请先识别分部")
            return
            
        selected_indices = self.partition_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("提示", "请选择要解析的分部")
            return
            
        try:
            self._log_message("正在解析选中的分部...")
            
            # 获取选中的分部
            self.selected_partitions = [self.partitions_data[i] for i in selected_indices]
            
            # 调用架子鼓解析器
            if hasattr(self.app_ref, 'drums_parser'):
                parser = self.app_ref.drums_parser
                analysis_notes = parser.parse_partitions(
                    self.current_midi_file, 
                    self.selected_partitions
                )
                # 同时保存到self和app_ref上
                self.analysis_notes = analysis_notes
                self.analysis_file = self.current_midi_file
                if self.app_ref:
                    self.app_ref.analysis_notes = analysis_notes
                    self.app_ref.analysis_file = self.current_midi_file
                
                self._update_event_table()
                self._log_message(f"解析完成，共 {len(self.analysis_notes)} 个事件")
            else:
                self._log_message("架子鼓解析器不可用", "WARNING")
                
        except Exception as e:
            self._log_message(f"解析失败: {e}", "ERROR")

    def _update_event_table(self):
        """更新事件表显示"""
        if not self.event_tree or not self.analysis_notes:
            return
            
        # 清空现有项目
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
            
        # 添加解析的事件
        for i, note in enumerate(self.analysis_notes[:100]):  # 限制显示前100个事件
            time_str = f"{note.get('time', 0):.2f}s"
            note_type = "打击" if note.get('type') == 'note_on' else "释放"
            note_name = self._get_drum_name(note.get('note', 0))
            velocity = note.get('velocity', 0)
            
            self.event_tree.insert("", tk.END, values=(time_str, note_type, note_name, velocity))

    def _get_drum_name(self, note_number):
        """根据MIDI音符号获取鼓件名称"""
        drum_names = {
            35: "底鼓1", 36: "底鼓2", 37: "侧击", 38: "军鼓1", 39: "拍手",
            40: "军鼓2", 41: "低嗵鼓", 42: "踩镲闭", 43: "低嗵鼓", 44: "踩镲踏板",
            45: "中嗵鼓", 46: "踩镲开", 47: "中高嗵鼓", 48: "高嗵鼓", 49: "吊镲1",
            50: "高嗵鼓", 51: "叮叮镲", 52: "中国镲", 53: "叮叮镲", 54: "铃鼓",
            55: "溅镲", 56: "牛铃", 57: "吊镲2", 58: "颤音鼓", 59: "叮叮镲",
            60: "高邦戈鼓", 61: "低邦戈鼓", 62: "哑音康加鼓", 63: "开音康加鼓",
            64: "低康加鼓", 65: "高音鼓", 66: "低音鼓", 67: "高阿戈戈铃",
            68: "低阿戈戈铃", 69: "响葫芦", 70: "短口哨", 71: "长口哨",
            72: "短刮葫芦", 73: "长刮葫芦", 74: "响棒", 75: "木鱼",
            76: "木块", 77: "哑音三角铁", 78: "开音三角铁", 79: "摇铃",
            80: "铃铛", 81: "响板"
        }
        return drum_names.get(note_number, f"音符{note_number}")

    def _start_play(self):
        """开始播放"""
        if not self.current_midi_file:
            messagebox.showwarning("提示", "请先选择MIDI文件")
            return
            
        try:
            def _do_start():
                self._log_message("开始架子鼓播放...")
                # 调用架子鼓控制器播放
                if hasattr(self.controller, 'start_from_file'):
                    tempo_var = self.app_ref.tempo_var if self.app_ref else self.tempo_var
                    tempo = tempo_var.get()
                    success = self.controller.start_from_file(self.current_midi_file, tempo=tempo)
                    if success:
                        self._log_message("播放已开始")
                        self._update_button_states(playing=True)
                        # 注册回调以在完成/停止时更新UI并联动播放列表
                        self._register_playback_callbacks()
                    else:
                        self._log_message("播放启动失败", "ERROR")
                else:
                    self._log_message("架子鼓控制器不可用", "ERROR")

            # 倒计时执行
            enable = bool(getattr(self, 'enable_countdown_var', tk.BooleanVar(value=True)).get())
            secs = int(getattr(self, 'countdown_seconds_var', tk.IntVar(value=3)).get())
            if enable and secs > 0:
                self._update_button_states(playing=False)
                self.btn_play.configure(state=tk.DISABLED)
                self._countdown_remaining = secs
                def _tick():
                    rem = getattr(self, '_countdown_remaining', 0)
                    if rem <= 0:
                        self.countdown_label.configure(text="")
                        self.btn_play.configure(state=tk.NORMAL)
                        _do_start()
                        return
                    self.countdown_label.configure(text=f"{rem} 秒后开始...")
                    self._countdown_remaining = rem - 1
                    self.countdown_label.after(1000, _tick)
                _tick()
            else:
                _do_start()
        
        except Exception as e:
            self._log_message(f"播放异常: {e}", "ERROR")

    def _pause_play(self):
        """暂停播放"""
        try:
            if hasattr(self.controller, 'pause'):
                self.controller.pause()
                self._log_message("播放已暂停")
                self._update_button_states(paused=True)
        except Exception as e:
            self._log_message(f"暂停失败: {e}", "ERROR")

    def _stop_play(self):
        """停止播放"""
        try:
            if hasattr(self.controller, 'stop'):
                self.controller.stop()
                self._log_message("播放已停止")
                self._update_button_states(playing=False)
        except Exception as e:
            self._log_message(f"停止失败: {e}", "ERROR")

    def _update_button_states(self, playing=False, paused=False):
        """更新按钮状态"""
        if not all([self.btn_play, self.btn_pause, self.btn_stop]):
            return
            
        if playing and not paused:
            self.btn_play.configure(state=tk.DISABLED)
            self.btn_pause.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.NORMAL)
        elif paused:
            self.btn_play.configure(state=tk.NORMAL, text="继续")
            self.btn_pause.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.btn_play.configure(state=tk.NORMAL, text="开始播放")
            self.btn_pause.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.DISABLED)

    def _add_to_playlist(self, file_path):
        """添加文件到播放列表"""
        if not self.playlist_tree:
            return
        
        filename = os.path.basename(file_path)
        iid = self.playlist_tree.insert("", tk.END, text=filename, 
                                       values=("MIDI", "就绪"))
        self._playlist_paths[iid] = file_path

    def _play_selected_from_playlist(self):
        try:
            if not self.playlist_tree:
                return
            sel = self.playlist_tree.selection()
            if not sel:
                # 若未选中，播放第一个
                first = self.playlist_tree.get_children()
                if not first:
                    return
                iid = first[0]
            else:
                iid = sel[0]
            path = self._playlist_paths.get(iid)
            if not path:
                return
            self.current_midi_file = path
            midi_path_var = self.app_ref.midi_path_var if self.app_ref else self.midi_path_var
            midi_path_var.set(path)
            self._current_playing_iid = iid
            self._mark_playlist_status(iid, "播放中")
            self._start_play()
        except Exception as e:
            self._log_message(f"播放所选失败: {e}", "ERROR")

    def _play_next_from_playlist(self):
        try:
            if not self.playlist_tree:
                return
            items = self.playlist_tree.get_children()
            if not items:
                return
            cur = self._current_playing_iid
            if cur not in items:
                idx = 0
            else:
                idx = items.index(cur) + 1
            if idx >= len(items):
                if self.playlist_mode_var.get() == '循环':
                    idx = 0
                else:
                    return
            iid = items[idx]
            path = self._playlist_paths.get(iid)
            if not path:
                return
            self.current_midi_file = path
            midi_path_var = self.app_ref.midi_path_var if self.app_ref else self.midi_path_var
            midi_path_var.set(path)
            self._current_playing_iid = iid
            self._mark_playlist_status(iid, "播放中")
            self._start_play()
        except Exception as e:
            self._log_message(f"下一首失败: {e}", "ERROR")

    def _play_prev_from_playlist(self):
        try:
            if not self.playlist_tree:
                return
            items = self.playlist_tree.get_children()
            if not items:
                return
            cur = self._current_playing_iid
            if cur not in items:
                idx = 0
            else:
                idx = max(0, items.index(cur) - 1)
            iid = items[idx]
            path = self._playlist_paths.get(iid)
            if not path:
                return
            self.current_midi_file = path
            midi_path_var = self.app_ref.midi_path_var if self.app_ref else self.midi_path_var
            midi_path_var.set(path)
            self._current_playing_iid = iid
            self._mark_playlist_status(iid, "播放中")
            self._start_play()
        except Exception as e:
            self._log_message(f"上一首失败: {e}", "ERROR")

    def _remove_selected_from_playlist(self):
        try:
            if not self.playlist_tree:
                return
            sel = self.playlist_tree.selection()
            for iid in sel:
                self.playlist_tree.delete(iid)
                self._playlist_paths.pop(iid, None)
                if self._current_playing_iid == iid:
                    self._current_playing_iid = None
        except Exception as e:
            self._log_message(f"移除失败: {e}", "ERROR")

    def _clear_playlist(self):
        try:
            if not self.playlist_tree:
                return
            for iid in list(self.playlist_tree.get_children()):
                self.playlist_tree.delete(iid)
            self._playlist_paths.clear()
            self._current_playing_iid = None
        except Exception as e:
            self._log_message(f"清空失败: {e}", "ERROR")

    def _mark_playlist_status(self, playing_iid: Optional[str], status: str):
        try:
            if not self.playlist_tree:
                return
            for iid in self.playlist_tree.get_children():
                vals = list(self.playlist_tree.item(iid, 'values'))
                if len(vals) < 2:
                    continue
                vals[1] = status if playing_iid and iid == playing_iid else ("就绪" if iid in self._playlist_paths else "")
                self.playlist_tree.item(iid, values=vals)
        except Exception:
            pass

    def _register_playback_callbacks(self):
        try:
            # 优先通过 app_ref 的 playback_service 注入回调
            svc = getattr(self.app_ref, 'playback_service', None)
            if svc and hasattr(svc, 'set_auto_callbacks'):
                svc.set_auto_callbacks(
                    on_complete=self._on_play_complete,
                    on_stop=self._on_play_stopped,
                    on_error=lambda msg=None: self._on_play_error(msg),
                )
                return
            # 回退：若 controller 支持 set_callbacks
            if hasattr(self.controller, 'set_callbacks'):
                try:
                    self.controller.set_callbacks(on_complete=self._on_play_complete,
                                                  on_stop=self._on_play_stopped)
                    return
                except Exception:
                    pass
        except Exception:
            pass

    def _on_play_complete(self):
        try:
            self._log_message("播放完成", "SUCCESS")
            self._update_button_states(playing=False)
            # 播放列表联动
            mode = self.playlist_mode_var.get()
            if mode in ("顺序", "循环"):
                self._play_next_from_playlist()
        except Exception:
            pass

    def _on_play_stopped(self):
        try:
            self._log_message("播放停止", "INFO")
            self._update_button_states(playing=False)
        except Exception:
            pass

    def _on_play_error(self, msg=None):
        try:
            self._log_message(f"播放错误: {msg}", "ERROR")
            self._update_button_states(playing=False)
        except Exception:
            pass

    def _log_message(self, message, level="INFO"):
        """记录日志消息"""
        if not self.log_text:
            return
        
        import time
        timestamp = time.strftime("%H:%M:%S")
        
        # 根据级别设置颜色
        color_map = {
            "INFO": "#000000",
            "SUCCESS": "#008000", 
            "WARNING": "#FF8C00",
            "ERROR": "#FF0000"
        }
        
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # 限制日志长度
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 1000:
            self.log_text.delete("1.0", f"{len(lines)-500}.0")

    # ===== 定时和对时功能实现 =====
    
    def _timing_enable_network_clock(self):
        """启用网络时钟"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_enable_network_clock()
            self._log_message("网络时钟已启用", "INFO")
        except Exception as e:
            self._log_message(f"启用网络时钟失败: {e}", "ERROR")

    def _timing_sync_now(self):
        """立即同步时间"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_sync_now()
            self._log_message("时间同步请求已发送", "INFO")
        except Exception as e:
            self._log_message(f"时间同步异常: {e}", "ERROR")

    def _timing_use_local(self):
        """切换到本地时钟"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_use_local()
            self._log_message("已切换到本地时钟", "INFO")
        except Exception as e:
            self._log_message(f"切换本地时钟失败: {e}", "ERROR")

    def _timing_apply_servers(self):
        """应用NTP服务器设置"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_apply_servers()
            self._log_message("NTP服务器设置已应用", "INFO")
        except Exception as e:
            self._log_message(f"应用NTP服务器失败: {e}", "ERROR")

    def _timing_toggle_ntp(self, enabled):
        """切换NTP启用状态"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_toggle_ntp(enabled)
            if enabled:
                self._log_message("NTP后台对时已启用", "INFO")
            else:
                self._log_message("NTP已禁用，使用本地时钟", "INFO")
        except Exception as e:
            self._log_message(f"切换NTP状态失败: {e}", "ERROR")

    def _timing_set_resync_settings(self, interval, threshold):
        """设置对时参数"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_set_resync_settings(interval, threshold)
            self._log_message(f"对时参数已更新: 间隔={interval}s, 阈值={threshold}ms", "INFO")
        except Exception as e:
            self._log_message(f"设置对时参数失败: {e}", "ERROR")

    def _timing_schedule_for_current_instrument(self):
        """为当前乐器创建定时计划"""
        try:
            if not self.current_midi_file:
                self._log_message("请先选择MIDI文件", "WARNING")
                return
            
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_schedule_for_current_instrument()
            self._log_message("定时计划创建请求已发送", "INFO")
        except Exception as e:
            self._log_message(f"创建定时计划失败: {e}", "ERROR")

    def _timing_cancel_schedule(self):
        """取消定时计划"""
        try:
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_cancel_schedule()
            self._log_message("定时计划取消请求已发送", "INFO")
        except Exception as e:
            self._log_message(f"取消定时计划失败: {e}", "ERROR")

    def _timing_test_now(self):
        """立即测试播放（按当前设置）"""
        try:
            if not self.current_midi_file:
                self._log_message("请先选择MIDI文件", "WARNING")
                return
            
            if not self.app_ref:
                self._log_message("应用引用不可用", "ERROR")
                return
            if not hasattr(self.app_ref, 'playback_controller'):
                self._log_message("播放控制器不可用", "ERROR")
                return
            if not self.app_ref.playback_controller:
                self._log_message("播放控制器未初始化", "ERROR")
                return
                
            # 通过播放控制器调用定时功能
            self.app_ref.playback_controller._timing_test_now()
            self._log_message("立即测试播放请求已发送", "INFO")
        except Exception as e:
            self._log_message(f"测试播放失败: {e}", "ERROR")

    def _timing_get_ui_status(self):
        """获取定时服务状态信息"""
        try:
            if not self.app_ref:
                return {}
            if not hasattr(self.app_ref, 'playback_controller'):
                return {}
            if not self.app_ref.playback_controller:
                return {}
                
            # 通过播放控制器获取定时状态
            return self.app_ref.playback_controller._timing_get_ui_status()
        except Exception as e:
            self._log_message(f"获取定时状态失败: {e}", "ERROR")
        return {}

    def _refresh_timing_status(self, delay_ms: int = 0):
        """刷新定时状态显示"""
        def _do():
            try:
                st = self._timing_get_ui_status() or {}
                provider = st.get('provider', 'Local')
                delta = st.get('sys_delta_ms', 0.0)
                rtt = st.get('rtt_ms', 0.0)
                manual = st.get('manual_compensation_ms', 0.0)
                auto_latency = st.get('auto_latency_ms', None)
                net_shift = st.get('net_shift_ms', None)
                local_chain = st.get('local_chain_ms', None)
                next_fire = st.get('next_fire', '')
                remaining = st.get('remaining_ms')
                # 倒计时格式化
                def _fmt_ms(ms):
                    try:
                        ms = int(ms)
                        s, msec = divmod(ms, 1000)
                        h, rem = divmod(s, 3600)
                        m, sec = divmod(rem, 60)
                        return f"{h:02d}:{m:02d}:{sec:02d}.{msec:03d}"
                    except Exception:
                        return "--:--:--.---"
                lines = []
                lines.append(f"来源: {provider}")
                lines.append(f"NTP-本地偏差: {float(delta):.2f} ms")
                lines.append(f"网络往返延迟: {float(rtt):.2f} ms")
                if auto_latency is not None:
                    try:
                        lines.append(f"自动延迟(估计): {float(auto_latency):.2f} ms")
                    except Exception:
                        lines.append(f"自动延迟(估计): {auto_latency} ms")
                lines.append(f"手动补偿: {float(manual):.2f} ms")
                if net_shift is not None:
                    try:
                        lines.append(f"合成偏移(正=延后,负=提前): {float(net_shift):.2f} ms")
                    except Exception:
                        lines.append(f"合成偏移(正=延后,负=提前): {net_shift} ms")
                if local_chain is not None:
                    try:
                        lines.append(f"本地链路延迟: {float(local_chain):.2f} ms")
                    except Exception:
                        lines.append(f"本地链路延迟: {local_chain} ms")
                if next_fire:
                    lines.append(f"下一次: {next_fire}")
                if remaining is not None:
                    lines.append(f"倒计时: {_fmt_ms(remaining)}")
                self.timing_status_var.set("\n".join(lines))
            except Exception:
                pass
            # 循环刷新
            try:
                if hasattr(self, 'app_ref') and self.app_ref and hasattr(self.app_ref, 'root'):
                    self.app_ref.root.after(1000, self._refresh_timing_status)
            except Exception:
                pass
        try:
            if hasattr(self, 'app_ref') and self.app_ref and hasattr(self.app_ref, 'root'):
                self.app_ref.root.after(delay_ms or 0, _do)
            else:
                _do()
        except Exception:
            _do()
