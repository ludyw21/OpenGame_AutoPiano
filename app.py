#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField AutoPiano 主应用程序类
作为模块协调器和应用程序入口点
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
from typing import Dict, Any, Optional

# 导入自定义模块
from event_bus import event_bus, Events
from module_manager import ModuleManager
from ui_manager import UIManager
from meowauto.midi import analyzer, groups
from meowauto.ui.sidebar import Sidebar
from meowauto.ui.yuanshen import YuanShenPage


class MeowFieldAutoPiano:
    """MeowField AutoPiano 主应用程序"""
    
    def __init__(self):
        """初始化应用程序"""
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("MeowField AutoPiano v1.0.3")
        self.root.geometry("1600x980")
        self.root.resizable(True, True)
        
        # 设置窗口图标（如果存在）
        self._set_window_icon()
        
        # 初始化事件总线
        self.event_bus = event_bus
        
        # 初始化模块管理器
        self.module_manager = ModuleManager(self.event_bus)
        
        # 初始化UI管理器
        self.ui_manager = UIManager(self.root, self.event_bus)
        self.current_game = "默认"
        self.yuanshen_page = None
        self.sidebar_win = None
        
        # 注册事件监听器
        self._register_event_listeners()
        
        # 加载模块
        self._load_modules()
        
        # 创建UI组件
        self._create_ui_components()
        # 创建并对接侧边栏
        self._create_sidebar_window()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 绑定热键
        self._bind_hotkeys()
        
        # 发布系统就绪事件
        self.event_bus.publish(Events.SYSTEM_READY, {'version': '1.0.3'}, 'App')
        # 初始化标题后缀
        self._update_titles_suffix(self.current_game)
    
    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_paths = [
                "icon.ico",
                "assets/icon.ico",
                "meowauto/assets/icon.ico"
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
                    break
        except Exception:
            pass
    
    def _bind_hotkeys(self):
        """绑定热键"""
        try:
            # 空格键：播放/暂停
            self.root.bind('<space>', self._on_space_key)
            # ESC键：停止
            self.root.bind('<Escape>', self._on_escape_key)
            # Ctrl+S：停止自动演奏
            self.root.bind('<Control-s>', self._on_ctrl_s_key)
            # Ctrl+Shift+C：停止所有播放（优先绑定全局，降级为窗口内）
            try:
                import threading
                import keyboard  # type: ignore
                def _hotkey_stop():
                    try:
                        # 在主线程调度停止，避免线程问题
                        if hasattr(self, 'root'):
                            self.root.after(0, lambda: (self._stop_auto_play(), self._stop_playback()))
                        else:
                            self._stop_auto_play(); self._stop_playback()
                    except Exception:
                        pass
                # 注册系统级热键（后台线程，避免阻塞）
                def _register_kb():
                    try:
                        keyboard.add_hotkey('ctrl+shift+c', _hotkey_stop, suppress=False)
                    except Exception:
                        pass
                t = threading.Thread(target=_register_kb, daemon=True)
                t.start()
                self._log_message("全局热键已注册: Ctrl+Shift+C (停止播放)")
            except Exception:
                # 回退到窗口级绑定
                self.root.bind('<Control-Shift-C>', lambda e: (self._stop_auto_play(), self._stop_playback()))
                self._log_message("窗口热键已注册: Ctrl+Shift+C (停止播放)")
            
            self._log_message("热键绑定完成: 空格键(开始/暂停/恢复), ESC键(停止), Ctrl+S(停止自动演奏), Ctrl+Shift+C(停止播放)")
        except Exception as e:
            self._log_message(f"热键绑定失败: {str(e)}", "ERROR")
    
    def _on_space_key(self, event):
        """空格键事件处理"""
        try:
            # 如果正在播放，空格键用于暂停/恢复
            if hasattr(self, 'auto_play_button') and self.auto_play_button.cget("text") == "停止弹琴":
                if hasattr(self, 'pause_button') and self.pause_button.cget("text") == "暂停":
                    self._pause_auto_play()
                else:
                    self._resume_auto_play()
            else:
                # 如果没有在播放，空格键用于开始播放
                self._start_auto_play()
        except Exception as e:
            self._log_message(f"空格键处理失败: {str(e)}", "ERROR")
    
    def _on_escape_key(self, event):
        """ESC键事件处理"""
        try:
            # 停止所有播放
            self._stop_auto_play()
            self._stop_playback()
        except Exception as e:
            self._log_message(f"ESC键处理失败: {str(e)}", "ERROR")
    
    def _on_ctrl_s_key(self, event):
        """Ctrl+S键事件处理"""
        try:
            # 停止自动演奏
            self._stop_auto_play()
        except Exception as e:
            self._log_message(f"Ctrl+S键处理失败: {str(e)}", "ERROR")
    
    def _register_event_listeners(self):
        """注册事件监听器"""
        # 模块加载事件
        self.event_bus.subscribe('module.loaded', self._on_module_loaded)
        self.event_bus.subscribe('module.unloaded', self._on_module_unloaded)
        
        # 系统事件
        self.event_bus.subscribe(Events.SYSTEM_ERROR, self._on_system_error)
        self.event_bus.subscribe(Events.SYSTEM_SHUTDOWN, self._on_system_shutdown)
        
        # UI事件
        self.event_bus.subscribe(Events.UI_THEME_CHANGED, self._on_theme_changed)
        self.event_bus.subscribe(Events.UI_LAYOUT_CHANGED, self._on_layout_changed)
        
        # 播放事件
        self.event_bus.subscribe(Events.PLAYBACK_START, self._on_playback_start)
        self.event_bus.subscribe(Events.PLAYBACK_STOP, self._on_playback_stop)
        self.event_bus.subscribe(Events.PLAYBACK_PAUSE, self._on_playback_pause)
        self.event_bus.subscribe(Events.PLAYBACK_RESUME, self._on_playback_resume)
        
        # 文件事件
        self.event_bus.subscribe(Events.FILE_LOADED, self._on_file_loaded)
        self.event_bus.subscribe(Events.FILE_CONVERTED, self._on_file_converted)
        self.event_bus.subscribe(Events.FILE_ERROR, self._on_file_error)
    
    def _load_modules(self):
        """加载所有模块"""
        try:
            self.ui_manager.set_status("正在加载模块...")
            
            # 为模块管理器提供logger实例
            from meowauto.core import Logger
            logger = Logger()
            self.module_manager.logger = logger
            
            # 加载核心模块
            results = self.module_manager.load_all_modules()
            
            # 检查加载结果
            failed_modules = [name for name, success in results.items() if not success]
            if failed_modules:
                error_msg = f"以下模块加载失败: {', '.join(failed_modules)}"
                self.event_bus.publish(Events.SYSTEM_ERROR, {'message': error_msg}, 'App')
                self.ui_manager.set_status(f"模块加载失败: {len(failed_modules)} 个")
                self._log_message(error_msg, "ERROR")
            else:
                self.ui_manager.set_status("所有模块加载完成")
                self.event_bus.publish('system.info', {'message': '所有模块加载成功'}, 'App')
                self._log_message("所有模块加载成功", "SUCCESS")
            
        except Exception as e:
            error_msg = f"模块加载过程中发生错误: {e}"
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': error_msg}, 'App')
            self.ui_manager.set_status("模块加载失败")
            self._log_message(error_msg, "ERROR")
    
    def _create_ui_components(self):
        """创建UI组件"""
        try:
            # 直接创建功能组件，不依赖模块加载状态
            self._create_file_selection_component()
            self._create_playback_control_component()
            self._create_right_pane()
            self._create_bottom_progress()
            
        except Exception as e:
            error_msg = f"创建UI组件失败: {e}"
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': error_msg}, 'App')
        
        # 添加测试数据到播放列表
        self._add_test_playlist_data()

    def _create_sidebar_window(self):
        """创建左侧可折叠的悬浮侧边栏窗口，并与主窗体联动"""
        try:
            self.sidebar_win = tk.Toplevel(self.root)
            self.sidebar_win.overrideredirect(True)
            self.sidebar_win.attributes('-topmost', True)
            # 初始几何
            self.sidebar_width_expanded = 200
            self.sidebar_width_collapsed = 40
            self.sidebar_current_width = self.sidebar_width_collapsed
            # 内容
            container = ttk.Frame(self.sidebar_win, padding=0)
            container.pack(fill=tk.BOTH, expand=True)
            self.sidebar = Sidebar(container, on_action=self._on_sidebar_action, width=self.sidebar_width_expanded)
            self.sidebar.attach(row=0, column=0)
            # 默认折叠
            self.sidebar.toggle()
            # 跟随主窗体移动/缩放（不覆盖已有绑定）
            try:
                self.root.bind('<Configure>', self._on_root_configure, add="+")
            except TypeError:
                # 兼容不支持 add 参数的实现，退而求其次：直接绑定
                self.root.bind('<Configure>', self._on_root_configure)
            self.sidebar.frame.bind('<Configure>', self._on_sidebar_configure)
            self._position_sidebar()
        except Exception as e:
            self._log_message(f"创建侧边栏失败: {e}", "ERROR")

    def _on_sidebar_configure(self, event=None):
        """侧边栏内容尺寸变化时，同步窗口宽度"""
        try:
            # 依据内部frame宽度更新toplevel宽度
            w = max(self.sidebar_width_collapsed, min(self.sidebar_width_expanded, event.width if event else self.sidebar.frame.winfo_width()))
            self.sidebar_current_width = w
            self._position_sidebar()
        except Exception:
            pass

    def _on_root_configure(self, event=None):
        """主窗体移动或尺寸变化时，重定位侧边栏"""
        self._position_sidebar()

    def _position_sidebar(self):
        try:
            x = self.root.winfo_x() - self.sidebar_current_width
            y = self.root.winfo_y()
            h = self.root.winfo_height()
            self.sidebar_win.geometry(f"{self.sidebar_current_width}x{h}+{x}+{y}")
        except Exception:
            pass

    def _on_sidebar_action(self, key: str):
        """侧边栏按钮回调"""
        try:
            if key == 'game-default':
                self._switch_game('开放空间')
            elif key == 'game-yuanshen':
                self._switch_game('原神')
            elif key == 'about':
                self._show_about()
            # 其他功能键可在此扩展
        except Exception as e:
            self._log_message(f"侧边栏事件错误: {e}", "ERROR")

    def _switch_game(self, game_name: str):
        """切换游戏，原神显示占位页，默认恢复主界面"""
        self.current_game = game_name
        is_default = (game_name in ('默认', '开放空间'))
        try:
            # 切换页面内容
            if not is_default:
                # 隐藏主分栏
                try:
                    self.ui_manager.paned_window.forget()
                except Exception:
                    pass
                # 显示占位页
                if self.yuanshen_page is None:
                    self.yuanshen_page = YuanShenPage(self.ui_manager.page_container)
                # 避免重复pack
                if not str(self.yuanshen_page.frame) in [str(c) for c in self.ui_manager.page_container.pack_slaves()]:
                    self.yuanshen_page.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            else:
                # 恢复主分栏
                try:
                    self.ui_manager.paned_window.pack(fill=tk.BOTH, expand=True)
                except Exception:
                    pass
                # 隐藏占位页
                if self.yuanshen_page is not None:
                    try:
                        self.yuanshen_page.frame.pack_forget()
                    except Exception:
                        pass
            # 更新标题
            self._update_titles_suffix(self.current_game)
        except Exception as e:
            self._log_message(f"切换游戏失败: {e}", "ERROR")

    def _show_about(self):
        """显示关于窗口，加载 README.md 内容"""
        try:
            about = tk.Toplevel(self.root)
            about.title("关于 MeowField AutoPiano")
            about.geometry("720x540")
            about.transient(self.root)
            about.grab_set()
            frm = ttk.Frame(about)
            frm.pack(fill=tk.BOTH, expand=True)
            txt = tk.Text(frm, wrap=tk.WORD)
            ybar = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=txt.yview)
            txt.configure(yscrollcommand=ybar.set)
            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ybar.pack(side=tk.RIGHT, fill=tk.Y)
            readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
            content = ''
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"无法读取 README.md: {e}"
            txt.insert(tk.END, content)
            txt.configure(state=tk.DISABLED)
        except Exception as e:
            self._log_message(f"显示关于窗口失败: {e}", "ERROR")

    def _update_titles_suffix(self, game: str | None):
        """更新根窗口和UIManager标题的后缀"""
        try:
            suffix = game if game and game.strip() else None
            # 更新顶部内嵌标题
            if hasattr(self, 'ui_manager') and hasattr(self.ui_manager, 'set_title_suffix'):
                self.ui_manager.set_title_suffix(suffix)
            # 同步根窗口标题
            base = "MeowField AutoPiano v1.0.3"
            self.root.title(f"{base} [{suffix}]") if suffix else self.root.title(base)
        except Exception:
            pass
    
    def _create_file_selection_component(self):
        """创建文件选择组件"""
        try:
            # 在左侧框架中创建文件选择区域
            file_frame = ttk.LabelFrame(self.ui_manager.left_frame, text="文件选择", padding="12")
            file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            
            # 音频文件选择
            ttk.Label(file_frame, text="音频文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            self.mp3_path_var = tk.StringVar()
            mp3_entry = ttk.Entry(file_frame, textvariable=self.mp3_path_var, width=50)
            mp3_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
            ttk.Button(file_frame, text="浏览", command=self._browse_mp3).grid(row=0, column=2)
            
            # MIDI文件选择
            ttk.Label(file_frame, text="MIDI文件:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
            self.midi_path_var = tk.StringVar()
            midi_entry = ttk.Entry(file_frame, textvariable=self.midi_path_var, width=50)
            midi_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
            ttk.Button(file_frame, text="浏览", command=self._browse_midi).grid(row=1, column=2, pady=(5, 0))
            
            # 乐谱文件选择
            ttk.Label(file_frame, text="乐谱文件:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
            self.score_path_var = tk.StringVar()
            score_entry = ttk.Entry(file_frame, textvariable=self.score_path_var, width=50)
            score_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
            ttk.Button(file_frame, text="浏览", command=self._browse_score).grid(row=2, column=2, pady=(5, 0))
            
            # 转换按钮
            convert_frame = ttk.Frame(file_frame)
            convert_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
            
            ttk.Button(convert_frame, text="音频转MIDI", 
                      command=self._convert_mp3_to_midi).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(convert_frame, text="MIDI转LRCp", 
                      command=self._convert_midi_to_lrcp).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(convert_frame, text="批量转换", 
                      command=self._batch_convert).pack(side=tk.LEFT)
            
            # 配置网格权重
            file_frame.columnconfigure(1, weight=1)
            
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建文件选择组件失败: {e}'}, 'App')
    
    def _create_playback_control_component(self):
        """创建播放控制组件"""
        try:
            # 在左侧框架中创建播放控制区域
            control_frame = ttk.LabelFrame(self.ui_manager.left_frame, text="播放控制", padding="12")
            control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            
            # 使用 Notebook 进行分页，避免控件拥挤重叠
            notebook = ttk.Notebook(control_frame)
            notebook.pack(fill=tk.BOTH, expand=True)

            # 各页签
            tab_controls = ttk.Frame(notebook)
            tab_params = ttk.Frame(notebook)
            tab_progress = ttk.Frame(notebook)
            tab_playlist = ttk.Frame(notebook)
            tab_help = ttk.Frame(notebook)

            notebook.add(tab_controls, text="控制")
            notebook.add(tab_params, text="参数")
            notebook.add(tab_progress, text="进度")
            notebook.add(tab_playlist, text="播放列表")
            notebook.add(tab_help, text="帮助")

            # ——— 控制页 ———
            mode_frame = ttk.Frame(tab_controls)
            mode_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
            ttk.Label(mode_frame, text="演奏模式:").pack(side=tk.LEFT, padx=(0, 10))
            self.playback_mode = tk.StringVar(value="midi")
            midi_radio = ttk.Radiobutton(mode_frame, text="MIDI模式", variable=self.playback_mode, value="midi", command=self._on_mode_changed)
            midi_radio.pack(side=tk.LEFT, padx=(0, 10))
            lrcp_radio = ttk.Radiobutton(mode_frame, text="LRCp模式", variable=self.playback_mode, value="lrcp", command=self._on_mode_changed)
            lrcp_radio.pack(side=tk.LEFT, padx=(0, 10))

            button_frame = ttk.Frame(tab_controls)
            button_frame.pack(side=tk.TOP, anchor=tk.W)
            self._create_auto_play_controls(button_frame)
            ttk.Button(button_frame, text="播放MIDI", command=self._play_midi).pack(pady=(0, 5))
            ttk.Button(button_frame, text="停止", command=self._stop_playback).pack()

            # 自定义倒计时（秒）
            countdown_frame = ttk.Frame(tab_controls)
            countdown_frame.pack(side=tk.TOP, anchor=tk.W, pady=(6, 0))
            ttk.Label(countdown_frame, text="倒计时(秒) → ").pack(side=tk.LEFT)
            self.countdown_seconds_var = tk.IntVar(value=3)
            ttk.Spinbox(countdown_frame, from_=0, to=30, increment=1, width=6, textvariable=self.countdown_seconds_var).pack(side=tk.LEFT)

            # 移除：MIDI 预处理设置（已迁移到右侧“后处理(应用于解析结果)”）

            # ——— 参数页 ———
            param_frame = ttk.Frame(tab_params)
            param_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            ttk.Label(param_frame, text="速度:").pack(anchor=tk.W)
            self.tempo_var = tk.DoubleVar(value=1.0)
            # 使用离散速度选项替代连续滑块
            tempo_values = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
            self._tempo_combo = ttk.Combobox(param_frame, state="readonly", values=[str(v) for v in tempo_values])
            # 初始化显示为当前值
            self._tempo_combo.set(f"{self.tempo_var.get():.2f}")
            def _on_tempo_select(event=None):
                try:
                    val = float(self._tempo_combo.get())
                    self.tempo_var.set(val)
                except Exception:
                    pass
            self._tempo_combo.bind('<<ComboboxSelected>>', _on_tempo_select)
            self._tempo_combo.pack(fill=tk.X)
            ttk.Label(param_frame, text="音量:").pack(anchor=tk.W, pady=(10, 0))
            self.volume_var = tk.DoubleVar(value=0.7)
            volume_scale = ttk.Scale(param_frame, from_=0.0, to=1.0, variable=self.volume_var, orient=tk.HORIZONTAL)
            volume_scale.pack(fill=tk.X)
            self.debug_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(param_frame, text="调试模式", variable=self.debug_var, command=self._on_debug_toggle).pack(anchor=tk.W, pady=(10, 0))

            # 移除：“高级”标签页（和弦与调度选项改由右侧或使用默认）

            # ——— 进度页 ———
            progress_frame = ttk.Frame(tab_progress)
            progress_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            self.progress_var = tk.DoubleVar()
            self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
            self.progress_bar.pack(fill=tk.X, pady=(0, 5))
            self.time_var = tk.StringVar(value="00:00 / 00:00")
            time_label = ttk.Label(progress_frame, textvariable=self.time_var)
            time_label.pack(anchor=tk.W)

            # ——— 播放列表页 ———
            playlist_container = ttk.Frame(tab_playlist)
            playlist_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            # 播放列表工具栏
            playlist_toolbar = ttk.Frame(playlist_container)
            playlist_toolbar.pack(fill=tk.X, pady=(0, 5))
            ttk.Button(playlist_toolbar, text="添加文件", command=self._add_to_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="移除选中", command=self._remove_from_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="清空列表", command=self._clear_playlist).pack(side=tk.LEFT)
            ttk.Label(playlist_toolbar, text="播放顺序:").pack(side=tk.LEFT, padx=(12, 4))
            self.playlist_order_var = tk.StringVar(value="顺序")
            ttk.Combobox(playlist_toolbar, textvariable=self.playlist_order_var, state="readonly", width=10,
                         values=["顺序", "随机", "单曲循环"]).pack(side=tk.LEFT)

            # 播放列表显示区域
            playlist_display = ttk.Frame(playlist_container)
            playlist_display.pack(fill=tk.BOTH, expand=True)
            columns = ('序号', '文件名', '类型', '时长', '状态')
            self.playlist_tree = ttk.Treeview(playlist_display, columns=columns, show='headings', height=8)
            for col in columns:
                self.playlist_tree.heading(col, text=col)
                self.playlist_tree.column(col, width=100)
            playlist_scrollbar = ttk.Scrollbar(playlist_display, orient=tk.VERTICAL, command=self.playlist_tree.yview)
            self.playlist_tree.configure(yscrollcommand=playlist_scrollbar.set)
            self.playlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            playlist_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.playlist_tree.bind('<Double-1>', self._on_playlist_double_click)

            # ——— 帮助页 ———
            help_frame = ttk.Frame(tab_help)
            help_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            help_text = (
                "热键说明:\n"
                "• Ctrl+T: 切换主题\n"
                "• Ctrl+D: 切换控件密度\n"
                "• Ctrl+Shift+C: 暂停演奏\n\n"
                "使用说明:\n"
                "1. 选择音频文件 → 点击\"音频转MIDI\"进行转换\n"
                "2. 选择MIDI文件 → 点击\"MIDI转LRCp\"生成乐谱\n"
                "3. 设置演奏模式和参数\n"
                "4. 点击\"自动弹琴\"开始演奏\n"
                "5. 遇到报错不要慌，有点bug是正常的（），启动时控制台那一堆报错不用管，\n遇到其它问题请提issue或者去q群反馈，带好截图和问题描述\n\n"
                "注意: 新版本不自带PianoTrans（音频转换模型），需要单独下载"
            )
            ttk.Label(help_frame, text=help_text, justify=tk.LEFT, wraplength=600).pack(anchor=tk.W, fill=tk.X)
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建播放控制组件失败: {e}'}, 'App')

    def _create_auto_play_controls(self, parent):
        """创建自动弹琴控制按钮"""
        # 自动弹琴按钮
        self.auto_play_button = ttk.Button(parent, text="自动弹琴", command=self._toggle_auto_play)
        self.auto_play_button.pack(pady=(0, 5))
        # 暂停/恢复按钮
        self.pause_button = ttk.Button(parent, text="暂停", command=self._toggle_pause, state="disabled")
        self.pause_button.pack(pady=(0, 5))

    def _create_playlist_component(self):
        """创建播放列表组件"""
        try:
            # 在左侧框架中创建播放列表区域
            playlist_frame = ttk.LabelFrame(self.ui_manager.left_frame, text="播放列表", padding="12")
            playlist_frame.grid(row=2, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
            self.ui_manager.left_frame.rowconfigure(2, weight=1)
            
            # 播放列表工具栏
            playlist_toolbar = ttk.Frame(playlist_frame)
            playlist_toolbar.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Button(playlist_toolbar, text="添加文件", 
                      command=self._add_to_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="移除选中", 
                      command=self._remove_from_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="清空列表", 
                      command=self._clear_playlist).pack(side=tk.LEFT)
            
            # 播放列表显示区域
            playlist_display = ttk.Frame(playlist_frame)
            playlist_display.pack(fill=tk.BOTH, expand=True)
            
            # 创建播放列表树形视图
            columns = ('序号', '文件名', '类型', '时长', '状态')
            self.playlist_tree = ttk.Treeview(playlist_display, columns=columns, show='headings', height=8)
            
            for col in columns:
                self.playlist_tree.heading(col, text=col)
                self.playlist_tree.column(col, width=100)
            
            # 添加滚动条
            playlist_scrollbar = ttk.Scrollbar(playlist_display, orient=tk.VERTICAL, command=self.playlist_tree.yview)
            self.playlist_tree.configure(yscrollcommand=playlist_scrollbar.set)
            
            self.playlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            playlist_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 绑定双击事件
            self.playlist_tree.bind('<Double-1>', self._on_playlist_double_click)
        
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建播放列表组件失败: {e}'}, 'App')

        
    
    def _create_right_pane(self):
        """创建右侧分页：MIDI解析设置 / 事件表 / 系统日志"""
        try:
            notebook = ttk.Notebook(self.ui_manager.right_frame)
            notebook.pack(fill=tk.BOTH, expand=True)

            tab_settings = ttk.Frame(notebook)
            tab_events = ttk.Frame(notebook)
            tab_logs = ttk.Frame(notebook)
            notebook.add(tab_settings, text="MIDI解析设置")
            notebook.add(tab_events, text="事件表")
            notebook.add(tab_logs, text="系统日志")

            # —— 解析设置（加滚动条容器）——
            # 使用 Canvas + Scrollbar 实现整个设置页可滚动
            settings_canvas = tk.Canvas(tab_settings, highlightthickness=0)
            settings_scrollbar = ttk.Scrollbar(tab_settings, orient=tk.VERTICAL, command=settings_canvas.yview)
            settings_inner = ttk.Frame(settings_canvas)
            def _on_inner_config(event=None):
                try:
                    settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
                except Exception:
                    pass
            settings_inner.bind("<Configure>", _on_inner_config)
            settings_canvas.create_window((0, 0), window=settings_inner, anchor="nw")
            settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
            settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Pitch groups
            grp_frame = ttk.LabelFrame(settings_inner, text="音高分组选择", padding="8")
            grp_frame.pack(fill=tk.X, padx=6, pady=6)
            self.pitch_group_vars = {}
            row = 0
            col = 0
            for name in groups.ORDERED_GROUP_NAMES:
                var = tk.BooleanVar(value=True)
                self.pitch_group_vars[name] = var
                ttk.Checkbutton(grp_frame, text=name, variable=var).grid(row=row, column=col, sticky=tk.W, padx=4, pady=2)
                col += 1
                if col % 2 == 0:
                    row += 1
                    col = 0
            btns = ttk.Frame(grp_frame)
            btns.grid(row=row+1, column=0, columnspan=2, sticky=tk.W)
            ttk.Button(btns, text="全选", command=lambda: [v.set(True) for v in self.pitch_group_vars.values()]).pack(side=tk.LEFT, padx=(0,6))
            ttk.Button(btns, text="全不选", command=lambda: [v.set(False) for v in self.pitch_group_vars.values()]).pack(side=tk.LEFT)

            # Melody extraction and channel filter
            mel_frame = ttk.LabelFrame(settings_inner, text="主旋律提取", padding="8")
            mel_frame.pack(fill=tk.X, padx=6, pady=6)
            self.enable_melody_extract_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(mel_frame, text="启用主旋律提取", variable=self.enable_melody_extract_var).grid(row=0, column=0, sticky=tk.W)
            ttk.Label(mel_frame, text="优先通道").grid(row=0, column=1, sticky=tk.W, padx=(12,0))
            self.melody_channel_var = tk.StringVar(value="自动")
            self.melody_channel_combo = ttk.Combobox(mel_frame, textvariable=self.melody_channel_var, state="readonly",
                                                     values=["自动"] + [str(i) for i in range(16)])
            self.melody_channel_combo.grid(row=0, column=2, sticky=tk.W)
            tip = "通道筛选与音高/节奏熵启发式：优先中高音(60-84)，节奏熵较低且连贯的声部更可能是主旋律。"
            ttk.Label(mel_frame, text=tip, wraplength=520, foreground="#666").grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(6,0))
            # 熵权重与最小得分
            ttk.Label(mel_frame, text="熵权重").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
            self.entropy_weight_var = tk.DoubleVar(value=0.5)
            ttk.Spinbox(mel_frame, from_=0.0, to=5.0, increment=0.1, textvariable=self.entropy_weight_var, width=8).grid(row=2, column=1, sticky=tk.W)
            ttk.Label(mel_frame, text="最小得分(过滤力度)").grid(row=2, column=2, sticky=tk.W, padx=(12,0))
            self.melody_min_score_var = tk.DoubleVar(value=0.0)
            ttk.Spinbox(mel_frame, from_=-100.0, to=100.0, increment=0.5, textvariable=self.melody_min_score_var, width=10).grid(row=2, column=3, sticky=tk.W)
            # 挡位（预设更激进）
            ttk.Label(mel_frame, text="挡位").grid(row=3, column=0, sticky=tk.W, pady=(6,0))
            self.melody_level_var = tk.StringVar(value="中")
            self.melody_level_combo = ttk.Combobox(mel_frame, textvariable=self.melody_level_var, state="readonly",
                                                   values=["弱", "中", "强", "极强"]) 
            self.melody_level_combo.grid(row=3, column=1, sticky=tk.W)
            def _apply_melody_level(*_):
                level = self.melody_level_var.get()
                # 更激进：提高熵权重与最小得分
                presets = {
                    "弱": (0.5, -10.0),
                    "中": (1.0, 0.0),
                    "强": (1.5, 5.0),
                    "极强": (2.5, 12.0),
                }
                ew, ms = presets.get(level, (1.0, 0.0))
                self.entropy_weight_var.set(ew)
                self.melody_min_score_var.set(ms)
            self.melody_level_combo.bind('<<ComboboxSelected>>', _apply_melody_level)

            # 提取算法与过滤参数
            ttk.Label(mel_frame, text="算法").grid(row=4, column=0, sticky=tk.W, pady=(6,0))
            self.melody_mode_var = tk.StringVar(value="熵启发")
            self.melody_mode_combo = ttk.Combobox(
                mel_frame, textvariable=self.melody_mode_var, state="readonly",
                values=["熵启发", "节拍过滤", "重复过滤", "混合"]
            )
            self.melody_mode_combo.grid(row=4, column=1, sticky=tk.W)
            ttk.Label(mel_frame, text="强度(0-1)").grid(row=4, column=2, sticky=tk.W, padx=(12,0))
            self.melody_strength_var = tk.DoubleVar(value=0.5)
            ttk.Spinbox(mel_frame, from_=0.0, to=1.0, increment=0.05, textvariable=self.melody_strength_var, width=8).grid(row=4, column=3, sticky=tk.W)
            ttk.Label(mel_frame, text="重复惩罚").grid(row=5, column=0, sticky=tk.W, pady=(6,0))
            self.melody_rep_penalty_var = tk.DoubleVar(value=1.0)
            ttk.Spinbox(mel_frame, from_=0.0, to=5.0, increment=0.1, textvariable=self.melody_rep_penalty_var, width=8).grid(row=5, column=1, sticky=tk.W)

            # Post-processing controls
            pp_frame = ttk.LabelFrame(settings_inner, text="后处理(应用于解析结果)", padding="8")
            pp_frame.pack(fill=tk.X, padx=6, pady=6)
            self.enable_postproc_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(pp_frame, text="启用后处理", variable=self.enable_postproc_var).grid(row=0, column=0, sticky=tk.W)
            ttk.Label(pp_frame, text="黑键移调").grid(row=0, column=1, sticky=tk.W, padx=(12,0))
            self.black_transpose_strategy_var = tk.StringVar(value="就近")
            self.black_transpose_combo = ttk.Combobox(pp_frame, textvariable=self.black_transpose_strategy_var, state="readonly",
                                                      values=["关闭", "向下", "就近"])
            self.black_transpose_combo.grid(row=0, column=2, sticky=tk.W)
            ttk.Label(pp_frame, text="量化窗口(ms)").grid(row=0, column=3, sticky=tk.W, padx=(12,0))
            self.quantize_window_var = tk.IntVar(value=30)
            ttk.Spinbox(pp_frame, from_=1, to=200, increment=1, textvariable=self.quantize_window_var, width=8).grid(row=0, column=4, sticky=tk.W)
            ttk.Label(pp_frame, text="BPM").grid(row=0, column=5, sticky=tk.W, padx=(12,0))
            self.bpm_var = tk.IntVar(value=100)
            ttk.Spinbox(pp_frame, from_=20, to=300, increment=1, textvariable=self.bpm_var, width=8).grid(row=0, column=6, sticky=tk.W)
            # 高级功能：和弦识别（基于窗口对齐）
            self.enable_chord_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(pp_frame, text="识别和弦(同窗同按计为和弦)", variable=self.enable_chord_var).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(6,0))

            # 迁移：和弦键位设置（用于回放阶段）
            chord_frame = ttk.LabelFrame(settings_inner, text="回放和弦键位设置", padding="8")
            chord_frame.pack(fill=tk.X, padx=6, pady=(0,6))
            self.r_enable_chord_keys_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                chord_frame,
                text="启用和弦按键 (C,Dm,Em,F,G,Am,G7 -> z,x,c,v,b,n,m)",
                variable=self.r_enable_chord_keys_var,
                command=self._on_player_options_changed,
            ).grid(row=0, column=0, columnspan=3, sticky=tk.W)
            self.r_chord_drop_root_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                chord_frame,
                text="使用和弦键时去除根音",
                variable=self.r_chord_drop_root_var,
                command=self._on_player_options_changed,
            ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(4,0))
            ttk.Label(chord_frame, text="和弦识别模式").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
            self.r_chord_mode_var = tk.StringVar(value="贪心匹配")
            ttk.Combobox(
                chord_frame,
                textvariable=self.r_chord_mode_var,
                state="readonly",
                values=["七和弦优先", "仅三和弦", "贪心匹配"],
            ).grid(row=2, column=1, sticky=tk.W)
            ttk.Label(chord_frame, text="和弦最小延音(ms)").grid(row=2, column=2, sticky=tk.W, padx=(12,0))
            self.r_chord_min_sustain_var = tk.IntVar(value=1500)
            ttk.Spinbox(chord_frame, from_=0, to=5000, increment=10, textvariable=self.r_chord_min_sustain_var, width=8, command=self._on_player_options_changed).grid(row=2, column=3, sticky=tk.W)

            # Analyze button
            act_frame = ttk.Frame(settings_inner)
            act_frame.pack(fill=tk.X, padx=6, pady=(0,6))
            ttk.Button(act_frame, text="解析当前MIDI", command=self._analyze_current_midi).pack(side=tk.LEFT)

            # —— 事件表 ——
            ev_toolbar = ttk.Frame(tab_events)
            ev_toolbar.pack(fill=tk.X, pady=(6,2), padx=6)
            ttk.Button(ev_toolbar, text="刷新", command=self._populate_event_table).pack(side=tk.LEFT)
            ttk.Button(ev_toolbar, text="导出CSV", command=self._export_event_csv).pack(side=tk.LEFT, padx=(6,0))
            ttk.Button(ev_toolbar, text="导出按键谱", command=self._export_key_notation).pack(side=tk.LEFT, padx=(6,0))

            ev_container = ttk.Frame(tab_events)
            ev_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            columns = ("序号", "开始(s)", "类型", "音符", "通道", "组", "结束(s)", "时长(s)", "和弦")
            self.event_tree = ttk.Treeview(ev_container, columns=columns, show='headings')
            for col in columns:
                self.event_tree.heading(col, text=col)
                self.event_tree.column(col, width=100, anchor=tk.CENTER)
            ybar = ttk.Scrollbar(ev_container, orient=tk.VERTICAL, command=self.event_tree.yview)
            self.event_tree.configure(yscrollcommand=ybar.set)
            self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ybar.pack(side=tk.RIGHT, fill=tk.Y)
            # 启用单元格编辑：双击进入编辑
            self.event_tree.bind('<Double-1>', self._on_event_tree_double_click)

            # —— 系统日志 ——
            log_toolbar = ttk.Frame(tab_logs)
            log_toolbar.pack(fill=tk.X, pady=(6, 5), padx=6)
            ttk.Button(log_toolbar, text="清空日志", command=self._clear_log).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(log_toolbar, text="保存日志", command=self._save_log).pack(side=tk.LEFT)
            self.log_text = tk.Text(tab_logs, height=20, width=50)
            self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))
            # 初始日志
            self.log_text.insert(tk.END, "🎹 MeowField AutoPiano v1.0.2 启动成功\n")
            self.log_text.insert(tk.END, "支持功能: MP3转MIDI、MIDI播放、自动弹琴、批量转换\n")
            self.log_text.insert(tk.END, "=" * 50 + "\n")
            self.log_text.insert(tk.END, "系统就绪，可以开始使用...\n")
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建右侧分页失败: {e}'}, 'App')

    def _create_bottom_progress(self):
        """在主窗口左下角创建播放进度显示"""
        try:
            bottom = ttk.Frame(self.ui_manager.left_frame)
            bottom.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(6, 0))
            self.ui_manager.left_frame.rowconfigure(3, weight=0)
            self.bottom_progress_var = tk.DoubleVar()
            self.bottom_progress = ttk.Progressbar(bottom, variable=self.bottom_progress_var, maximum=100)
            self.bottom_progress.pack(fill=tk.X)
            self.bottom_time_var = tk.StringVar(value="00:00 / 00:00")
            ttk.Label(bottom, textvariable=self.bottom_time_var).pack(anchor=tk.W)
            # 若已有进度条，保持同步
            self._sync_progress_targets = True
        except Exception:
            pass

    def _sync_progress(self, value: float, time_text: str):
        """同步进度到底部与原进度标签（若存在）"""
        try:
            self.bottom_progress_var.set(value)
            self.bottom_time_var.set(time_text)
            if hasattr(self, 'progress_var'):
                self.progress_var.set(value)
            if hasattr(self, 'time_var'):
                self.time_var.set(time_text)
        except Exception:
            pass

    def _on_event_tree_double_click(self, event):
        """双击编辑事件表单元格"""
        try:
            region = self.event_tree.identify('region', event.x, event.y)
            if region != 'cell':
                return
            row_id = self.event_tree.identify_row(event.y)
            col_id = self.event_tree.identify_column(event.x)
            if not row_id or not col_id:
                return
            col_index = int(col_id.replace('#', '')) - 1
            bbox = self.event_tree.bbox(row_id, col_id)
            if not bbox:
                return
            x, y, w, h = bbox
            value_list = list(self.event_tree.item(row_id, 'values'))
            old_val = value_list[col_index] if col_index < len(value_list) else ''
            # 创建覆盖输入框
            edit = ttk.Entry(self.event_tree)
            edit.insert(0, str(old_val))
            edit.place(x=x, y=y, width=w, height=h)

            def commit(event=None):
                try:
                    new_val = edit.get()
                    value_list[col_index] = new_val
                    self.event_tree.item(row_id, values=value_list)
                finally:
                    edit.destroy()

            edit.bind('<Return>', commit)
            edit.bind('<FocusOut>', commit)
            edit.focus_set()
        except Exception:
            pass

    def _analyze_current_midi(self):
        """解析当前选择的 MIDI，应用分组筛选与主旋律提取，填充事件表"""
        try:
            midi_path = getattr(self, 'midi_path_var', None).get() if hasattr(self, 'midi_path_var') else ''
            if not midi_path or not os.path.exists(midi_path):
                messagebox.showerror("错误", "请先在上方选择有效的MIDI文件")
                return
            self._log_message(f"开始解析MIDI: {os.path.basename(midi_path)}")
            res = analyzer.parse_midi(midi_path)
            if not res.get('ok'):
                messagebox.showerror("错误", f"解析失败: {res.get('error')}")
                return
            notes = res.get('notes', [])
            total_before = len(notes)
            self._log_message(f"原始音符数: {total_before}")
            # update channel combo with detected channels
            channels = res.get('channels', [])
            self.melody_channel_combo.configure(values=["自动"] + [str(c) for c in channels])

            # filter by selected groups
            selected = [name for name, v in self.pitch_group_vars.items() if v.get()]
            notes = groups.filter_notes_by_groups(notes, selected)
            after_group = len(notes)
            self._log_message(f"分组筛选后音符数: {after_group} (选择组: {','.join(selected) if selected else '无'})")

            # melody extraction
            if bool(self.enable_melody_extract_var.get()):
                try:
                    ch_text = self.melody_channel_var.get()
                    prefer = None if ch_text in ("自动", "", None) else int(ch_text)
                    ew = float(self.entropy_weight_var.get()) if hasattr(self, 'entropy_weight_var') else 0.5
                    ms = float(self.melody_min_score_var.get()) if hasattr(self, 'melody_min_score_var') else None
                    # 模式映射
                    mode_disp = getattr(self, 'melody_mode_var', tk.StringVar(value='熵启发')).get()
                    mode_map = {
                        '熵启发': 'entropy',
                        '节拍过滤': 'beat',
                        '重复过滤': 'repetition',
                        '混合': 'hybrid',
                    }
                    mode = mode_map.get(mode_disp, 'entropy')
                    strength = float(getattr(self, 'melody_strength_var', tk.DoubleVar(value=0.5)).get())
                    rep_pen = float(getattr(self, 'melody_rep_penalty_var', tk.DoubleVar(value=1.0)).get())
                    self._log_message(
                        f"主旋律提取 开启 | 模式: {mode_disp}({mode}) | 强度: {strength:.2f} | 重复惩罚: {rep_pen:.2f} | 熵权重: {ew:.2f} | 最小得分: {ms if ms is not None else '无'} | 优先通道: {ch_text}")
                    before_mel = len(notes)
                    notes = analyzer.extract_melody(
                        notes,
                        prefer_channel=prefer,
                        entropy_weight=ew,
                        min_score=ms,
                        mode=mode,
                        strength=strength,
                        repetition_penalty=rep_pen,
                    )
                    after_mel = len(notes)
                    # 估计通道（多数票）
                    try:
                        from collections import Counter
                        ch_count = Counter([n.get('channel', 0) for n in notes])
                        chosen_ch = ch_count.most_common(1)[0][0] if ch_count else '未知'
                    except Exception:
                        chosen_ch = '未知'
                    self._log_message(f"主旋律提取后音符数: {after_mel} (原有 {before_mel}) | 估计通道: {chosen_ch}")
                except Exception as ex_mel:
                    self._log_message(f"主旋律提取过程异常: {ex_mel}", "ERROR")

            # 后处理：黑键移调 + 分组量化 + 和弦标注
            if bool(getattr(self, 'enable_postproc_var', tk.BooleanVar(value=False)).get()):
                # 黑键移调
                strat = (self.black_transpose_strategy_var.get() if hasattr(self, 'black_transpose_strategy_var') else "关闭")
                if strat != "关闭":
                    def _to_white(note: int) -> int:
                        pc = note % 12
                        white = {0,2,4,5,7,9,11}
                        if pc in white:
                            return note
                        if strat == "向下":
                            for d in range(1,7):
                                cand = (pc - d) % 12
                                if cand in white:
                                    return (note - pc) + cand
                            return note
                        # 就近
                        best = None
                        bestd = 99
                        for w in (0,2,4,5,7,9,11):
                            dist = min((pc - w) % 12, (w - pc) % 12)
                            if dist < bestd:
                                bestd = dist
                                best = w
                        return (note - pc) + (best if best is not None else pc)
                    for n in notes:
                        n['note'] = _to_white(int(n.get('note', 0)))
                        n['group'] = groups.group_for_note(n['note'])
                # 时间窗口分组(量化)：仅对起始时间进行对齐
                try:
                    from meowauto.utils import midi_tools as _mt
                    win = int(self.quantize_window_var.get()) if hasattr(self, 'quantize_window_var') else 30
                    notes = _mt.group_window(notes, window_ms=max(1, win))
                except Exception:
                    pass
                # 和弦标注：同一时刻(窗口对齐后)若同时按下>=2音，标注和弦大小
                if bool(getattr(self, 'enable_chord_var', tk.BooleanVar(value=False)).get()):
                    from collections import defaultdict
                    bucket = defaultdict(list)
                    for n in notes:
                        bucket[round(float(n.get('start_time', 0.0)), 6)].append(n)
                    for t, arr in bucket.items():
                        if len(arr) >= 2:
                            for n in arr:
                                n['is_chord'] = True
                                n['chord_size'] = len(arr)
                        else:
                            for n in arr:
                                n['is_chord'] = False
                                n['chord_size'] = 1

            # expand to event rows (on/off)
            # 保存供回放使用的分析结果与对应文件
            self.analysis_notes = notes
            self.analysis_file = midi_path
            self._populate_event_table()
            self._log_message(
                f"MIDI解析完成: {len(notes)} 条音符；分组筛选: {len(selected)} 组；主旋律提取: {'开启' if self.enable_melody_extract_var.get() else '关闭'}")
        except Exception as e:
            self._log_message(f"MIDI解析异常: {e}", "ERROR")

    def _populate_event_table(self):
        """根据 self.analysis_notes 填充事件表"""
        try:
            if not hasattr(self, 'event_tree'):
                return
            # clear
            for item in self.event_tree.get_children():
                self.event_tree.delete(item)
            notes = getattr(self, 'analysis_notes', []) or []
            rows = []
            seq = 1
            for n in sorted(notes, key=lambda x: (x.get('start_time', 0.0), x.get('note', 0))):
                st = round(float(n.get('start_time', 0.0)), 3)
                et = round(float(n.get('end_time', n.get('start_time', 0.0))), 3)
                dur = round(max(0.0, et - st), 3)
                ch = n.get('channel', 0)
                note = n.get('note', 0)
                grp = n.get('group', groups.group_for_note(note))
                chord_col = ''
                if n.get('is_chord'):
                    chord_col = f"{int(n.get('chord_size', 0))}声部"
                # 在 note_on 行展示结束时间与时长；note_off 行仅展示结束时间
                rows.append((seq, st, 'note_on', note, ch, grp, et, dur, chord_col))
                seq += 1
                rows.append((seq, et, 'note_off', note, ch, grp, et, '', ''))
                seq += 1
            for r in rows:
                self.event_tree.insert('', tk.END, values=r)
        except Exception as e:
            self._log_message(f"填充事件表失败: {e}", "ERROR")
    
    def _create_help_component(self):
        """创建帮助说明组件"""
        try:
            # 在左侧框架中创建帮助说明区域
            help_frame = ttk.LabelFrame(self.ui_manager.left_frame, text="帮助说明", padding="12")
            help_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            
            # 帮助文本
            help_text = """热键说明:
• 空格: 开始/暂停/恢复
• ESC: 停止
• Ctrl+S: 停止自动演奏
• Ctrl+Shift+C: 停止所有播放（支持全局热键，若系统允许）
• Ctrl+T: 切换主题
• Ctrl+D: 切换控件密度

使用说明:
1. 选择音频文件 → 点击"音频转MIDI"进行转换
2. 选择MIDI文件 → 点击"解析当前MIDI"查看事件，并在右侧设置主旋律提取与后处理
3. 设置演奏模式和参数；可在左侧设置倒计时（默认3秒，可取消）
4. 点击"自动弹琴"开始演奏

注意: 新版本不自带PianoTrans（音频转换模型），需要单独下载"""
            
            help_label = ttk.Label(help_frame, text=help_text, justify=tk.LEFT, wraplength=600)
            help_label.pack(fill=tk.X)
            
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建帮助组件失败: {e}'}, 'App')
    
    # 事件处理方法
    def _on_module_loaded(self, event):
        """模块加载完成事件"""
        module_name = event.data.get('module_name')
        instances = event.data.get('instances', [])
        self.ui_manager.set_status(f"模块 {module_name} 加载完成: {', '.join(instances)}")
        self._log_message(f"模块 {module_name} 加载完成: {', '.join(instances)}")
    
    def _on_module_unloaded(self, event):
        """模块卸载完成事件"""
        module_name = event.data.get('module_name')
        self.ui_manager.set_status(f"模块 {module_name} 已卸载")
        self._log_message(f"模块 {module_name} 已卸载")
    
    def _on_system_error(self, event):
        """系统错误事件"""
        message = event.data.get('message', '未知错误')
        self.ui_manager.set_status(f"错误: {message}")
        self._log_message(f"错误: {message}", "ERROR")
    
    def _on_system_shutdown(self, event):
        """系统关闭事件"""
        self.root.quit()
    
    def _on_theme_changed(self, event):
        """主题改变事件"""
        theme = event.data.get('theme')
        mode = event.data.get('mode')
        self.ui_manager.set_status(f"主题已切换: {theme} ({mode})")
        self._log_message(f"主题已切换: {theme} ({mode})")
    
    def _on_layout_changed(self, event):
        """布局改变事件"""
        width = event.data.get('width')
        height = event.data.get('height')
        self.ui_manager.set_status(f"布局已调整: {width}x{height}")
        self._log_message(f"布局已调整: {width}x{height}")
    
    def _on_playback_start(self, event):
        """播放开始事件"""
        self.ui_manager.set_status("播放已开始")
        self._log_message("播放已开始")
    
    def _on_playback_stop(self, event):
        """播放停止事件"""
        self.ui_manager.set_status("播放已停止")
        self._log_message("播放已停止")
    
    def _on_playback_pause(self, event):
        """播放暂停事件"""
        self.ui_manager.set_status("播放已暂停")
        self._log_message("播放已暂停")
    
    def _on_playback_resume(self, event):
        """播放继续事件"""
        self.ui_manager.set_status("播放已继续")
        self._log_message("播放已继续")
    
    def _on_file_loaded(self, event):
        """文件加载事件"""
        file_path = event.data.get('file_path', '未知文件')
        self.ui_manager.set_status(f"文件已加载: {os.path.basename(file_path)}")
        self._log_message(f"文件已加载: {os.path.basename(file_path)}")
    
    def _on_file_converted(self, event):
        """文件转换事件"""
        file_path = event.data.get('file_path', '未知文件')
        self.ui_manager.set_status(f"文件转换完成: {os.path.basename(file_path)}")
        self._log_message(f"文件转换完成: {os.path.basename(file_path)}")
    
    def _on_file_error(self, event):
        """文件错误事件"""
        error_msg = event.data.get('error', '未知错误')
        self.ui_manager.set_status(f"文件操作失败: {error_msg}")
        self._log_message(f"文件操作失败: {error_msg}", "ERROR")
    
    # 功能方法
    def _browse_mp3(self):
        """浏览音频文件"""
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg"),
                ("MP3文件", "*.mp3"),
                ("WAV文件", "*.wav"),
                ("FLAC文件", "*.flac"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.mp3_path_var.set(file_path)
            self._log_message(f"已选择音频文件: {file_path}")
    
    def _browse_midi(self):
        """浏览MIDI文件"""
        file_path = filedialog.askopenfilename(
            title="选择MIDI文件",
            filetypes=[("MIDI文件", "*.mid;*.midi"), ("所有文件", "*.*")]
        )
        if file_path:
            self.midi_path_var.set(file_path)
            self._log_message(f"已选择MIDI文件: {file_path}")
            
            # 自动切换到MIDI模式
            self.playback_mode.set("midi")
            self._log_message("已自动切换到MIDI演奏模式", "INFO")
            self.ui_manager.set_status("MIDI演奏模式")
            
            # 自动添加到播放列表
            self._add_file_to_playlist(file_path, "MIDI文件")
            # 自动解析MIDI
            try:
                self._analyze_current_midi()
            except Exception as e:
                self._log_message(f"自动解析MIDI失败: {e}", "ERROR")
    
    def _browse_score(self):
        """浏览乐谱文件"""
        file_path = filedialog.askopenfilename(
            title="选择乐谱文件 (.lrcp)",
            filetypes=[("乐谱文件", "*.lrcp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.score_path_var.set(file_path)
            self._log_message(f"已选择乐谱文件: {file_path}")
            
            # 自动切换到LRCp模式
            self.playback_mode.set("lrcp")
            self._log_message("已自动切换到LRCp演奏模式", "INFO")
            self.ui_manager.set_status("LRCp演奏模式")
    
    def _convert_mp3_to_midi(self):
        """转换音频到MIDI"""
        audio_path = self.mp3_path_var.get()
        if not audio_path:
            messagebox.showerror("错误", "请先选择音频文件")
            return
        
        if not os.path.exists(audio_path):
            messagebox.showerror("错误", "音频文件不存在")
            return
        
        self._log_message("开始转换音频到MIDI...")
        self.ui_manager.set_status("正在转换...")
        
        try:
            # 检查PianoTrans模型路径
            pianotrans_path = "PianoTrans-v1.0"
            if not os.path.exists(pianotrans_path):
                self._log_message("PianoTrans模型目录不存在", "ERROR")
                messagebox.showerror("错误", f"PianoTrans模型目录不存在: {pianotrans_path}\n\n请确保PianoTrans-v1.0目录在程序根目录下")
                return
            
            # 尝试使用meowauto模块中的音频转换功能
            from meowauto.audio import AudioConverter
            from meowauto.core import Logger
            
            # 创建转换器实例
            logger = Logger()
            converter = AudioConverter(logger)
            
            # 执行转换
            output_path = os.path.splitext(audio_path)[0] + ".mid"
            success = converter.convert_audio_to_midi(audio_path, output_path)
            
            if success:
                self._log_message(f"音频转换成功: {output_path}", "SUCCESS")
                self.ui_manager.set_status("音频转换完成")
                messagebox.showinfo("成功", f"音频文件已转换为MIDI格式\n保存位置: {output_path}")
                
                # 自动添加到播放列表
                self._add_file_to_playlist(output_path, "MIDI文件")
            else:
                self._log_message("音频转换失败", "ERROR")
                self.ui_manager.set_status("音频转换失败")
                messagebox.showerror("错误", "音频转换失败，请检查文件格式和PianoTrans模型")
                
        except ImportError:
            self._log_message("音频转换模块不可用", "ERROR")
            messagebox.showerror("错误", "音频转换模块不可用，请检查meowauto模块")
        except Exception as e:
            self._log_message(f"音频转换异常: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"音频转换过程中发生错误:\n{str(e)}")
    
    def _convert_midi_to_lrcp(self):
        """转换MIDI到LRCp"""
        midi_path = self.midi_path_var.get()
        if not midi_path:
            messagebox.showerror("错误", "请先选择MIDI文件")
            return
        
        if not os.path.exists(midi_path):
            messagebox.showerror("错误", "MIDI文件不存在")
            return
        
        self._log_message("开始转换MIDI到LRCp...")
        self.ui_manager.set_status("正在转换...")
        
        try:
            # 尝试使用meowauto模块中的转换功能
            from meowauto.music import LrcpConverter
            from meowauto.core import ConfigManager
            
            # 创建转换器实例
            config = ConfigManager()
            converter = LrcpConverter(config)
            
            # 执行转换
            output_path = os.path.splitext(midi_path)[0] + ".lrcp"
            success = converter.convert_midi_to_lrcp(midi_path, output_path)
            
            if success:
                self._log_message(f"MIDI转换成功: {output_path}", "SUCCESS")
                self.ui_manager.set_status("MIDI转换完成")
                messagebox.showinfo("成功", f"MIDI文件已转换为LRCp格式\n保存位置: {output_path}")
                
                # 自动添加到播放列表
                self._add_file_to_playlist(output_path, "LRCp乐谱")
            else:
                self._log_message("MIDI转换失败", "ERROR")
                self.ui_manager.set_status("MIDI转换失败")
                messagebox.showerror("错误", "MIDI转换失败，请检查文件格式")
                
        except ImportError:
            self._log_message("MIDI转换模块不可用", "ERROR")
            messagebox.showerror("错误", "MIDI转换模块不可用，请检查meowauto模块")
        except Exception as e:
            self._log_message(f"MIDI转换异常: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"MIDI转换过程中发生错误:\n{str(e)}")
    
    def _batch_convert(self):
        """批量转换"""
        folder_path = filedialog.askdirectory(title="选择包含音频文件的文件夹")
        if not folder_path:
            return
        
        self._log_message(f"开始批量转换文件夹: {folder_path}")
        self.ui_manager.set_status("正在批量转换...")
        
        # 批量转换功能待实现
        self._log_message("批量转换功能待实现", "WARNING")
        messagebox.showinfo("提示", "批量转换功能正在开发中，敬请期待")
    
    def _toggle_auto_play(self):
        """切换自动弹琴"""
        # 若正在倒计时，视为取消
        if getattr(self, '_counting_down', False):
            try:
                if hasattr(self, 'root') and getattr(self, '_countdown_job', None):
                    self.root.after_cancel(self._countdown_job)
            except Exception:
                pass
            self._counting_down = False
            self._countdown_job = None
            self.ui_manager.set_status("已取消倒计时")
            self._log_message("已取消倒计时")
            self.auto_play_button.configure(text="自动弹琴")
            return

        if self.auto_play_button.cget("text") == "自动弹琴":
            # 开始自动弹琴（带倒计时）
            secs = 0
            try:
                secs = int(self.countdown_seconds_var.get()) if hasattr(self, 'countdown_seconds_var') else 0
            except Exception:
                secs = 0
            if secs <= 0:
                self._start_auto_play()
                return
            # 执行倒计时
            self._counting_down = True
            self.auto_play_button.configure(text=f"倒计时{secs}s(点击取消)")
            self.pause_button.configure(state="disabled")
            self.ui_manager.set_status(f"{secs} 秒后开始自动弹琴...")

            def tick(remaining):
                if not getattr(self, '_counting_down', False):
                    return
                if remaining <= 0:
                    self._counting_down = False
                    self._countdown_job = None
                    self.auto_play_button.configure(text="自动弹琴")
                    # 开始
                    self._start_auto_play()
                    return
                try:
                    self.auto_play_button.configure(text=f"倒计时{remaining}s(点击取消)")
                    self.ui_manager.set_status(f"{remaining} 秒后开始自动弹琴...")
                except Exception:
                    pass
                if hasattr(self, 'root'):
                    self._countdown_job = self.root.after(1000, lambda: tick(remaining - 1))
                else:
                    # 退化处理：无 root.after 时直接开始
                    self._counting_down = False
                    self._start_auto_play()
            tick(secs)
        else:
            # 停止自动弹琴
            self._stop_auto_play()
    
    def _toggle_pause(self):
        """切换暂停/恢复状态"""
        # 检查是否有MIDI播放器在播放
        if hasattr(self, 'midi_player') and self.midi_player and self.midi_player.is_playing:
            if self.midi_player.is_paused:
                # 恢复MIDI播放
                self._resume_midi_play()
            else:
                # 暂停MIDI播放
                self._pause_midi_play()
            return
        
        # 检查是否有自动演奏器在播放
        if hasattr(self, 'auto_player') and self.auto_player and self.auto_player.is_playing:
            if self.auto_player.is_paused:
                # 恢复自动演奏
                self._resume_auto_play()
            else:
                # 暂停自动演奏
                self._pause_auto_play()
            return
        
        # 没有正在播放的内容
        self._log_message("没有正在播放的内容", "WARNING")
    
    def _on_mode_changed(self):
        """演奏模式变化处理"""
        mode = self.playback_mode.get()
        if mode == "midi":
            self._log_message("已切换到MIDI演奏模式", "INFO")
            self.ui_manager.set_status("MIDI演奏模式")
        elif mode == "lrcp":
            self._log_message("已切换到LRCp演奏模式", "INFO")
            self.ui_manager.set_status("LRCp演奏模式")
    
    def _on_debug_toggle(self):
        """调试模式开关联动 AutoPlayer"""
        try:
            enabled = self.debug_var.get() if hasattr(self, 'debug_var') else False
            if hasattr(self, 'auto_player') and self.auto_player:
                # 动态切换 AutoPlayer 调试模式
                if hasattr(self.auto_player, 'set_debug'):
                    self.auto_player.set_debug(bool(enabled))
                # 同步一次高级选项（避免调试过程中遗漏）
                self._apply_player_options()
            self._log_message(f"调试模式: {'开启' if enabled else '关闭'}", "INFO")
        except Exception as e:
            self._log_message(f"切换调试模式失败: {str(e)}", "ERROR")

    def _on_player_options_changed(self):
        """高级回放设置变更时，实时下发到 AutoPlayer（若存在）"""
        try:
            self._apply_player_options()
        except Exception as e:
            self._log_message(f"应用回放设置失败: {str(e)}", "ERROR")

    def _apply_player_options(self):
        """将 UI 的高级设置应用到 AutoPlayer"""
        try:
            if hasattr(self, 'auto_player') and self.auto_player and hasattr(self.auto_player, 'set_options'):
                allow_rt = bool(self.allow_retrigger_var.get()) if hasattr(self, 'allow_retrigger_var') else True
                gap_ms = int(self.retrigger_gap_var.get()) if hasattr(self, 'retrigger_gap_var') else 40
                eps_ms = int(self.epsilon_var.get()) if hasattr(self, 'epsilon_var') else 6
                send_ahead_ms = int(self.send_ahead_var.get()) if hasattr(self, 'send_ahead_var') else 2
                spin_threshold_ms = int(self.spin_threshold_var.get()) if hasattr(self, 'spin_threshold_var') else 1
                post_action_sleep_ms = int(self.post_action_sleep_var.get()) if hasattr(self, 'post_action_sleep_var') else 0
                # 迁移到右侧：优先读取右侧变量，其次回退到左侧旧变量
                if hasattr(self, 'r_enable_chord_keys_var'):
                    enable_chord_keys = bool(self.r_enable_chord_keys_var.get())
                else:
                    enable_chord_keys = bool(self.enable_chord_keys_var.get()) if hasattr(self, 'enable_chord_keys_var') else False
                if hasattr(self, 'r_chord_drop_root_var'):
                    chord_drop_root = bool(self.r_chord_drop_root_var.get())
                else:
                    chord_drop_root = bool(self.chord_drop_root_var.get()) if hasattr(self, 'chord_drop_root_var') else False
                # 将中文显示映射为内部模式值
                if hasattr(self, 'r_chord_mode_var'):
                    chord_mode_display = str(self.r_chord_mode_var.get())
                else:
                    chord_mode_display = str(self.chord_mode_var.get()) if hasattr(self, 'chord_mode_var') else '七和弦优先'
                _mode_map = {
                    '七和弦优先': 'triad7',
                    '仅三和弦': 'triad',
                    '贪心匹配': 'greedy',
                    # 兼容旧配置（若直接存了英文值）
                    'triad7': 'triad7',
                    'triad': 'triad',
                    'greedy': 'greedy',
                }
                chord_mode = _mode_map.get(chord_mode_display, 'triad7')
                if hasattr(self, 'r_chord_min_sustain_var'):
                    chord_min_sustain_ms = int(self.r_chord_min_sustain_var.get())
                else:
                    chord_min_sustain_ms = int(self.chord_min_sustain_var.get()) if hasattr(self, 'chord_min_sustain_var') else 120
                self.auto_player.set_options(
                    allow_retrigger=allow_rt,
                    retrigger_min_gap_ms=gap_ms,
                    epsilon_ms=eps_ms,
                    send_ahead_ms=send_ahead_ms,
                    spin_threshold_ms=spin_threshold_ms,
                    post_action_sleep_ms=post_action_sleep_ms,
                    enable_chord_keys=enable_chord_keys,
                    chord_drop_root=chord_drop_root,
                    chord_mode=chord_mode,
                    chord_min_sustain_ms=chord_min_sustain_ms,
                    # 预处理选项
                    enable_quantize=bool(self.enable_quantize_var.get()) if hasattr(self, 'enable_quantize_var') else True,
                    quantize_grid_ms=int(self.quantize_grid_var.get()) if hasattr(self, 'quantize_grid_var') else 30,
                    enable_black_transpose=bool(self.enable_black_transpose_var.get()) if hasattr(self, 'enable_black_transpose_var') else True,
                    black_transpose_strategy=(
                        'down' if (getattr(self, 'black_transpose_strategy_var', None) and self.black_transpose_strategy_var.get() == '向下优先') else 'nearest'
                    ),
                )
                # 刷新按键输入表（若存在该组件/函数）
                try:
                    if hasattr(self, 'refresh_key_input_table') and callable(getattr(self, 'refresh_key_input_table')):
                        self.refresh_key_input_table()
                    elif hasattr(self, '_refresh_key_input_table') and callable(getattr(self, '_refresh_key_input_table')):
                        self._refresh_key_input_table()
                    elif hasattr(self, '_refresh_key_mapping') and callable(getattr(self, '_refresh_key_mapping')):
                        self._refresh_key_mapping()
                except Exception:
                    pass
        except Exception:
            pass
    
    def _auto_detect_mode(self):
        """自动检测演奏模式"""
        # 检查是否有乐谱文件
        score_path = self.score_path_var.get()
        if score_path and os.path.exists(score_path):
            # 有乐谱文件，切换到LRCp模式
            self.playback_mode.set("lrcp")
            self._log_message("检测到乐谱文件，自动切换到LRCp模式", "INFO")
            return "lrcp"
        
        # 检查是否有MIDI文件
        midi_path = self.midi_path_var.get()
        if midi_path and os.path.exists(midi_path):
            # 有MIDI文件，切换到MIDI模式
            self.playback_mode.set("midi")
            self._log_message("检测到MIDI文件，自动切换到MIDI模式", "INFO")
            return "midi"
        
        # 默认MIDI模式
        self.playback_mode.set("midi")
        return "midi"
    
    def _pause_midi_play(self):
        """暂停MIDI播放"""
        try:
            if hasattr(self, 'midi_player') and self.midi_player:
                self.midi_player.pause_midi()
                
                # 更新按钮状态
                self.pause_button.configure(text="恢复")
                self.ui_manager.set_status("MIDI播放已暂停")
                self._log_message("MIDI播放已暂停")
                
                # 无进度模拟逻辑
                
        except Exception as e:
            self._log_message(f"暂停MIDI播放失败: {str(e)}", "ERROR")
    
    def _resume_midi_play(self):
        """恢复MIDI播放"""
        try:
            if hasattr(self, 'midi_player') and self.midi_player:
                self.midi_player.resume_midi()
                
                # 更新按钮状态
                self.pause_button.configure(text="暂停")
                self.ui_manager.set_status("MIDI播放已恢复")
                self._log_message("MIDI播放已恢复")
                
                # 无进度模拟逻辑
                
        except Exception as e:
            self._log_message(f"恢复MIDI播放失败: {str(e)}", "ERROR")
    
    def _pause_auto_play(self):
        """暂停自动弹琴"""
        try:
            if hasattr(self, 'auto_player') and self.auto_player:
                self.auto_player.pause_auto_play()
                
                # 更新按钮状态
                self.pause_button.configure(text="恢复")
                self.ui_manager.set_status("自动弹琴已暂停")
                self._log_message("自动弹琴已暂停")
                
                
        except Exception as e:
            self._log_message(f"暂停自动弹琴失败: {str(e)}", "ERROR")
    
    def _resume_auto_play(self):
        """恢复自动弹琴"""
        try:
            if hasattr(self, 'auto_player') and self.auto_player:
                self.auto_player.resume_auto_play()
                
                # 更新按钮状态
                self.pause_button.configure(text="暂停")
                self.ui_manager.set_status("自动弹琴已恢复")
                self._log_message("自动弹琴已恢复")
                
                
        except Exception as e:
            self._log_message(f"恢复自动弹琴失败: {str(e)}", "ERROR")
    
    def _start_auto_play(self):
        """开始自动弹琴"""
        try:
            # 检查是否已经在演奏中
            if hasattr(self, 'auto_player') and self.auto_player and self.auto_player.is_playing:
                self._log_message("自动演奏已在进行中", "WARNING")
                return
            
            # 检查按钮状态
            if self.auto_play_button.cget("text") == "停止弹琴":
                self._log_message("自动演奏已在进行中", "WARNING")
                return
            
            # 自动检测演奏模式
            mode = self._auto_detect_mode()
            self._log_message(f"检测到演奏模式: {mode}", "INFO")
            
            # 根据模式执行不同的逻辑
            if mode == "lrcp":
                self._start_lrcp_play()
            else:
                self._start_midi_play()
            
        except Exception as e:
            self._log_message(f"启动自动弹琴失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"启动自动弹琴失败:\n{str(e)}")
    
    def _start_lrcp_play(self):
        """开始LRCp模式演奏"""
        try:
            # 检查是否有乐谱文件
            score_path = self.score_path_var.get()
            if not score_path:
                messagebox.showwarning("警告", "请先选择乐谱文件(.lrcp)")
                return
            
            if not os.path.exists(score_path):
                messagebox.showerror("错误", "乐谱文件不存在")
                return
            
            self._log_message(f"开始LRCp模式演奏: {os.path.basename(score_path)}")
            
            # LRCp 播放暂未实现，避免使用模拟模式
            self.ui_manager.set_status("LRCp 播放暂未实现")
            self._log_message("LRCp 播放暂未实现，待模块实现后接入", "WARNING")
            messagebox.showinfo("提示", "LRCp 播放暂未实现，当前版本不支持。")
            
        except Exception as e:
            self._log_message(f"LRCp模式演奏失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"LRCp模式演奏失败:\n{str(e)}")
    
    def _start_midi_play(self):
        """开始MIDI模式演奏"""
        try:
            # 首先检查是否有直接选择的MIDI文件
            midi_path = self.midi_path_var.get()
            if midi_path and os.path.exists(midi_path):
                # 使用直接选择的MIDI文件
                file_name = os.path.basename(midi_path)
                file_type = "MIDI文件"
                self._log_message(f"使用直接选择的MIDI文件: {file_name}", "INFO")
            else:
                # 检查播放列表
                if not self.playlist_tree.get_children():
                    messagebox.showwarning("警告", "播放列表为空，请先添加文件")
                    return
                
                # 获取当前选中的文件
                selected = self.playlist_tree.selection()
                if not selected:
                    # 如果没有选中文件，选择第一个
                    items = self.playlist_tree.get_children()
                    if items:
                        self.playlist_tree.selection_set(items[0])
                        selected = [items[0]]
                
                if not selected:
                    messagebox.showwarning("警告", "没有可播放的文件")
                    return
                
                # 获取文件信息
                item = self.playlist_tree.item(selected[0])
                file_name = item['values'][1] if item['values'] else "未知文件"
                file_type = item['values'][2] if item['values'] and len(item['values']) > 2 else "未知类型"
                
                # 获取完整文件路径
                if not hasattr(self, '_file_paths'):
                    self._file_paths = {}
                
                midi_path = self._file_paths.get(selected[0])
                if not midi_path:
                    midi_path = file_name
            
            # 尝试使用自动演奏功能
            try:
                # 检查是否已经在演奏中
                if hasattr(self, 'auto_player') and self.auto_player and self.auto_player.is_playing:
                    self._log_message("自动演奏已在进行中，请先停止当前演奏", "WARNING")
                    return
                
                # 首先尝试从模块管理器获取实例
                if hasattr(self, 'module_manager') and self.module_manager:
                    playback_module = self.module_manager.get_module_instance('playback')
                    if playback_module and 'AutoPlayer' in playback_module:
                        self.auto_player = playback_module['AutoPlayer']
                        self._log_message("从模块管理器获取AutoPlayer实例", "INFO")
                    else:
                        # 如果模块管理器没有实例，尝试直接导入
                        from meowauto.playback import AutoPlayer
                        from meowauto.core import Logger
                        logger = Logger()
                        self.auto_player = AutoPlayer(logger)
                        self._log_message("直接导入AutoPlayer模块", "INFO")
                else:
                    # 模块管理器不可用，直接导入
                    from meowauto.playback import AutoPlayer
                    from meowauto.core import Logger
                    logger = Logger()
                    self.auto_player = AutoPlayer(logger)
                    self._log_message("直接导入AutoPlayer模块", "INFO")
                
                # 应用 UI 调试模式到 AutoPlayer
                try:
                    if hasattr(self, 'debug_var') and hasattr(self.auto_player, 'set_debug'):
                        self.auto_player.set_debug(bool(self.debug_var.get()))
                except Exception:
                    pass
                
                # 设置回调
                self.auto_player.set_callbacks(
                    on_start=lambda: self._log_message("自动演奏已开始", "SUCCESS"),
                    on_pause=lambda: self._log_message("自动演奏已暂停", "INFO"),
                    on_resume=lambda: self._log_message("自动演奏已恢复", "INFO"),
                    on_stop=lambda: self._log_message("自动演奏已停止"),
                    on_progress=lambda p: self._on_progress_update(p),
                    on_complete=lambda: self._on_playback_complete(),
                    on_error=lambda msg: self._log_message(f"自动演奏错误: {msg}", "ERROR")
                )
                
                # 根据文件类型选择演奏模式
                if file_type == "MIDI文件":
                    # 使用21键系统的默认键盘映射（仅 L/M/H 1-7）
                    default_key_mapping = {
                        'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
                        'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
                        'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7'
                    }
                    # 若存在与当前文件匹配的已解析音符，则直接使用它们进行回放，绕过后处理
                    use_analyzed = False
                    try:
                        if getattr(self, 'analysis_notes', None) and getattr(self, 'analysis_file', ''):
                            if os.path.abspath(self.analysis_file) == os.path.abspath(midi_path):
                                use_analyzed = True
                    except Exception:
                        use_analyzed = False

                    if use_analyzed:
                        # 使用解析结果：仍需应用一次和弦/调度相关设置
                        self._apply_player_options()
                        success = self.auto_player.start_auto_play_midi_events(self.analysis_notes, tempo=self.tempo_var.get(), key_mapping=default_key_mapping)
                    else:
                        # 在使用内部解析前，应用一次左侧回放设置
                        self._apply_player_options()
                        # 回退到内部解析
                        success = self.auto_player.start_auto_play_midi(midi_path, tempo=self.tempo_var.get(), key_mapping=default_key_mapping)
                else:
                    # 其他文件类型，使用模拟模式
                    success = True
                
                if success:
                    # 更新按钮状态
                    self.auto_play_button.configure(text="停止弹琴")
                    self.pause_button.configure(text="暂停", state="normal")
                    self.ui_manager.set_status(f"自动弹琴已开始: {file_name}")
                    self._log_message(f"开始自动弹琴: {file_name} ({file_type})", "SUCCESS")
                    
                    # 更新播放列表状态（如果是从播放列表播放的）
                    if not midi_path == self.midi_path_var.get():
                        selected = self.playlist_tree.selection()
                        if selected:
                            self.playlist_tree.set(selected[0], "状态", "正在播放")
                    
                    # 进度由真实回调驱动
                else:
                    self._log_message("自动演奏启动失败", "ERROR")
                    
            except ImportError as e:
                # 如果自动演奏模块不可用，使用模拟模式
                self._log_message(f"自动演奏模块不可用，使用模拟模式: {e}", "WARNING")
                
                # 更新按钮状态
                self.auto_play_button.configure(text="停止弹琴")
                self.pause_button.configure(text="暂停", state="normal")
                self.ui_manager.set_status(f"自动弹琴已开始: {file_name}")
                self._log_message(f"开始自动弹琴: {file_name} ({file_type})", "SUCCESS")
                
                # 更新播放列表状态（如果是从播放列表播放的）
                if not midi_path == self.midi_path_var.get():
                    selected = self.playlist_tree.selection()
                    if selected:
                        self.playlist_tree.set(selected[0], "状态", "正在播放")
                
                # 进度由真实回调驱动
            
        except Exception as e:
            self._log_message(f"MIDI模式演奏失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"MIDI模式演奏失败:\n{str(e)}")
    
    
    
    def _stop_auto_play(self):
        """停止自动弹琴"""
        try:
            # 停止实际的自动演奏
            if hasattr(self, 'auto_player') and self.auto_player:
                try:
                    self.auto_player.stop_auto_play()
                except Exception as e:
                    self._log_message(f"停止自动演奏器失败: {str(e)}", "WARNING")
            
            # 更新按钮状态
            self.auto_play_button.configure(text="自动弹琴")
            self.pause_button.configure(text="暂停", state="disabled")
            self.ui_manager.set_status("自动弹琴已停止")
            self._log_message("自动弹琴已停止")
            
            # 无进度模拟逻辑
            
            # 更新播放列表状态
            selected = self.playlist_tree.selection()
            if selected:
                self.playlist_tree.set(selected[0], "状态", "已停止")
            
        except Exception as e:
            self._log_message(f"停止自动弹琴失败: {str(e)}", "ERROR")
    
    

    def _on_progress_update(self, progress: float, current_str: str | None = None, total_str: str | None = None):
        """统一的进度更新回调（线程安全）"""
        try:
            p = max(0.0, min(100.0, float(progress)))
            # 生成时间文本；若缺失，沿用现有
            if current_str and total_str:
                time_text = f"{current_str} / {total_str}"
            else:
                time_text = getattr(self, 'bottom_time_var', tk.StringVar(value="00:00 / 00:00")).get()
            def _apply():
                # 通过统一方法同步到底部与原进度条
                if hasattr(self, '_sync_progress'):
                    self._sync_progress(p, time_text)
                else:
                    # 兜底：直接更新原控件
                    if hasattr(self, 'progress_var'):
                        self.progress_var.set(p)
                    if hasattr(self, 'time_var') and (current_str and total_str):
                        self.time_var.set(time_text)
            # 确保在主线程更新
            if hasattr(self, 'root'):
                self.root.after(0, _apply)
            else:
                _apply()
        except Exception:
            pass
    
    def _on_playback_complete(self):
        """播放完成处理"""
        self._log_message("播放完成", "SUCCESS")
        self.ui_manager.set_status("播放完成")
        
        # 自动播放下一首
        self._play_next()
    
    def _play_next(self):
        """根据播放顺序设置播放下一首"""
        try:
            all_items = self.playlist_tree.get_children()
            if not all_items:
                self._stop_auto_play()
                return
            order = getattr(self, 'playlist_order_var', tk.StringVar(value="顺序")).get()
            current_selected = self.playlist_tree.selection()
            # 单曲循环：保持当前选中并重播
            if order == "单曲循环" and current_selected:
                self._start_auto_play()
                return
            # 随机播放：随机选择一个（可避免与当前相同）
            if order == "随机":
                import random
                if current_selected and len(all_items) > 1:
                    candidates = [i for i in all_items if i != current_selected[0]]
                    next_item = random.choice(candidates)
                else:
                    next_item = random.choice(all_items)
                self.playlist_tree.selection_set(next_item)
                self._start_auto_play()
                return
            # 顺序播放（默认）
            if current_selected:
                current_index = list(all_items).index(current_selected[0])
                next_index = (current_index + 1) % len(all_items)
                self.playlist_tree.selection_set(all_items[next_index])
                self._start_auto_play()
            else:
                # 无选中则从第一首开始
                self.playlist_tree.selection_set(all_items[0])
                self._start_auto_play()
        except Exception as e:
            self._log_message(f"播放下一首失败: {str(e)}", "ERROR")
            self._stop_auto_play()

    def _export_event_csv(self):
        """导出事件表为CSV文件"""
        try:
            if not hasattr(self, 'event_tree') or not self.event_tree.get_children():
                messagebox.showwarning("提示", "事件表为空，无法导出")
                return
            filename = filedialog.asksaveasfilename(
                title="导出事件CSV",
                defaultextension=".csv",
                filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
            )
            if not filename:
                return
            import csv
            # 使用与定义时一致的列
            columns = ("序号", "开始(s)", "类型", "音符", "通道", "组", "结束(s)", "时长(s)", "和弦")
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for item in self.event_tree.get_children():
                    writer.writerow(self.event_tree.item(item)['values'])
            self._log_message(f"事件CSV已导出: {filename}", "SUCCESS")
            messagebox.showinfo("成功", f"事件CSV已导出到:\n{filename}")
        except Exception as e:
            self._log_message(f"导出事件CSV失败: {e}", "ERROR")

    def _export_key_notation(self):
        """导出按键谱：仅导出 note_on 事件，以键位映射（非音名），并按时间间隔加入空格。
        键位映射：
          低音区 L1-L7 -> a s d f g h j
          中音区 M1-M7 -> q w e r t y u
          高音区 H1-H7 -> 1 2 3 4 5 6 7
          和弦区 C, Dm, Em, F, G, Am, G7 -> z x c v b n m
        """
        try:
            if not hasattr(self, 'event_tree') or not self.event_tree.get_children():
                messagebox.showwarning("提示", "事件表为空，无法导出按键谱")
                return
            filename = filedialog.asksaveasfilename(
                title="导出按键谱",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if not filename:
                return
            # 从事件表收集 note_on 事件
            rows = []  # (start_time, midi_note)
            # 记录每个时间点的和弦名（若存在且在映射表中）
            from collections import defaultdict
            chords_by_time = defaultdict(set)
            for item in self.event_tree.get_children():
                vals = self.event_tree.item(item)['values']
                if not vals:
                    continue
                try:
                    seq, start_s, typ, note, ch, grp, end_s, dur, chord = vals
                except Exception:
                    # 容错列
                    if len(vals) >= 3 and vals[2] == 'note_on':
                        start_s = float(vals[1])
                        note = int(vals[3])
                        rows.append((start_s, note))
                        # 和弦列可能不存在
                        if len(vals) >= 9:
                            chord = vals[8]
                            if isinstance(chord, str):
                                chords_by_time[round(start_s, 6)].add(chord)
                        continue
                if str(typ) == 'note_on':
                    rows.append((float(start_s), int(note)))
                    if isinstance(chord, str):
                        chords_by_time[round(float(start_s), 6)].add(chord)
            # 按开始时间排序并按同一时间分组（和弦）
            bucket = defaultdict(list)
            for st, n in rows:
                bucket[round(st, 6)].append(n)
            times = sorted(bucket.keys())
            # 度数映射（C大调，黑键就近到白键），返回 (区间 L/M/H, 度数 '1'..'7')
            def midi_to_reg_deg(n: int) -> tuple[str, str]:
                pc = n % 12
                white_map = {0: '1', 2: '2', 4: '3', 5: '4', 7: '5', 9: '6', 11: '7'}
                if pc not in white_map:
                    # 就近到白键
                    for d in (1, -1, 2, -2):
                        cand = (pc + d) % 12
                        if cand in white_map:
                            pc = cand
                            break
                deg = white_map.get(pc, '1')
                # 分组：<C4 为 L，C4..B4 为 M，>=C5 为 H（边界外延伸容错）
                if n < 60:
                    reg = 'L'
                elif n <= 71:
                    reg = 'M'
                else:
                    reg = 'H'
                return reg, deg
            # 键位映射
            LOW = {'1':'a','2':'s','3':'d','4':'f','5':'g','6':'h','7':'j'}
            MID = {'1':'q','2':'w','3':'e','4':'r','5':'t','6':'y','7':'u'}
            HIGH = {'1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7'}
            CHORD_KEYS_ORDER = ['C', 'Dm', 'Em', 'F', 'G', 'Am', 'G7']
            CHORD_MAP = {'C':'z','Dm':'x','Em':'c','F':'v','G':'b','Am':'n','G7':'m'}
            def to_key(reg: str, deg: str) -> str:
                if reg == 'L':
                    return LOW.get(deg, 'a')
                if reg == 'M':
                    return MID.get(deg, 'q')
                return HIGH.get(deg, '1')
            # 使用 BPM 推算空格粒度：1 空格 = 八分音符
            try:
                bpm = int(getattr(self, 'bpm_var', tk.IntVar(value=100)).get())
                beat = 60.0 / max(1, bpm)
                unit = beat / 2.0
            except Exception:
                unit = 0.3
            # 生成文本：同一时间点内，将和弦键（若有）放在最前，然后是音符键；多键同刻用方括号聚合
            parts = []
            last_t = None
            for t in times:
                if last_t is not None:
                    delta = max(0.0, t - last_t)
                    spaces = int(round(delta / unit))
                    parts.append(' ' * max(1, spaces))
                # 构建本刻需要按下的键位
                keys = []
                # 和弦键（若存在且在映射表中）
                present_chords = [c for c in CHORD_KEYS_ORDER if c in chords_by_time.get(t, set())]
                for cname in present_chords:
                    keys.append(CHORD_MAP[cname])
                # 音符键
                chord_notes = sorted(bucket[t])
                for n in chord_notes:
                    reg, deg = midi_to_reg_deg(n)
                    keys.append(to_key(reg, deg))
                token = ''.join(keys)
                if len(keys) > 1:
                    parts.append(f"[{token}]")
                else:
                    parts.append(token)
                last_t = t
            content = ''.join(parts)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            self._log_message(f"按键谱已导出: {filename}", "SUCCESS")
            messagebox.showinfo("成功", f"按键谱已导出到:\n{filename}")
        except Exception as e:
            self._log_message(f"导出按键谱失败: {e}", "ERROR")
    
    def _play_midi(self):
        """播放MIDI"""
        midi_path = self.midi_path_var.get()
        if not midi_path:
            messagebox.showerror("错误", "请先选择MIDI文件")
            return
        
        if not os.path.exists(midi_path):
            messagebox.showerror("错误", "MIDI文件不存在")
            return
        
        self.ui_manager.set_status("正在播放MIDI...")
        self._log_message("开始播放MIDI文件")
        
        try:
            # 尝试使用meowauto模块中的MIDI播放功能
            from meowauto.playback import MidiPlayer
            from meowauto.core import Logger
            
            # 创建播放器实例并保存为实例属性
            logger = Logger()
            self.midi_player = MidiPlayer(logger)  # 保存为实例属性
            
            # 设置播放参数
            tempo = self.tempo_var.get()
            volume = self.volume_var.get()
            
            # 设置播放参数
            self.midi_player.set_tempo(tempo)
            self.midi_player.set_volume(volume)
            
            # 设置播放回调
            self.midi_player.set_callbacks(
                on_start=lambda: self._log_message("MIDI播放已开始", "SUCCESS"),
                on_pause=lambda: self._log_message("MIDI播放已暂停", "INFO"),
                on_resume=lambda: self._log_message("MIDI播放已恢复", "INFO"),
                on_stop=lambda: self._log_message("MIDI播放已停止"),
                on_progress=lambda p: self._on_progress_update(p),
                on_complete=lambda: self._on_playback_complete(),
                on_error=lambda msg: self._log_message(f"MIDI播放错误: {msg}", "ERROR")
            )
            
            # 开始播放
            success = self.midi_player.play_midi(midi_path, progress_callback=self._on_progress_update)
            
            if success:
                self._log_message("MIDI播放成功", "SUCCESS")
                self.ui_manager.set_status("MIDI播放中...")
                
                # 启用暂停按钮
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="暂停", state="normal")
                
                # 进度由真实回调驱动
            else:
                self._log_message("MIDI播放失败", "ERROR")
                self.ui_manager.set_status("MIDI播放失败")
                messagebox.showerror("错误", "MIDI播放失败，请检查文件格式")
                
        except ImportError:
            self._log_message("MIDI播放模块不可用", "ERROR")
            messagebox.showerror("错误", "MIDI播放模块不可用，请检查meowauto模块")
        except Exception as e:
            self._log_message(f"MIDI播放异常: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"MIDI播放过程中发生错误:\n{str(e)}")
    
    def _stop_playback(self):
        """停止播放"""
        try:
            # 停止MIDI播放
            if hasattr(self, 'midi_player') and self.midi_player:
                try:
                    self.midi_player.stop_midi()
                    self._log_message("MIDI播放已停止")
                except Exception as e:
                    self._log_message(f"停止MIDI播放失败: {str(e)}", "WARNING")
            
            # 停止自动演奏
            if hasattr(self, 'auto_player') and self.auto_player:
                try:
                    self.auto_player.stop_auto_play()
                    self._log_message("自动演奏已停止")
                except Exception as e:
                    self._log_message(f"停止自动演奏失败: {str(e)}", "WARNING")
            
            # 无进度模拟逻辑
            
            # 重置进度
            self.progress_var.set(0)
            self.time_var.set("00:00 / 00:00")
            
            # 禁用暂停按钮
            if hasattr(self, 'pause_button'):
                self.pause_button.configure(text="暂停", state="disabled")
            
            self.ui_manager.set_status("播放已停止")
            self._log_message("播放已停止")
            
            # 更新播放列表状态
            selected = self.playlist_tree.selection()
            if selected:
                self.playlist_tree.set(selected[0], "状态", "已停止")
            
        except Exception as e:
            self._log_message(f"停止播放失败: {str(e)}", "ERROR")
    
    def _add_file_to_playlist(self, file_path, file_type):
        """添加文件到播放列表"""
        try:
            # 添加到播放列表
            item_count = len(self.playlist_tree.get_children()) + 1
            file_name = os.path.basename(file_path)
            
            # 计算文件时长（这里简化处理）
            duration = "未知"
            if os.path.exists(file_path):
                try:
                    # 尝试获取文件时长
                    if file_path.lower().endswith('.mid') or file_path.lower().endswith('.midi'):
                        import mido
                        mid = mido.MidiFile(file_path)
                        duration_seconds = mid.length
                        duration = f"{int(duration_seconds//60):02d}:{int(duration_seconds%60):02d}"
                    else:
                        duration = "未知"
                except:
                    duration = "未知"
            
            # 插入项目并存储完整路径
            item_id = self.playlist_tree.insert("", "end", values=(item_count, file_name, file_type, duration, "未播放"))
            # 将完整路径存储到字典中
            if not hasattr(self, '_file_paths'):
                self._file_paths = {}
            self._file_paths[item_id] = file_path
            self._log_message(f"已添加到播放列表: {file_name}")
            
        except Exception as e:
            self._log_message(f"添加文件到播放列表失败: {str(e)}", "ERROR")
    
    def _add_to_playlist(self):
        """添加文件到播放列表"""
        file_path = filedialog.askopenfilename(
            title="选择文件",
            filetypes=[
                ("乐谱文件", "*.lrcp"),
                ("MIDI文件", "*.mid;*.midi"),
                ("音频文件", "*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 确定文件类型
            if file_ext == '.lrcp':
                file_type = "LRCp乐谱"
            elif file_ext in ['.mid', '.midi']:
                file_type = "MIDI文件"
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                file_type = "音频文件"
            else:
                file_type = "未知类型"
            
            self._add_file_to_playlist(file_path, file_type)
    
    def _remove_from_playlist(self):
        """从播放列表移除文件"""
        selected = self.playlist_tree.selection()
        if selected:
            for item in selected:
                item_data = self.playlist_tree.item(item)
                file_name = item_data['values'][1] if item_data['values'] else "未知文件"
                self.playlist_tree.delete(item)
                self._log_message(f"已从播放列表移除: {file_name}")
            
            # 重新编号
            items = self.playlist_tree.get_children()
            for i, item in enumerate(items, 1):
                values = list(self.playlist_tree.item(item)['values'])
                values[0] = i
                self.playlist_tree.item(item, values=values)
        else:
            messagebox.showwarning("提示", "请先选择要移除的项目")
    
    def _clear_playlist(self):
        """清空播放列表"""
        if messagebox.askyesno("确认", "确定要清空播放列表吗？"):
            self.playlist_tree.delete(*self.playlist_tree.get_children())
            self._log_message("播放列表已清空")
    
    def _save_playlist(self):
        """保存播放列表"""
        if not self.playlist_tree.get_children():
            messagebox.showwarning("提示", "播放列表为空，无法保存")
            return
        
        filename = filedialog.asksaveasfilename(
            title="保存播放列表",
            defaultextension=".m3u8",
            filetypes=[("播放列表", "*.m3u8"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for item in self.playlist_tree.get_children():
                        values = self.playlist_tree.item(item)['values']
                        if values and len(values) > 1:
                            f.write(f"#EXTINF:-1,{values[1]}\n")
                            # 这里应该保存实际的文件路径
                            f.write(f"# {values[1]}\n")
                
                self._log_message(f"播放列表已保存到: {filename}")
                messagebox.showinfo("成功", f"播放列表已保存到:\n{filename}")
            except Exception as e:
                self._log_message(f"保存播放列表失败: {str(e)}", "ERROR")
    
    def _on_playlist_double_click(self, event):
        """播放列表双击事件"""
        selected = self.playlist_tree.selection()
        if selected:
            item_id = selected[0]
            item = self.playlist_tree.item(item_id)
            filename = item['values'][1] if item['values'] else "未知文件"
            ftype = item['values'][2] if item['values'] and len(item['values']) > 2 else "未知类型"
            # 获取完整路径
            full_path = None
            try:
                if hasattr(self, '_file_paths'):
                    full_path = self._file_paths.get(item_id)
            except Exception:
                full_path = None
            if not full_path:
                full_path = filename
            # 切换模式并设置路径
            if ftype == "MIDI文件" and full_path:
                self.playback_mode.set("midi")
                self.midi_path_var.set(full_path)
                self.ui_manager.set_status(f"双击播放: {filename}")
                self._log_message(f"双击播放: {filename}")
                # 先解析再开始自动弹琴
                try:
                    self._analyze_current_midi()
                except Exception as e:
                    self._log_message(f"双击解析失败: {e}", "ERROR")
                self._start_auto_play()
            elif ftype == "LRCp乐谱" and full_path:
                self.playback_mode.set("lrcp")
                self.score_path_var.set(full_path)
                self.ui_manager.set_status(f"双击播放: {filename}")
                self._log_message(f"双击播放: {filename}")
                self._start_auto_play()
            else:
                self.ui_manager.set_status(f"不支持的文件类型: {filename}")
                self._log_message(f"不支持的文件类型: {filename}", "WARNING")
    
    def _clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", tk.END)
        self._log_message("日志已清空")
    
    def _save_log(self):
        """保存日志"""
        try:
            filename = filedialog.asksaveasfilename(
                title="保存日志",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get("1.0", tk.END))
                self._log_message(f"日志已保存到: {filename}")
                messagebox.showinfo("成功", f"日志已保存到:\n{filename}")
        except Exception as e:
            self._log_message(f"保存日志失败: {str(e)}", "ERROR")
    
    def _log_message(self, message: str, level: str = "INFO"):
        """记录日志消息"""
        try:
            if hasattr(self, 'log_text'):
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {message}\n"
                
                # 根据级别添加颜色标记
                if level == "ERROR":
                    formatted_message = f"[{timestamp}] ❌ {message}\n"
                elif level == "WARNING":
                    formatted_message = f"[{timestamp}] ⚠️ {message}\n"
                elif level == "SUCCESS":
                    formatted_message = f"[{timestamp}] ✅ {message}\n"
                else:
                    formatted_message = f"[{timestamp}] ℹ️ {message}\n"
                
                self.log_text.insert(tk.END, formatted_message)
                self.log_text.see(tk.END)  # 滚动到最新内容
                
                # 限制日志行数，避免内存占用过大
                lines = self.log_text.get("1.0", tk.END).split('\n')
                if len(lines) > 1000:
                    self.log_text.delete("1.0", "500.0")
        except Exception as e:
            print(f"日志记录失败: {e}")
    
    def _add_test_playlist_data(self):
        """添加测试数据到播放列表"""
        try:
            if hasattr(self, 'playlist_tree'):
                # 添加一些测试项目
                test_items = [
                    ("1", "测试MIDI文件.mid", "MIDI文件", "02:30", "未播放"),
                    ("2", "示例音频.mp3", "音频文件", "03:45", "未播放"),
                    ("3", "乐谱文件.lrcp", "LRCp乐谱", "02:15", "未播放")
                ]
                
                for item in test_items:
                    self.playlist_tree.insert('', 'end', values=item)
                
                self._log_message("已添加测试数据到播放列表", "INFO")
        except Exception as e:
            self._log_message(f"添加测试数据失败: {e}", "ERROR")
    
    def _on_closing(self):
        """应用程序关闭事件"""
        try:
            # 发布系统关闭事件
            self.event_bus.publish(Events.SYSTEM_SHUTDOWN, {}, 'App')
            
            # 销毁窗口
            self.root.destroy()
            
        except Exception as e:
            print(f"关闭应用程序时发生错误: {e}")
            self.root.destroy()
    
    def run(self):
        """运行应用程序"""
        try:
            self.ui_manager.set_status("应用程序启动完成")
            self._log_message("应用程序启动完成", "SUCCESS")
            self.root.mainloop()
        except Exception as e:
            error_msg = f"应用程序运行失败: {e}"
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': error_msg}, 'App')
            print(error_msg) 