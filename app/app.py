#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField AutoPiano 主应用程序类
作为模块协调器和应用程序入口点
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
# 现代化主题：优先使用 ttkbootstrap
try:
    import ttkbootstrap as ttkb  # type: ignore
except Exception:
    ttkb = None
import os
import time
import sys
import tempfile
import uuid
from typing import Dict, Any, Optional

# 导入自定义模块
from event_bus import event_bus, Events
from module_manager import ModuleManager
from ui_manager import UIManager
from meowauto.midi import analyzer, groups
from meowauto.midi.partitioner import CombinedInstrumentPartitioner, TrackChannelPartitioner
from meowauto.ui.sidebar import Sidebar
from router import Router
from pages.solo import SoloPage
from pages.ensemble import EnsemblePage
# 瘦身：组件化UI构建
from pages.components import file_select as comp_file_select
from pages.components import playback_controls as comp_playback
from pages.components import right_pane as comp_right
from pages.components import bottom_progress as comp_bottom
# 新增：乐器板块页面 与 工具页面
try:
    from pages.instruments.epiano import EPianoPage  # type: ignore
    from pages.instruments.guitar import GuitarPage  # type: ignore
    from pages.instruments.bass import BassPage  # type: ignore
    from pages.instruments.drums import DrumsPage  # type: ignore
except Exception:
    EPianoPage = GuitarPage = BassPage = DrumsPage = None  # type: ignore
try:
    from pages.tools.audio2midi import Audio2MidiPage  # type: ignore
except Exception:
    Audio2MidiPage = None  # type: ignore
from meowauto.playback.playlist_manager import PlaylistManager
from meowauto.core import Logger
from meowauto.utils.exporters.key_notation import build_key_notation
from meowauto.utils.exporters.event_csv import export_event_csv
from meowauto.app.services.playback_service import PlaybackService
from meowauto.app.controllers.playback_controller import PlaybackController
try:
    from meowauto.app.controllers.drums_controller import DrumsController  # type: ignore
except Exception:
    DrumsController = None  # type: ignore


class MeowFieldAutoPiano:
    """MeowField AutoPiano 主应用程序"""
    
    def __init__(self):
        """初始化应用程序"""
        # 创建主窗口（ttkbootstrap 优先）
        if 'ttkb' in globals() and ttkb is not None:
            try:
                self.root = ttkb.Window(themename="pink")  # 现代扁平主题
                self._using_ttkbootstrap = True
            except Exception:
                self.root = tk.Tk()
                self._using_ttkbootstrap = False
        else:
            self.root = tk.Tk()
            self._using_ttkbootstrap = False
        # 主窗口标题（固定为中文）
        self.root.title("MeowField自动演奏程序")
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
        self.current_game = "开放空间"
        self.current_mode = "solo"  # 保留：兼容旧逻辑的全局模式（默认独奏）
        # 新增：按乐器独立模式（后续若提供合奏，仅修改对应乐器项）
        self.instrument_mode = {
            '电子琴': 'solo',
            '吉他': 'solo',
            '贝斯': 'solo',
            '架子鼓': 'solo',
        }
        # 新增：当前乐器板块，默认电子琴
        self.current_instrument = "电子琴"
        # 移除游戏页面：不再区分游戏
        self.yuanshen_page = None  # 保留字段以避免外部引用报错
        self.sky_page = None
        self.sidebar_win = None
        # 播放服务（提前初始化，以便页面注册时可用）
        try:
            self.playback_service = PlaybackService()
        except Exception:
            self.playback_service = None

        # 初始化 Router（暂不切换到新页面，后续逐步迁移）
        try:
            self.router = Router(
                getattr(self.ui_manager, 'left_content_frame', self.ui_manager.left_frame),
                self.ui_manager.right_frame,
                set_title=self.ui_manager.set_title_suffix,
            )
            # 可预注册页面（不立即显示）
            try:
                self.router.register('solo', SoloPage(controller=self))
                self.router.register('ensemble', EnsemblePage(controller=self))
                # 注册乐器板块页面（容错）
                try:
                    if EPianoPage:
                        self.router.register('inst:epiano', EPianoPage(controller=self))
                except Exception:
                    pass
                try:
                    if GuitarPage:
                        self.router.register('inst:guitar', GuitarPage(controller=self))
                except Exception:
                    pass
                try:
                    if BassPage:
                        self.router.register('inst:bass', BassPage(controller=self))
                except Exception:
                    pass
                try:
                    if DrumsPage:
                        # 传入真实的 DrumsController，并把 app 引用传给页面以复用文件选择/播放列表
                        ctrl = DrumsController(self.playback_service) if DrumsController else self
                        self.router.register('inst:drums', DrumsPage(controller=ctrl, app_ref=self))
                except Exception:
                    pass
                # 注册工具页面
                try:
                    if Audio2MidiPage:
                        self.router.register('tool:audio2midi', Audio2MidiPage(controller=self))
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            self.router = None
        
        # 注册事件监听器
        self._register_event_listeners()
        
        # 加载模块
        self._load_modules()
        
        # 创建UI组件（迁移至页面内构建，不在此全局创建）
        # self._create_ui_components()
        # 创建并对接侧边栏（嵌入左侧容器，默认展开）
        self._create_sidebar_window()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        # 绑定销毁事件（调试 mainloop 退出问题）
        try:
            self.root.bind('<Destroy>', self._on_root_destroy, add="+")
        except TypeError:
            self.root.bind('<Destroy>', self._on_root_destroy)
        
        # 绑定热键
        self._bind_hotkeys()
        
        # 默认显示电子琴板块
        try:
            self.current_instrument = '电子琴'
            if getattr(self, 'router', None):
                self.router.show('inst:epiano', title=f"{self.current_instrument}")
        except Exception:
            pass
        # 发布系统就绪事件
        self.event_bus.publish(Events.SYSTEM_READY, {'version': '1.0.6'}, 'App')
        # 初始化标题后缀
        try:
            self._update_titles_suffix(self.current_instrument)
        except Exception:
            pass
        # 启动期关闭保护：避免初始化阶段误触发关闭
        self._startup_protect = True
        # 仅调试期：默认不允许关闭，需显式授权（Ctrl+Q 或确认对话框）
        self._allow_close = False
        try:
            self.root.after(1000, lambda: setattr(self, '_startup_protect', False))
        except Exception:
            self._startup_protect = False
        # 绑定 Ctrl+Q 作为“明确退出”
        try:
            self.root.bind('<Control-q>', lambda e: self._request_close())
        except Exception:
            pass
        # 播放列表管理器
        try:
            self.logger = Logger()
        except Exception:
            self.logger = None  # 容错
        try:
            self.playlist = PlaylistManager(self.logger if self.logger else Logger())
        except Exception:
            self.playlist = None
        # 播放服务（已在前文初始化；此处仅兜底）
        try:
            if not getattr(self, 'playback_service', None):
                self.playback_service = PlaybackService()
        except Exception:
            if not getattr(self, 'playback_service', None):
                self.playback_service = None
        # 控制器占位：协调 UI 与播放服务
        try:
            self.playback_controller = PlaybackController(self, self.playback_service)
        except Exception:
            self.playback_controller = None
        # 分部缓存：保存最近一次分离结果，供导出与预听使用
        self._last_split_parts = {}
        # 分部选择：记录用户在弹窗中勾选的分部名称集合
        self._selected_part_names = set()
    
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
                        # 全局空格：暂停/恢复（不抑制系统事件）
                        keyboard.add_hotkey('space', lambda: self.root.after(0, lambda: self._on_space_key(None)), suppress=False)
                        # 全局 ESC：停止
                        keyboard.add_hotkey('esc', lambda: self.root.after(0, lambda: self._on_escape_key(None)), suppress=False)
                    except Exception:
                        pass
                t = threading.Thread(target=_register_kb, daemon=True)
                t.start()
                self._log_message("全局热键已注册: 空格(暂停/恢复), ESC(停止), Ctrl+Shift+C(停止播放)")
            except Exception:
                # 回退到窗口级绑定
                self.root.bind('<Control-Shift-C>', lambda e: (self._stop_auto_play(), self._stop_playback()))
                self._log_message("窗口热键已注册: 空格, ESC, Ctrl+S, Ctrl+Shift+C")
            
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
        """（已迁移）保留占位，避免外部调用报错"""
        return
    
    def _create_sidebar_window(self):
        """禁用侧边栏创建，功能已移至标题栏"""
        try:
            # 设置标题栏按钮的回调函数
            if hasattr(self.ui_manager, 'set_title_action_callback'):
                self.ui_manager.set_title_action_callback(self._on_sidebar_action)
            
            # 移除侧边栏占位空间
            shell = getattr(self.ui_manager, 'left_shell', None)
            if shell is not None:
                try:
                    # 设置左侧栏宽度为0，隐藏侧边栏区域
                    shell.grid_columnconfigure(0, minsize=0, weight=0)
                    # 增加内容区域权重
                    shell.grid_columnconfigure(1, weight=1)
                except Exception:
                    pass
            
            # 隐藏侧边栏容器
            holder = getattr(self.ui_manager, 'left_sidebar_holder', None)
            if holder is not None:
                try:
                    holder.pack_forget()
                    holder.grid_forget()
                except Exception:
                    pass
            
            self._log_message("侧边栏已禁用，功能已移至标题栏", "INFO")
        except Exception as e:
            self._log_message(f"禁用侧边栏失败: {e}", "ERROR")

    def _on_sidebar_configure(self, event=None):
        """不再响应内部内容尺寸变化，避免反馈循环导致闪烁。"""
        return

    def _on_root_configure(self, event=None):
        """主窗体变化时，这里无需处理悬浮几何。保留占位。"""
        return

    def _on_root_unmap(self, event=None):
        return

    def _on_root_map(self, event=None):
        return

    def _on_root_deactivate(self, event=None):
        return

    def _on_root_activate(self, event=None):
        return

    def _position_sidebar(self):
        """嵌入式时不需要定位悬浮窗。"""
        return

    def _update_sidebar_width(self, w: int):
        """侧边栏动画过程中实时回调，更新嵌入容器宽度。"""
        try:
            if not getattr(self, 'sidebar_shrink_holder', False):
                return
            shell = getattr(self.ui_manager, 'left_shell', None)
            if shell is None:
                return
            w = int(w)
            if hasattr(self, 'sidebar_width_collapsed') and hasattr(self, 'sidebar_width_expanded'):
                w = max(self.sidebar_width_collapsed, min(self.sidebar_width_expanded, w))
            # 去抖：无变化则不重绘
            if getattr(self, '_sidebar_last_w', None) == w:
                return
            self._sidebar_last_w = w
            self.sidebar_current_width = w
            # 通过 grid 列的 minsize 实现侧边栏宽度动画
        except Exception:
            pass


    def _on_sidebar_action(self, key: str):
        """侧边栏按钮回调"""
        try:
            if key == 'mode-ensemble':
                self.current_mode = 'ensemble'
                try:
                    if getattr(self, 'router', None):
                        cur = self.router.current() if hasattr(self.router, 'current') else None
                        if isinstance(cur, str) and cur.startswith('inst:'):
                            title = f"{getattr(self, 'current_instrument', '电子琴')}"
                            self.router.show(cur, title=title)
                        else:
                            self.router.show('ensemble', title="合奏")
                    self.ui_manager.set_status('已切换为合奏页面')
                except Exception:
                    pass
                return
            if key == 'inst-epiano':
                try:
                    self.current_instrument = '电子琴'
                    title = f"{self.current_instrument}"
                    if getattr(self, 'router', None):
                        self.router.show('inst:epiano', title=title)
                    self.ui_manager.set_status('已切换至电子琴板块')
                except Exception:
                    pass
                return
            if key == 'inst-guitar':
                try:
                    self.current_instrument = '吉他'
                    title = f"{self.current_instrument}"
                    if getattr(self, 'router', None):
                        self.router.show('inst:guitar', title=title)
                    self.ui_manager.set_status('已切换至吉他板块')
                except Exception:
                    pass
                return
            if key == 'inst-bass':
                try:
                    self.current_instrument = '贝斯'
                    title = f"{self.current_instrument}"
                    if getattr(self, 'router', None):
                        self.router.show('inst:bass', title=title)
                    self.ui_manager.set_status('已切换至贝斯板块（占位）')
                except Exception:
                    pass
                return
            if key == 'inst-drums':
                try:
                    self.current_instrument = '架子鼓'
                    title = f"{self.current_instrument}"
                    if getattr(self, 'router', None):
                        self.router.show('inst:drums', title=title)
                    self.ui_manager.set_status('已切换至架子鼓板块')
                except Exception:
                    pass
                return
            if key == 'tool-audio2midi':
                try:
                    if getattr(self, 'router', None):
                        self.router.show('tool:audio2midi', title="音频转MIDI")
                    self.ui_manager.set_status('已切换至 音频转MIDI 工具')
                except Exception:
                    pass
                return
        except Exception:
            pass

    # 已移除：关于窗口与游戏切换等页面功能

    def _update_titles_suffix(self, suffix_text: str | None):
        """更新 UIManager 顶部内嵌标题后缀；根窗口标题保持固定中文。"""
        try:
            suffix = suffix_text if suffix_text and str(suffix_text).strip() else None
            # 更新 UIManager 顶部内嵌标题
            if hasattr(self, 'ui_manager') and hasattr(self.ui_manager, 'set_title_suffix'):
                self.ui_manager.set_title_suffix(suffix)
            # 根窗口标题固定，不随页面变化
            self.root.title("MeowField自动演奏程序")
        except Exception:
            pass
    
    def _create_file_selection_component(self, parent_left=None):
        """创建文件选择组件（委托组件模块）"""
        try:
            target = parent_left if parent_left is not None else self.ui_manager.left_frame
            comp_file_select.create_file_selection(self, target)
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建文件选择组件失败: {e}'}, 'App')

    def _create_playback_control_component(self, parent_left=None, include_ensemble: bool = True):
        """创建播放控制组件（委托组件模块）"""
        try:
            target = parent_left if parent_left is not None else self.ui_manager.left_frame
            comp_playback.create_playback_controls(self, target, include_ensemble=include_ensemble)
        except Exception as e:
            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建播放控制组件失败: {e}'}, 'App')

    def _create_right_pane(self, parent_right=None, *, show_midi_parse: bool = True, show_events: bool = True, show_logs: bool = True):
        """创建右侧分页（委托组件模块）
        参数：
        - show_midi_parse: 是否显示“解析当前MIDI”按钮与“MIDI解析设置”页签
        - show_events: 是否显示“事件表”页签
        - show_logs: 是否显示“系统日志”页签
        """
        try:
            target = parent_right if parent_right is not None else self.ui_manager.right_frame
            comp_right.create_right_pane(self, target, show_midi_parse=show_midi_parse, show_events=show_events, show_logs=show_logs)
        except Exception:
            pass


    def _create_auto_play_controls(self, parent):
        """在播放控制区域创建“自动弹琴/暂停”按钮。
        该方法由 `pages/components/playback_controls.py` 调用。
        """
        try:
            # 行容器
            row = ttk.Frame(parent)
            row.pack(side=tk.TOP, anchor=tk.W, pady=(0, 6))

            # 自动弹琴按钮（开始/停止由内部逻辑切换文案）
            self.auto_play_button = ttk.Button(row, text="自动弹琴", command=self._start_auto_play)
            self.auto_play_button.pack(side=tk.LEFT, padx=(0, 8))

            # 暂停/恢复按钮（默认禁用，开始后启用）
            self.pause_button = ttk.Button(row, text="暂停", state="disabled", command=self._pause_or_resume)
            self.pause_button.pack(side=tk.LEFT)

            # 可视倒计时标签（默认隐藏）
            try:
                self.countdown_label = ttk.Label(row, text="")
                self.countdown_label.pack(side=tk.LEFT, padx=(12,0))
            except Exception:
                self.countdown_label = None

            # 倒计时设置（默认启用3秒）
            try:
                cfg = ttk.Frame(parent)
                cfg.pack(side=tk.TOP, anchor=tk.W, pady=(0, 2))
                ttk.Label(cfg, text="开始前倒计时:").pack(side=tk.LEFT)
                self.enable_auto_countdown_var = tk.BooleanVar(value=True)
                ttk.Checkbutton(cfg, variable=self.enable_auto_countdown_var).pack(side=tk.LEFT, padx=(6, 6))
                self.auto_countdown_seconds_var = tk.IntVar(value=3)
                ttk.Spinbox(cfg, from_=0, to=30, increment=1, width=6, textvariable=self.auto_countdown_seconds_var).pack(side=tk.LEFT)
                ttk.Label(cfg, text="秒").pack(side=tk.LEFT, padx=(6,0))
            except Exception:
                pass
        except Exception as e:
            self._log_message(f"创建自动演奏按钮失败: {e}", "ERROR")

    def _pause_or_resume(self):
        """切换暂停/恢复。供暂停按钮回调使用。"""
        try:
            if self.pause_button.cget("text") == "暂停":
                self._pause_auto_play()
            else:
                self._resume_auto_play()
        except Exception as e:
            self._log_message(f"切换暂停/恢复失败: {e}", "ERROR")

    def _create_bottom_progress(self, parent_left=None):
        """创建左下角进度显示（委托组件模块）。"""
        try:
            target = parent_left if parent_left is not None else self.ui_manager.left_frame
            comp_bottom.create_bottom_progress(self, target)
        except Exception as e:
            self._log_message(f"创建底部进度失败: {e}", "ERROR")


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
            # 若用户已在主界面选择了分部，则优先用所选分部的事件集合作为后续分析输入
            try:
                if isinstance(getattr(self, '_selected_part_names', None), set) and self._selected_part_names and isinstance(getattr(self, '_last_split_parts', None), dict):
                    merged: list[dict] = []
                    for name in self._selected_part_names:
                        sec = self._last_split_parts.get(name)
                        if sec and isinstance(sec, dict):
                            evs = sec.get('notes') or []
                        else:
                            # dataclass PartSection 也可能以对象形式存储
                            evs = getattr(sec, 'notes', []) if sec is not None else []
                        if isinstance(evs, list):
                            merged.extend([e for e in evs if isinstance(e, dict)])
                    if merged:
                        self._log_message(f"使用所选分部进行分析: {', '.join(sorted(self._selected_part_names))} | 事件数: {len(merged)}")
                        notes = merged
            except Exception:
                pass
            # 预处理：整曲移调（优先自动选择白键占比最高的移调）
            if bool(getattr(self, 'enable_preproc_var', tk.BooleanVar(value=False)).get()) and notes:
                try:
                    if bool(getattr(self, 'pretranspose_auto_var', tk.BooleanVar(value=True)).get()):
                        chosen, best_ratio = self._auto_choose_best_transpose(notes)
                        # 应用自动选择的结果
                        auto_notes = getattr(self, '_auto_transposed_notes_cache', None)
                        if auto_notes:
                            notes = auto_notes
                        else:
                            notes = self._transpose_notes(notes, chosen)
                        self.pretranspose_semitones_var.set(chosen)
                        self.pretranspose_white_ratio_var.set(f"{best_ratio*100:.1f}%")
                        self._log_message(f"预处理移调(自动): {chosen} 半音 | 白键占比: {best_ratio*100:.1f}%")
                    else:
                        chosen = int(getattr(self, 'pretranspose_semitones_var', tk.IntVar(value=0)).get())
                        notes = self._transpose_notes(notes, chosen)
                        ratio = self._white_key_ratio(notes)
                        self.pretranspose_white_ratio_var.set(f"{ratio*100:.1f}%")
                        self._log_message(f"预处理移调(手动): {chosen} 半音 | 白键占比: {ratio*100:.1f}%")
                except Exception as exp:
                    self._log_message(f"预处理移调失败: {exp}", "WARNING")
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
        try:
            # 直接调用quit，避免在关闭过程中产生额外输出
            pass
        except Exception:
            pass
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
            # 新工作流：先识别分部，填充左侧分部列表，用户选择后再解析
            try:
                self._ui_select_partitions()
                self.ui_manager.set_status("已识别分部，请在左侧选择分部后点击‘应用所选分部并解析’")
            except Exception as e:
                self._log_message(f"分部识别失败: {e}", "ERROR")
    
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
        """切换自动弹琴（委托控制器）。"""
        try:
            if getattr(self, 'playback_controller', None):
                return self.playback_controller.toggle_auto_play()
        except Exception:
            pass
        # 回退到旧逻辑
        try:
            from meowauto.app.controllers.playback_controller import PlaybackController
            if not getattr(self, 'playback_controller', None):
                self.playback_controller = PlaybackController(self, getattr(self, 'playback_service', None))
            return self.playback_controller.toggle_auto_play()
        except Exception:
            # 最终回退：不做操作
            return
    
    def _toggle_pause(self):
        """切换暂停/恢复状态（委托控制器）。"""
        try:
            if getattr(self, 'playback_controller', None):
                return self.playback_controller.toggle_pause()
        except Exception:
            pass
        # 回退到旧逻辑
        try:
            from meowauto.app.controllers.playback_controller import PlaybackController
            if not getattr(self, 'playback_controller', None):
                self.playback_controller = PlaybackController(self, getattr(self, 'playback_service', None))
            return self.playback_controller.toggle_pause()
        except Exception:
            # 最终回退
            self._log_message("没有正在播放的内容", "WARNING")
            return
    
    def _on_mode_changed(self):
        """演奏模式变化处理"""
        mode = self.playback_mode.get()
        if mode == "midi":
            self._log_message("已切换到MIDI演奏模式", "INFO")
            self.ui_manager.set_status("MIDI演奏模式")
    
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

    # ===================== 分部/分轨 选择与控制 =====================
    def _ui_select_partitions(self):
        """识别当前 MIDI 的分部并在左侧“分部识别与选择”树表中展示；不弹出小窗。"""
        try:
            midi_path = getattr(self, 'midi_path_var', None).get() if hasattr(self, 'midi_path_var') else ''
            if not midi_path or not os.path.exists(midi_path):
                messagebox.showerror("错误", "请先在上方选择有效的MIDI文件")
                return
            if not getattr(self, 'playback_controller', None):
                self.playback_controller = PlaybackController(self, getattr(self, 'playback_service', None))
            # 构建事件
            events = self.playback_controller._build_note_events_with_track(midi_path)
            # 乐器分部优先
            parts = CombinedInstrumentPartitioner().split(events)
            # 回退：若无识别结果，则按轨/通道分离
            if not parts:
                parts = TrackChannelPartitioner(include_meta=True).split(events)
            if not parts:
                messagebox.showwarning("提示", "未能识别到可用分部")
                return
            self._last_split_parts = parts
            # 填充左侧 Treeview
            self._populate_parts_tree(parts)
            # 默认策略：若识别出与当前乐器相关的分部则预选，否则全选
            try:
                related = []
                cur_inst = getattr(self, 'current_instrument', '')
                for name in parts.keys():
                    if ('鼓' in cur_inst and 'drums' in name) or ('贝斯' in cur_inst and 'bass' in name) or ('吉他' in cur_inst and 'guitar' in name) or ('琴' in cur_inst and ('keys' in name or 'piano' in name)):
                        related.append(name)
                if related:
                    self._selected_part_names = set(related)
                    # 选中这些节点
                    if hasattr(self, '_parts_tree'):
                        for iid in self._parts_tree.get_children():
                            vals = self._parts_tree.item(iid, 'values')
                            if vals and vals[0] in self._selected_part_names:
                                self._parts_tree.selection_add(iid)
                else:
                    # 默认全选
                    self._ui_parts_select_all()
            except Exception:
                self._ui_parts_select_all()
            self._log_message("分部识别完成：请在左侧勾选需要的分部，然后点击‘应用所选分部并解析’。")
        except Exception as e:
            self._log_message(f"分部识别失败: {e}", "ERROR")

    def _populate_parts_tree(self, parts: dict):
        """将分部结果填充到左侧 Treeview（_parts_tree）。首列为勾选框字符。"""
        try:
            tree = getattr(self, '_parts_tree', None)
            if tree is None:
                return
            # 勾选字典：若不存在则创建
            if not hasattr(self, '_parts_checked') or not isinstance(getattr(self, '_parts_checked'), dict):
                self._parts_checked = {}
            # 清空
            for iid in tree.get_children():
                tree.delete(iid)
            # 填充
            for name, sec in parts.items():
                if isinstance(sec, dict):
                    cnt = int(sec.get('meta', {}).get('count', len(sec.get('notes') or [])))
                    desc = str(sec.get('meta', {}).get('hint', ''))
                else:
                    try:
                        meta = getattr(sec, 'meta', {}) or {}
                        cnt = int(meta.get('count', len(getattr(sec, 'notes', []) or [])))
                        desc = str(meta.get('hint', ''))
                    except Exception:
                        cnt = len(getattr(sec, 'notes', []) or [])
                        desc = ''
                # 默认选中：若已有状态则沿用，否则默认 True
                checked = bool(self._parts_checked.get(name, True))
                self._parts_checked[name] = checked
                mark = '☑' if checked else '☐'
                # 注意列顺序需与 UI 定义一致（选择, 分部, 计数, 说明）
                tree.insert('', tk.END, values=(mark, name, cnt, desc))
        except Exception as e:
            self._log_message(f"填充分部列表失败: {e}", "ERROR")

    def _get_parts_checked_names(self) -> list[str]:
        names: list[str] = []
        try:
            checked = getattr(self, '_parts_checked', {}) or {}
            # 返回勾选为 True 的分部名
            for name, ok in checked.items():
                if ok:
                    names.append(name)
        except Exception:
            pass
        return names

    def _ui_parts_select_all(self):
        try:
            tree = getattr(self, '_parts_tree', None)
            if tree is None:
                return
            # 勾选全部
            self._parts_checked = {}
            for iid in tree.get_children():
                vals = list(tree.item(iid, 'values'))
                if not vals or len(vals) < 2:
                    continue
                name = vals[1]
                self._parts_checked[name] = True
                vals[0] = '☑'
                tree.item(iid, values=vals)
        except Exception:
            pass

    def _ui_parts_select_none(self):
        try:
            tree = getattr(self, '_parts_tree', None)
            if tree is None:
                return
            # 全部取消
            self._parts_checked = {}
            for iid in tree.get_children():
                vals = list(tree.item(iid, 'values'))
                if not vals or len(vals) < 2:
                    continue
                name = vals[1]
                self._parts_checked[name] = False
                vals[0] = '☐'
                tree.item(iid, values=vals)
        except Exception:
            pass

    def _ui_parts_select_invert(self):
        try:
            tree = getattr(self, '_parts_tree', None)
            if tree is None:
                return
            # 逐行取反
            if not hasattr(self, '_parts_checked'):
                self._parts_checked = {}
            for iid in tree.get_children():
                vals = list(tree.item(iid, 'values'))
                if not vals or len(vals) < 2:
                    continue
                name = vals[1]
                cur = bool(self._parts_checked.get(name, False))
                self._parts_checked[name] = not cur
                vals[0] = '☑' if not cur else '☐'
                tree.item(iid, values=vals)
        except Exception:
            pass

    def _ui_apply_selected_parts_and_analyze(self):
        """将 Treeview 中所选分部写入集合并进入解析流程。"""
        try:
            sels = self._get_parts_checked_names()
            if not sels:
                messagebox.showwarning("提示", "未选择任何分部")
                return
            self._selected_part_names = set(sels)
            self._log_message(f"分部已选择: {', '.join(sels)}，开始解析...")
            self._analyze_current_midi()
        except Exception as e:
            self._log_message(f"应用所选分部并解析失败: {e}", "ERROR")

    def _open_part_selection_dialog(self, part_names):
        """弹出多选窗口供用户选择分部。"""
        try:
            win = tk.Toplevel(self.root)
            win.title("选择要播放/导出的分部")
            win.geometry("420x360")
            ttk.Label(win, text="可用分部（可多选）:").pack(side=tk.TOP, anchor=tk.W, padx=10, pady=(10, 6))
            lb = tk.Listbox(win, selectmode=tk.MULTIPLE)
            lb.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            for n in part_names:
                lb.insert(tk.END, n)

            # 预选之前选过的
            try:
                previously = [n for n in part_names if n in getattr(self, '_selected_part_names', set())]
                for i, n in enumerate(part_names):
                    if n in previously:
                        lb.selection_set(i)
            except Exception:
                pass

            btn_row = ttk.Frame(win)
            btn_row.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

            def on_ok():
                try:
                    sels = [part_names[i] for i in lb.curselection()]
                    if not sels:
                        messagebox.showwarning("提示", "未选择任何分部")
                        return
                    self._selected_part_names = set(sels)
                    self._log_message(f"分部已选择: {', '.join(sels)}")
                    win.destroy()
                except Exception:
                    win.destroy()

            def on_all():
                lb.select_set(0, tk.END)

            ttk.Button(btn_row, text="全选", command=on_all).pack(side=tk.LEFT)
            ttk.Button(btn_row, text="确定", command=on_ok).pack(side=tk.RIGHT)
            ttk.Button(btn_row, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=(8, 0))
            win.transient(self.root)
            win.grab_set()
            self.root.wait_window(win)
        except Exception as e:
            self._log_message(f"打开分部选择窗口失败: {e}", "ERROR")

    def _ui_play_selected_partitions(self):
        """使用控制器播放已选择的分部（若未选择则尝试先识别并选择）。"""
        try:
            if not getattr(self, '_last_split_parts', None):
                self._ui_select_partitions()
            parts = getattr(self, '_last_split_parts', {})
            if not parts:
                messagebox.showwarning("提示", "没有可用分部可播放")
                return
            # 优先读取 Treeview 勾选
            selected = self._get_parts_checked_names()
            if not selected:
                selected = list(getattr(self, '_selected_part_names', set()) or [])
            if not selected:
                # 默认全选
                selected = list(parts.keys())
            if not getattr(self, 'playback_controller', None):
                self.playback_controller = PlaybackController(self, getattr(self, 'playback_service', None))
            mode = None
            my_role = None
            try:
                mode = getattr(self, 'ensemble_mode_var', tk.StringVar(value='ensemble')).get()
            except Exception:
                mode = None
            ok = bool(self.playback_controller.play_selected_parts(
                parts, selected,
                tempo=float(getattr(self, 'tempo_scale_var', tk.DoubleVar(value=1.0)).get()),
                on_progress=getattr(self, '_on_play_progress', None),
                mode=mode,
                my_role=my_role,
            ))
            if ok:
                self._log_message(f"正在播放分部: {', '.join(selected)}")
                self.ui_manager.set_status("正在播放所选分部")
            else:
                messagebox.showerror("错误", "分部播放失败")
        except Exception as e:
            self._log_message(f"分部播放异常: {e}", "ERROR")

    def _ui_export_selected_partitions(self):
        """将所选分部分别导出为多个 MIDI 文件。"""
        try:
            if not getattr(self, '_last_split_parts', None):
                self._ui_select_partitions()
            parts = getattr(self, '_last_split_parts', {})
            if not parts:
                messagebox.showwarning("提示", "没有可用分部可导出")
                return
            # 优先读取 Treeview 勾选
            selected = self._get_parts_checked_names()
            if not selected:
                selected = list(getattr(self, '_selected_part_names', set()) or [])
            if selected:
                # 仅保留所选
                parts = {k: v for k, v in parts.items() if k in set(selected)}
            out_dir = filedialog.askdirectory(title="选择导出文件夹")
            if not out_dir:
                return
            if not getattr(self, 'playback_controller', None):
                self.playback_controller = PlaybackController(self, getattr(self, 'playback_service', None))
            written = self.playback_controller.export_partitions_to_midis(parts, out_dir, tempo_bpm=120)
            if written:
                messagebox.showinfo("导出完成", f"已导出 {len(written)} 个文件到:\n{out_dir}")
            else:
                messagebox.showwarning("提示", "没有写出任何文件")
        except Exception as e:
            self._log_message(f"导出分部异常: {e}", "ERROR")

    # ===================== 播放列表控制器方法 =====================
    def _add_to_playlist(self):
        try:
            filetypes = [
                ("支持的文件", ".mid .midi .lrcp .mp3 .wav .flac .m4a .aac .ogg"),
{{ ... }}
                ("MIDI", ".mid .midi"),
                ("谱面 LRCp", ".lrcp"),
                ("音频", ".mp3 .wav .flac .m4a .aac .ogg"),
                ("所有文件", "*.*"),
            ]
            paths = filedialog.askopenfilenames(title="添加到播放列表", filetypes=filetypes)
            if not paths:
                return
            for p in paths:
                if self.playlist and self.playlist.add_item(p):
                    self._append_playlist_tree_row(p)
        except Exception as e:
            self._log_message(f"添加文件失败: {e}", "ERROR")

    def _import_folder_to_playlist(self):
        try:
            folder = filedialog.askdirectory(title="选择文件夹导入")
            if not folder:
                return
            exts = {'.mid','.midi','.lrcp','.mp3','.wav','.flac','.m4a','.aac','.ogg'}
            for root, _, files in os.walk(folder):
                for name in files:
                    if os.path.splitext(name)[1].lower() in exts:
                        p = os.path.join(root, name)
                        if self.playlist and self.playlist.add_item(p):
                            self._append_playlist_tree_row(p)
        except Exception as e:
            self._log_message(f"导入文件夹失败: {e}", "ERROR")

    def _remove_from_playlist(self):
        try:
            sel = list(self.playlist_tree.selection()) if hasattr(self, 'playlist_tree') else []
            if not sel:
                return
            # 从后往前移除，避免索引变化
            indices = sorted([int(self.playlist_tree.item(iid,'values')[0]) - 1 for iid in sel], reverse=True)
            for idx in indices:
                try:
                    if self.playlist:
                        self.playlist.remove_item(idx)
                finally:
                    # 删除树节点
                    for iid in sel:
                        self.playlist_tree.delete(iid)
            self._rebuild_playlist_tree()
        except Exception as e:
            self._log_message(f"移除失败: {e}", "ERROR")

    def _clear_playlist(self):
        try:
            if self.playlist:
                self.playlist.clear_playlist()
            if hasattr(self, 'playlist_tree'):
                for iid in self.playlist_tree.get_children():
                    self.playlist_tree.delete(iid)
        except Exception as e:
            self._log_message(f"清空播放列表失败: {e}", "ERROR")

    def _save_playlist(self):
        try:
            if not self.playlist or not self.playlist.playlist_items:
                messagebox.showinfo("提示", "播放列表为空")
                return
            path = filedialog.asksaveasfilename(title="保存播放列表", defaultextension=".json", filetypes=[("JSON","*.json")])
            if not path:
                return
            data = [it['path'] for it in self.playlist.playlist_items]
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log_message(f"播放列表已保存: {os.path.basename(path)}", "SUCCESS")
        except Exception as e:
            self._log_message(f"保存播放列表失败: {e}", "ERROR")

    def _append_playlist_tree_row(self, file_path: str):
        try:
            if not hasattr(self, 'playlist_tree') or not self.playlist:
                return
            idx = len(self.playlist.playlist_items)
            item = self.playlist.playlist_items[-1]
            values = (idx, item.get('name'), item.get('type'), item.get('duration'), item.get('status'))
            self.playlist_tree.insert('', 'end', values=values)
        except Exception:
            pass

    def _rebuild_playlist_tree(self):
        try:
            if not hasattr(self, 'playlist_tree') or not self.playlist:
                return
            for iid in self.playlist_tree.get_children():
                self.playlist_tree.delete(iid)
            for i, it in enumerate(self.playlist.playlist_items, start=1):
                self.playlist_tree.insert('', 'end', values=(i, it.get('name'), it.get('type'), it.get('duration'), it.get('status')))
        except Exception:
            pass

    def _on_playlist_mode_changed(self, *_):
        try:
            mode = getattr(self, 'playlist_mode_var', None)
            mode_str = mode.get() if mode else '单曲'
            if self.playlist:
                if mode_str == '随机':
                    self.playlist.random_play = True
                    self.playlist.loop_play = False
                elif mode_str == '循环':
                    self.playlist.random_play = False
                    self.playlist.loop_play = True
                elif mode_str == '顺序':
                    self.playlist.random_play = False
                    self.playlist.loop_play = False
                else:  # 单曲
                    self.playlist.random_play = False
                    self.playlist.loop_play = False
            self._log_message(f"播放模式: {mode_str}")
        except Exception:
            pass

    def _play_selected_from_playlist(self):
        try:
            if not hasattr(self, 'playlist_tree') or not self.playlist:
                return
            sel = self.playlist_tree.selection()
            if not sel:
                return
            # 取首个选中
            values = self.playlist_tree.item(sel[0], 'values')
            index = int(values[0]) - 1
            if self.playlist.set_current_item(index):
                item = self.playlist.get_current_item()
                if item and item.get('path'):
                    # 将路径放入 midi_path_var 并开始
                    if not hasattr(self, 'midi_path_var'):
                        self.midi_path_var = tk.StringVar()
                    self.midi_path_var.set(item['path'])
                    self._start_auto_play()
        except Exception as e:
            self._log_message(f"播放选中失败: {e}", "ERROR")

    def _play_next_from_playlist(self):
        try:
            if not self.playlist:
                return
            next_item = self.playlist.play_next()
            if next_item and next_item.get('path'):
                if not hasattr(self, 'midi_path_var'):
                    self.midi_path_var = tk.StringVar()
                self.midi_path_var.set(next_item['path'])
                self._start_auto_play()
                self._rebuild_playlist_tree()
        except Exception as e:
            self._log_message(f"下一首失败: {e}", "ERROR")

    def _play_prev_from_playlist(self):
        try:
            if not self.playlist:
                return
            prev_item = self.playlist.play_previous()
            if prev_item and prev_item.get('path'):
                if not hasattr(self, 'midi_path_var'):
                    self.midi_path_var = tk.StringVar()
                self.midi_path_var.set(prev_item['path'])
                self._start_auto_play()
                self._rebuild_playlist_tree()
        except Exception as e:
            self._log_message(f"上一首失败: {e}", "ERROR")

    def _apply_player_options(self):
        """将 UI 的高级设置应用到 AutoPlayer"""
        try:
            if hasattr(self, 'auto_player') and self.auto_player and hasattr(self.auto_player, 'set_options'):
                # 仅保留必要选项下发：键位回退与黑键移调
                enable_key_fallback = bool(self.r_enable_key_fallback_var.get()) if hasattr(self, 'r_enable_key_fallback_var') else True
                # 回放层禁用黑键移调
                enable_black_transpose = False
                black_transpose_strategy = (
                    'down' if (
                        getattr(self, 'black_transpose_strategy_var', None) and 
                        str(self.black_transpose_strategy_var.get()) in ('向下', '向下优先')
                    ) else 'nearest'
                )
                # 新增：和弦伴奏选项（默认关闭；UI 尚未提供时使用默认值）
                enable_chord_accomp = False
                chord_accomp_mode = 'triad'
                chord_accomp_min_sustain_ms = 120
                chord_replace_melody = False
                try:
                    if hasattr(self, 'enable_chord_accomp_var'):
                        enable_chord_accomp = bool(self.enable_chord_accomp_var.get())
                    if hasattr(self, 'chord_accomp_mode_var'):
                        chord_accomp_mode = str(self.chord_accomp_mode_var.get()) or 'triad'
                    if hasattr(self, 'chord_accomp_min_sustain_var'):
                        chord_accomp_min_sustain_ms = int(self.chord_accomp_min_sustain_var.get())
                    if hasattr(self, 'chord_replace_melody_var'):
                        chord_replace_melody = bool(self.chord_replace_melody_var.get())
                except Exception:
                    # 保持默认值
                    pass

                self.auto_player.set_options(
                    enable_key_fallback=enable_key_fallback,
                    enable_black_transpose=enable_black_transpose,
                    black_transpose_strategy=black_transpose_strategy,
                    enable_chord_accomp=enable_chord_accomp,
                    chord_accomp_mode=chord_accomp_mode,
                    chord_accomp_min_sustain_ms=chord_accomp_min_sustain_ms,
                    chord_replace_melody=chord_replace_melody,
                )
        except Exception as e:
            self._log_message(f"应用回放设置失败: {str(e)}", "ERROR")
    
    def _start_auto_play(self):
        """开始自动弹琴（仅MIDI模式）"""
        try:
            # 检查是否已经在演奏中
            if hasattr(self, 'auto_player') and self.auto_player and self.auto_player.is_playing:
                self._log_message("自动演奏已在进行中", "WARNING")
                return
            # 如有未完成的倒计时，先取消
            try:
                if hasattr(self, '_countdown_after_id') and self._countdown_after_id:
                    self.root.after_cancel(self._countdown_after_id)
                    self._countdown_after_id = None
            except Exception:
                pass

            # 倒计时触发
            def _do_start():
                self._start_midi_play()
                # 清除倒计时可视
                try:
                    if getattr(self, 'countdown_label', None):
                        self.countdown_label.configure(text="")
                except Exception:
                    pass
            try:
                enabled = bool(getattr(self, 'enable_auto_countdown_var', tk.BooleanVar(value=False)).get())
                sec = int(getattr(self, 'auto_countdown_seconds_var', tk.IntVar(value=0)).get())
            except Exception:
                enabled, sec = False, 0
            if enabled and sec > 0:
                def _tick(n: int):
                    if n <= 0:
                        self._log_message("开始！", "SUCCESS")
                        _do_start()
                        return
                    # 可视更新 + 日志
                    try:
                        if getattr(self, 'countdown_label', None):
                            self.countdown_label.configure(text=f"{n}s")
                    except Exception:
                        pass
                    self._log_message(f"倒计时: {n}", "INFO")
                    if hasattr(self, 'root'):
                        self._countdown_after_id = self.root.after(1000, lambda: _tick(n - 1))
                self._countdown_after_id = self.root.after(0, lambda: _tick(sec))
            else:
                _do_start()
        except Exception as e:
            self._log_message(f"启动自动弹琴失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"启动自动弹琴失败:\n{str(e)}")
    
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
                
                # 服务层启动自动演奏
                if not getattr(self, 'playback_service', None):
                    try:
                        from meowauto.app.services.playback_service import PlaybackService
                        self.playback_service = PlaybackService()
                    except Exception:
                        self.playback_service = None

                success = False
                if getattr(self, 'playback_service', None):
                    # 确保 service 内部已初始化，保持 self.auto_player 引用可用于 UI 检测
                    try:
                        self.playback_service.init_players()
                        self.auto_player = self.playback_service.auto_player
                    except Exception:
                        pass

                    # 组装回调
                    enable_cb = True
                    try:
                        enable_cb = bool(self.playback_callbacks_enabled_var.get())
                    except Exception:
                        enable_cb = True
                    try:
                        self.playback_service.set_auto_callbacks(
                            on_start=lambda: self._log_message("自动演奏已开始", "SUCCESS"),
                            on_pause=lambda: self._log_message("自动演奏已暂停", "INFO"),
                            on_resume=lambda: self._log_message("自动演奏已恢复", "INFO"),
                            on_stop=lambda: self._log_message("自动演奏已停止"),
                            on_progress=(lambda p: self._on_progress_update(p)) if enable_cb else None,
                            on_complete=lambda: self._on_playback_complete(),
                            on_error=lambda msg: self._log_message(f"自动演奏错误: {msg}", "ERROR"),
                        )
                    except Exception:
                        pass

                    # 收集 options（等价于 _apply_player_options 但不直接依赖 self.auto_player）
                    enable_key_fallback = bool(self.r_enable_key_fallback_var.get()) if hasattr(self, 'r_enable_key_fallback_var') else True
                    enable_black_transpose = bool(self.enable_black_transpose_var.get()) if hasattr(self, 'enable_black_transpose_var') else True
                    black_transpose_strategy = (
                        'down' if (
                            getattr(self, 'black_transpose_strategy_var', None) and 
                            str(self.black_transpose_strategy_var.get()) in ('向下', '向下优先')
                        ) else 'nearest'
                    )
                    enable_chord_accomp = False
                    chord_accomp_mode = 'triad'
                    chord_accomp_min_sustain_ms = 120
                    try:
                        if hasattr(self, 'enable_chord_accomp_var'):
                            enable_chord_accomp = bool(self.enable_chord_accomp_var.get())
                        if hasattr(self, 'chord_accomp_mode_var'):
                            chord_accomp_mode = str(self.chord_accomp_mode_var.get()) or 'triad'
                        if hasattr(self, 'chord_accomp_min_sustain_var'):
                            chord_accomp_min_sustain_ms = int(self.chord_accomp_min_sustain_var.get())
                    except Exception:
                        pass
                    try:
                        # 黑键移调为后处理，这里禁用
                        self.playback_service.configure_auto_player(
                            debug=(bool(self.debug_var.get()) if hasattr(self, 'debug_var') else None),
                            options=dict(
                                enable_key_fallback=enable_key_fallback,
                                enable_black_transpose=False,
                                black_transpose_strategy='nearest',
                                enable_chord_accomp=enable_chord_accomp,
                                chord_accomp_mode=chord_accomp_mode,
                                chord_accomp_min_sustain_ms=chord_accomp_min_sustain_ms,
                            ),
                        )
                    except Exception:
                        pass

                    # key mapping
                    try:
                        if hasattr(self, 'keymap_manager') and self.keymap_manager:
                            default_key_mapping = self.keymap_manager.get_mapping()
                        else:
                            from meowauto.config.key_mapping_manager import DEFAULT_MAPPING
                            default_key_mapping = DEFAULT_MAPPING
                    except Exception:
                        from meowauto.config.key_mapping_manager import DEFAULT_MAPPING
                        default_key_mapping = DEFAULT_MAPPING

                    # 分析结果复用与策略名
                    try:
                        strategy_name = self._resolve_strategy_name()
                    except Exception:
                        strategy_name = "strategy_21key"
                    use_analyzed = False
                    try:
                        if getattr(self, 'analysis_notes', None) and getattr(self, 'analysis_file', ''):
                            if os.path.abspath(self.analysis_file) == os.path.abspath(midi_path):
                                use_analyzed = True
                    except Exception:
                        use_analyzed = False

                    success = bool(self.playback_service.start_auto_play_from_path(
                        midi_path,
                        tempo=self.tempo_var.get(),
                        key_mapping=default_key_mapping,
                        strategy_name=strategy_name,
                        use_analyzed=use_analyzed,
                        analyzed_notes=(self.analysis_notes if use_analyzed else None),
                    ))
                else:
                    success = False

                if success:
                    # 更新按钮状态
                    self.auto_play_button.configure(text="停止弹琴", command=self._stop_auto_play)
                    self.pause_button.configure(text="暂停", state="normal")
                    self.ui_manager.set_status(f"自动弹琴已开始: {file_name}")
                    self._log_message(f"开始自动弹琴: {file_name} ({file_type})", "SUCCESS")
                    
                    # 更新播放列表状态（统一设置为正在播放）
                    try:
                        selected = self.playlist_tree.selection()
                        if selected:
                            self.playlist_tree.set(selected[0], "状态", "正在播放")
                    except Exception:
                        pass
                    
                    # 进度由真实回调驱动
                    # 启动自动连播watchdog兜底
                    try:
                        self._schedule_auto_next_watchdog()
                    except Exception:
                        pass
                else:
                    # 启动失败：标记状态并自动跳过到下一首，避免停滞
                    self._log_message("自动演奏启动失败，自动跳过到下一首", "ERROR")
                    try:
                        selected = self.playlist_tree.selection()
                        if selected:
                            self.playlist_tree.set(selected[0], "状态", "错误")
                    except Exception:
                        pass
                    try:
                        if hasattr(self, 'root'):
                            self.root.after(60, self._play_next)
                        else:
                            self._play_next()
                    except Exception:
                        pass
                    
            except ImportError as e:
                # 服务层/自动演奏模块不可用
                self._log_message(f"自动演奏模块不可用: {e}", "ERROR")
                raise
            
        except Exception as e:
            self._log_message(f"MIDI模式演奏失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"MIDI模式演奏失败:\n{str(e)}")
    
    
    
    def _stop_auto_play(self):
        """停止自动弹琴"""
        try:
            # 停止实际的自动演奏（委托服务层）
            try:
                if getattr(self, 'playback_service', None):
                    self.playback_service.stop_auto_only(getattr(self, 'auto_player', None))
                elif hasattr(self, 'auto_player') and self.auto_player:
                    # 向后兼容：若服务未初始化，直接调用旧实例
                    self.auto_player.stop_auto_play()
            except Exception as e:
                self._log_message(f"停止自动演奏器失败: {str(e)}", "WARNING")
            
            # 更新按钮状态
            self.auto_play_button.configure(text="自动弹琴", command=self._start_auto_play)
            self.pause_button.configure(text="暂停", state="disabled")
            # 取消倒计时并清空显示
            try:
                if hasattr(self, '_countdown_after_id') and self._countdown_after_id:
                    self.root.after_cancel(self._countdown_after_id)
                    self._countdown_after_id = None
                if getattr(self, 'countdown_label', None):
                    self.countdown_label.configure(text="")
            except Exception:
                pass
            self.ui_manager.set_status("自动弹琴已停止")
            self._log_message("自动弹琴已停止")
            # 关闭watchdog
            try:
                self._cancel_auto_next_watchdog()
            except Exception:
                pass
            
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
        # 防抖：标记已由完成回调触发，避免watchdog重复触发
        try:
            setattr(self, '_auto_next_guard', True)
            if hasattr(self, 'root'):
                self.root.after(2000, lambda: setattr(self, '_auto_next_guard', False))
        except Exception:
            pass
        # 将当前选中的播放列表项标记为已播放
        try:
            selected = self.playlist_tree.selection()
            if selected:
                self.playlist_tree.set(selected[0], "状态", "已播放")
        except Exception:
            pass
        
        # 自动播放下一首
        try:
            # 给 AutoPlayer 状态落盘与线程退出一点缓冲
            if hasattr(self, 'root'):
                self.root.after(120, self._play_next)
            else:
                self._play_next()
        except Exception:
            self._play_next()
    
    def _play_next(self):
        try:
            all_items = self.playlist_tree.get_children()
            if not all_items:
                self._stop_auto_play()
                return
            # 同步当前索引至管理器
            try:
                cur_idx = self._get_selected_playlist_index()
                if cur_idx is not None and getattr(self, 'playlist', None):
                    self.playlist.select_index(cur_idx)
                    # 确保模式与UI一致
                    self.playlist.set_order_mode(self.playlist_order_var.get())
                self._log_message(f"[NEXT] 当前索引={cur_idx} 模式={getattr(self, 'playlist_order_var', tk.StringVar(value='顺序')).get()}", "INFO")
            except Exception:
                pass
            # 询问管理器下一首
            next_idx = None
            if getattr(self, 'playlist', None):
                next_idx = self.playlist.next_index()
            self._log_message(f"[NEXT] 计算下一首索引={next_idx}", "INFO")
            # 顺序模式且到末尾
            if next_idx is None:
                self._stop_auto_play()
                return
            # 选中并播放
            self._select_playlist_index(next_idx)
            if hasattr(self, 'root'):
                self.root.after(0, self._play_selected_playlist_item)
            else:
                self._play_selected_playlist_item()
        except Exception as e:
            self._log_message(f"播放下一首失败: {str(e)}", "ERROR")
            self._stop_auto_play()

    def _schedule_auto_next_watchdog(self):
        """启动自动连播兜底检测：当AutoPlayer自然结束但未触发完成回调时，主动切下一首。"""
        try:
            # 先取消已有的
            self._cancel_auto_next_watchdog()
            # 初始化前一状态为正在播放，避免启动瞬间误触发
            self._auto_watch_prev_state = True
            def _tick():
                try:
                    playing = bool(getattr(self, 'auto_player', None) and self.auto_player.is_playing)
                    guard = bool(getattr(self, '_auto_next_guard', False))
                    if not playing and self._auto_watch_prev_state and not guard:
                        # 从 播放中 -> 非播放 且 未由完成回调触发，认为自然完成，兜底触发
                        self._log_message("[WD] 检测到播放结束，兜底触发自动下一首", "INFO")
                        self._on_playback_complete()
                        return
                    self._auto_watch_prev_state = playing
                except Exception:
                    pass
                finally:
                    try:
                        if hasattr(self, 'root'):
                            self._auto_next_watchdog_id = self.root.after(700, _tick)
                    except Exception:
                        pass
            if hasattr(self, 'root'):
                self._auto_next_watchdog_id = self.root.after(700, _tick)
        except Exception:
            pass

    def _cancel_auto_next_watchdog(self):
        """停止自动连播兜底检测"""
        try:
            if hasattr(self, '_auto_next_watchdog_id') and self._auto_next_watchdog_id and hasattr(self, 'root'):
                try:
                    self.root.after_cancel(self._auto_next_watchdog_id)
                except Exception:
                    pass
            self._auto_next_watchdog_id = None
        except Exception:
            pass

    def _play_selected_playlist_item(self):
        """根据播放列表当前选择，设置模式/路径，必要时解析，然后开始自动播放"""
        try:
            selected = self.playlist_tree.selection()
            if not selected:
                return
            item_id = selected[0]
            item = self.playlist_tree.item(item_id)
            filename = item['values'][1] if item['values'] else "未知文件"
            ftype = item['values'][2] if item['values'] and len(item['values']) > 2 else "未知类型"
            # 完整路径
            full_path = None
            try:
                if hasattr(self, '_file_paths'):
                    full_path = self._file_paths.get(item_id)
            except Exception:
                full_path = None
            if not full_path:
                full_path = filename
            # 日志增强
            try:
                self._log_message(f"[PLAY] 选择项ID={item_id} 文件={filename} 路径={full_path} 类型={ftype}", "INFO")
            except Exception:
                pass
            # 同步当前索引到管理器
            try:
                idx = self._get_selected_playlist_index()
                if idx is not None and getattr(self, 'playlist', None):
                    self.playlist.select_index(idx)
            except Exception:
                pass
            if ftype == "MIDI文件" and full_path:
                self.playback_mode.set("midi")
                self.midi_path_var.set(full_path)
                # 解析（会应用预处理与后处理）
                try:
                    self._analyze_current_midi()
                except Exception as e:
                    self._log_message(f"解析失败: {e}", "ERROR")
                # 若仍在播放，先停止，避免“仍在播放”导致无法启动下一首
                try:
                    if hasattr(self, 'auto_player') and self.auto_player and self.auto_player.is_playing:
                        self._log_message("检测到仍在播放，先停止当前演奏以切换下一首", "INFO")
                        self.auto_player.stop_auto_play()
                except Exception:
                    pass
                # 稍作延迟以确保线程完全退出
                try:
                    if hasattr(self, 'root'):
                        self.root.after(50, self._start_midi_play)
                    else:
                        self._start_midi_play()
                except Exception:
                    self._start_midi_play()
                # 更新播放列表状态
                try:
                    self.playlist_tree.set(item_id, "状态", "正在播放")
                except Exception:
                    pass
            else:
                self._log_message(f"不支持的文件类型: {filename}", "WARNING")
        except Exception as e:
            self._log_message(f"播放选中项失败: {e}", "ERROR")

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
            # 使用导出工具模块，保持列结构一致
            export_event_csv(self.event_tree, filename)
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
            # 构建按键谱文本（迁移到工具模块）
            content = build_key_notation(rows, chords_by_time, unit=0.3)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            self._log_message(f"按键谱已导出: {filename}", "SUCCESS")
            messagebox.showinfo("成功", f"按键谱已导出到:\n{filename}")
        except Exception as e:
            self._log_message(f"导出按键谱失败: {e}", "ERROR")
    
    

    def _stop_playback(self):
        """停止播放（委托服务层）"""
        try:
            try:
                if getattr(self, 'playback_service', None):
                    self.playback_service.stop_all()
                else:
                    # 向后兼容：若服务未初始化，直接尝试旧实例
                    if hasattr(self, 'midi_player') and self.midi_player:
                        self.midi_player.stop_midi()
                    if hasattr(self, 'auto_player') and self.auto_player:
                        self.auto_player.stop_auto_play()
                self._log_message("MIDI播放已停止")
                self._log_message("自动演奏已停止")
            except Exception:
                pass

            # 重置进度
            try:
                self.progress_var.set(0)
                self.time_var.set("00:00 / 00:00")
            except Exception:
                pass

            # 禁用暂停按钮
            if hasattr(self, 'pause_button'):
                self.pause_button.configure(text="暂停", state="disabled")
            # 重置自动弹琴按钮文本
            if hasattr(self, 'auto_play_button'):
                try:
                    self.auto_play_button.configure(text="自动弹琴", command=self._start_auto_play)
                except Exception:
                    pass
            # 取消倒计时并清空显示
            try:
                if hasattr(self, '_countdown_after_id') and self._countdown_after_id:
                    self.root.after_cancel(self._countdown_after_id)
                    self._countdown_after_id = None
                if getattr(self, 'countdown_label', None):
                    self.countdown_label.configure(text="")
            except Exception:
                pass
            
            self.ui_manager.set_status("播放已停止")
            self._log_message("播放已停止")
            
            # 更新播放列表状态
            try:
                selected = self.playlist_tree.selection()
                if selected:
                    self.playlist_tree.set(selected[0], "状态", "已停止")
            except Exception:
                pass
            # 关闭watchdog
            try:
                self._cancel_auto_next_watchdog()
            except Exception:
                pass
        except Exception as e:
            self._log_message(f"停止播放失败: {str(e)}", "ERROR")

    def _play_midi(self):
        """播放左上选择的MIDI文件（委托服务层）"""
        try:
            midi_path = self.midi_path_var.get() if hasattr(self, 'midi_path_var') else ''
            if not midi_path:
                messagebox.showerror("错误", "请先选择MIDI文件")
                return
            if not os.path.exists(midi_path):
                messagebox.showerror("错误", "MIDI文件不存在")
                return
            self.ui_manager.set_status("正在播放MIDI...")
            self._log_message("开始播放MIDI文件")
            tempo = float(self.tempo_var.get()) if hasattr(self, 'tempo_var') else 1.0
            volume = float(self.volume_var.get()) if hasattr(self, 'volume_var') else 0.7
            ok = False
            try:
                if getattr(self, 'playback_service', None):
                    ok = bool(self.playback_service.play_midi(
                        midi_path, tempo=tempo, volume=volume, on_progress=self._on_progress_update
                    ))
                else:
                    ok = False
            except Exception as e:
                self._log_message(f"启动MIDI播放失败: {e}", "ERROR")
            if ok:
                self._log_message("MIDI播放成功", "SUCCESS")
                self.ui_manager.set_status("MIDI播放中...")
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="暂停", state="正常" if hasattr(self.pause_button, 'state') else "normal")
                    try:
                        self.pause_button.configure(state="normal")
                    except Exception:
                        pass
            else:
                self._log_message("MIDI播放失败", "ERROR")
                self.ui_manager.set_status("MIDI播放失败")
                messagebox.showerror("错误", "MIDI播放失败，请检查文件格式")
        except ImportError:
            self._log_message("MIDI播放模块不可用", "ERROR")
            messagebox.showerror("错误", "MIDI播放模块不可用，请检查meowauto模块")
        except Exception as e:
            self._log_message(f"MIDI播放异常: {e}", "ERROR")
            messagebox.showerror("错误", f"MIDI播放过程中发生错误:\n{e}")

    def _pause_midi_play(self):
        """暂停MIDI播放（若支持）"""
        try:
            if hasattr(self, 'midi_player') and self.midi_player:
                try:
                    if hasattr(self.midi_player, 'pause_midi'):
                        self.midi_player.pause_midi()
                    elif hasattr(self.midi_player, 'pause'):
                        self.midi_player.pause()
                    self._log_message("MIDI播放已暂停")
                    if hasattr(self, 'pause_button'):
                        self.pause_button.configure(text="恢复")
                except Exception as e:
                    self._log_message(f"暂停MIDI失败: {e}", "WARNING")
        except Exception:
            pass

    def _resume_midi_play(self):
        """恢复MIDI播放（若支持）"""
        try:
            if hasattr(self, 'midi_player') and self.midi_player:
                try:
                    if hasattr(self.midi_player, 'resume_midi'):
                        self.midi_player.resume_midi()
                    elif hasattr(self.midi_player, 'resume'):
                        self.midi_player.resume()
                    self._log_message("MIDI播放已恢复")
                    if hasattr(self, 'pause_button'):
                        self.pause_button.configure(text="暂停")
                except Exception as e:
                    self._log_message(f"恢复MIDI失败: {e}", "WARNING")
        except Exception:
            pass
    
    def _pause_auto_play(self):
        """暂停自动演奏（若支持）"""
        try:
            if getattr(self, 'playback_service', None):
                self.playback_service.pause_auto_only(getattr(self, 'auto_player', None))
                self._log_message("自动演奏已暂停")
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="恢复")
            elif hasattr(self, 'auto_player') and self.auto_player and hasattr(self.auto_player, 'pause_auto_play'):
                self.auto_player.pause_auto_play()
                self._log_message("自动演奏已暂停")
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="恢复")
        except Exception as e:
            self._log_message(f"暂停自动演奏失败: {e}", "WARNING")

    def _resume_auto_play(self):
        """恢复自动演奏（若支持）"""
        try:
            if getattr(self, 'playback_service', None):
                self.playback_service.resume_auto_only(getattr(self, 'auto_player', None))
                self._log_message("自动演奏已恢复")
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="暂停")
            elif hasattr(self, 'auto_player') and self.auto_player and hasattr(self.auto_player, 'resume_auto_play'):
                self.auto_player.resume_auto_play()
                self._log_message("自动演奏已恢复")
                if hasattr(self, 'pause_button'):
                    self.pause_button.configure(text="暂停")
        except Exception as e:
            self._log_message(f"恢复自动演奏失败: {e}", "WARNING")

    # ===== 合奏：网络时钟与统一开始 =====
    def _ensure_playback_service(self):
        try:
            if not getattr(self, 'playback_service', None):
                from meowauto.app.services.playback_service import PlaybackService
                self.playback_service = PlaybackService()
            # 确保 players 初始化，并缓存 auto_player 引用
            try:
                self.playback_service.init_players()
                self.auto_player = self.playback_service.auto_player
            except Exception:
                pass
        except Exception:
            self.playback_service = None

    def _enable_network_clock(self):
        """启用公网对时并立即同步。"""
        try:
            self._ensure_playback_service()
            if not getattr(self, 'playback_service', None):
                self._log_message("播放服务不可用，无法启用网络时钟", "ERROR")
                return
            ok = bool(self.playback_service.use_network_clock())
            if ok:
                self._log_message("已启用网络时钟并完成同步", "SUCCESS")
            else:
                self._log_message("启用网络时钟失败，可能无法访问NTP服务器", "WARNING")
        except Exception as e:
            self._log_message(f"启用网络时钟异常: {e}", "ERROR")

    def _sync_network_clock(self):
        """手动对时：若已有网络时钟则调用其 sync()，否则尝试启用一次网络对时。"""
        try:
            self._ensure_playback_service()
            if not getattr(self, 'playback_service', None):
                self._log_message("播放服务不可用，无法对时", "ERROR")
                return
            provider = getattr(self.playback_service, 'clock_provider', None)
            ok = False
            try:
                if provider and hasattr(provider, 'sync'):
                    ok = bool(provider.sync())
            except Exception:
                ok = False
            if not ok:
                ok = bool(self.playback_service.use_network_clock())
            if ok:
                self._log_message("对时成功", "SUCCESS")
            else:
                self._log_message("对时失败，请检查网络", "WARNING")
        except Exception as e:
            self._log_message(f"对时异常: {e}", "ERROR")

    def _use_local_clock(self):
        """切回本地时钟。"""
        try:
            self._ensure_playback_service()
            if not getattr(self, 'playback_service', None):
                self._log_message("播放服务不可用，无法切回本地时钟", "ERROR")
                return
            self.playback_service.use_local_clock()
            self._log_message("已切回本地时钟", "INFO")
        except Exception as e:
            self._log_message(f"切回本地时钟异常: {e}", "ERROR")

    def _ensemble_plan_start(self):
        """按计划延时开始当前选定的演奏（基于播放列表/MIDI路径）。"""
        try:
            delay_s = 0.0
            try:
                delay_s = float(self.ensemble_delay_var.get()) if hasattr(self, 'ensemble_delay_var') else 0.0
            except Exception:
                delay_s = 0.0
            delay_ms = max(0, int(delay_s * 1000))
            if delay_ms == 0:
                self._log_message("立即开始(计划延时为0)", "INFO")
                self._start_midi_play()
                return
            self._log_message(f"已计划在 {delay_s:.2f} 秒后开始", "INFO")
            if hasattr(self, 'root'):
                self.root.after(delay_ms, self._start_midi_play)
            else:
                # 兜底：阻塞式等待（不建议，但保持功能可用）
                try:
                    time.sleep(delay_s)
                except Exception:
                    pass
                self._start_midi_play()
        except Exception as e:
            self._log_message(f"计划开始失败: {e}", "ERROR")

    def _ensemble_unified_start(self):
        """统一开始：倒计时后开始播放。"""
        try:
            count = 3
            try:
                count = int(self.ensemble_countdown_var.get()) if hasattr(self, 'ensemble_countdown_var') else 3
            except Exception:
                count = 3

            def _tick(n: int):
                try:
                    if n <= 0:
                        self._log_message("开始！", "SUCCESS")
                        self._start_midi_play()
                        return
                    self._log_message(f"统一开始倒计时: {n}", "INFO")
                    if hasattr(self, 'root'):
                        self.root.after(1000, lambda: _tick(n - 1))
                    else:
                        time.sleep(1)
                        _tick(n - 1)
                except Exception:
                    self._start_midi_play()

            # 若勾选“使用右侧解析事件”，解析逻辑已在 _start_midi_play 内部进行匹配复用
            _tick(max(0, count))
        except Exception as e:
            self._log_message(f"统一开始失败: {e}", "ERROR")
    
    def _add_file_to_playlist(self, file_path, file_type):
        """添加文件到播放列表"""
        try:
            # 初始化路径字典
            if not hasattr(self, '_file_paths'):
                self._file_paths = {}
            # 绝对路径与去重
            abspath = os.path.abspath(file_path)
            if abspath in self._file_paths.values():
                return False
            # 添加到播放列表
            item_count = len(self.playlist_tree.get_children()) + 1
            file_name = os.path.basename(file_path)
            
            # 计算文件时长（这里简化处理）
            duration = "未知"
            if os.path.exists(file_path):
                try:
                    # 尝试获取文件时长
                    if file_path.lower().endswith('.mid') or file_path.lower().endswith('.midi'):
                        try:
                            import mido
                        except Exception:
                            mido = None
                        if mido is not None:
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
            self._file_paths[item_id] = abspath
            self._log_message(f"已添加到播放列表: {file_name}")
            # 同步到管理器
            try:
                if getattr(self, 'playlist', None):
                    self.playlist.add_files([abspath], ftype=file_type)
            except Exception:
                pass
            return True
        except Exception as e:
            self._log_message(f"添加文件到播放列表失败: {str(e)}", "ERROR")
            return False
    
    def _add_to_playlist(self):
        """添加文件到播放列表（支持多选）"""
        paths = filedialog.askopenfilenames(
            title="选择文件",
            filetypes=[
                ("MIDI文件", "*.mid;*.midi"),
                ("所有文件", "*.*")
            ]
        )
        added = 0
        for file_path in paths or []:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.mid', '.midi']:
                file_type = "MIDI文件"
            else:
                file_type = "未知类型"
            
            if self._add_file_to_playlist(file_path, file_type):
                added += 1
        if added:
            self._refresh_playlist_indices()
            self._log_message(f"已添加 {added} 个文件到播放列表", "SUCCESS")

    def _add_folder_to_playlist(self):
        """选择文件夹并批量添加其中的MIDI文件"""
        folder = filedialog.askdirectory(title="选择包含MIDI文件的文件夹")
        if not folder:
            return
        midi_paths = []
        try:
            for root, _, files in os.walk(folder):
                for name in files:
                    lower = name.lower()
                    if lower.endswith('.mid') or lower.endswith('.midi'):
                        midi_paths.append(os.path.join(root, name))
        except Exception as e:
            self._log_message(f"扫描文件夹失败: {str(e)}", "ERROR")
            return
        if not midi_paths:
            messagebox.showinfo("提示", "未发现MIDI文件 (*.mid, *.midi)")
            return
        added = 0
        for p in sorted(midi_paths):
            if self._add_file_to_playlist(p, "MIDI文件"):
                added += 1
        if added:
            self._refresh_playlist_indices()
            self._log_message(f"已从文件夹添加 {added} 个MIDI文件", "SUCCESS")
    
    def _remove_from_playlist(self):
        """从播放列表移除文件"""
        selected = self.playlist_tree.selection()
        if selected:
            # 计算被选中的索引并倒序删除
            all_items = list(self.playlist_tree.get_children())
            indices = sorted([all_items.index(i) for i in selected if i in all_items], reverse=True)
            for idx in indices:
                item = all_items[idx]
                item_data = self.playlist_tree.item(item)
                file_name = item_data['values'][1] if item_data['values'] else "未知文件"
                self.playlist_tree.delete(item)
                self._log_message(f"已从播放列表移除: {file_name}")
                # 同步移除路径映射
                try:
                    if hasattr(self, '_file_paths') and item in self._file_paths:
                        del self._file_paths[item]
                except Exception:
                    pass
            # 同步到管理器
            try:
                if getattr(self, 'playlist', None):
                    self.playlist.remove_by_indices(indices)
            except Exception:
                pass
            # 重新编号
            self._refresh_playlist_indices()
        else:
            messagebox.showwarning("提示", "请先选择要移除的项目")
    
    def _clear_playlist(self):
        """清空播放列表"""
        if messagebox.askyesno("确认", "确定要清空播放列表吗？"):
            self.playlist_tree.delete(*self.playlist_tree.get_children())
            self._log_message("播放列表已清空")
            if hasattr(self, '_file_paths'):
                self._file_paths.clear()
            self._refresh_playlist_indices()
            try:
                if getattr(self, 'playlist', None):
                    self.playlist.clear()
            except Exception:
                pass

    def _refresh_playlist_indices(self):
        """刷新播放列表序号列"""
        try:
            items = self.playlist_tree.get_children()
            for i, item in enumerate(items, 1):
                values = list(self.playlist_tree.item(item)['values'])
                if values:
                    values[0] = i
                    self.playlist_tree.item(item, values=values)
        except Exception:
            pass
    
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
        self._play_selected_playlist_item()

    # —— 播放列表辅助方法 ——
    def _get_selected_playlist_index(self) -> Optional[int]:
        try:
            selected = self.playlist_tree.selection()
            if not selected:
                return None
            all_items = list(self.playlist_tree.get_children())
            return all_items.index(selected[0]) if selected[0] in all_items else None
        except Exception:
            return None

    def _select_playlist_index(self, index: int) -> None:
        try:
            all_items = list(self.playlist_tree.get_children())
            if 0 <= index < len(all_items):
                self.playlist_tree.selection_set(all_items[index])
                self.playlist_tree.see(all_items[index])
        except Exception:
            pass

    # ===== 预处理移调工具 =====
    def _transpose_notes(self, notes, semitone):
        """返回移调后的新 notes 列表，并更新 group 字段"""
        try:
            out = []
            for n in notes:
                m = dict(n)
                pitch = int(m.get('note', 0))
                pitch = max(0, min(127, pitch + int(semitone)))
                m['note'] = pitch
                m['group'] = groups.group_for_note(pitch)
                out.append(m)
            return out
        except Exception:
            return notes

    def _white_key_ratio(self, notes):
        """计算给定 notes 的白键占比(按事件音符计算)"""
        try:
            white = {0,2,4,5,7,9,11}
            cnt = 0
            total = 0
            for n in notes:
                pitch = int(n.get('note', 0))
                total += 1
                if (pitch % 12) in white:
                    cnt += 1
            return (cnt / total) if total else 0.0
        except Exception:
            return 0.0

    def _auto_choose_best_transpose(self, notes):
        """在[-6,6]范围内选择白键占比最高的移调，返回(最佳半音, 最佳占比)并应用移调结果到 notes 副本"""
        best_s = 0
        best_r = -1.0
        best_notes = notes
        try:
            for s in range(-6, 7):
                cand = self._transpose_notes(notes, s)
                r = self._white_key_ratio(cand)
                # 选择占比最高；占比相同优先绝对值更小，再优先正向(>=0)
                better = False
                if r > best_r:
                    better = True
                elif abs(r - best_r) < 1e-9:
                    if abs(s) < abs(best_s) or (abs(s) == abs(best_s) and s >= 0 and best_s < 0):
                        better = True
                if better:
                    best_r = r
                    best_s = s
                    best_notes = cand
            # 应用最佳结果
            # 注意：调用方期望返回 notes 已移调的副本
            # 这里直接返回选择
            # 更新 self.analysis_notes 会在上层完成
            # 但为便捷，这里直接返回选择(半音, 占比)并让上层替换 notes
            # 因为我们在上层使用返回的 notes
            # 为保持接口一致，这里只返回半音和占比，上层据此重新设置 notes
            # 然而当前上层逻辑希望自动分支“不重复移调”，所以改为直接返回半音和占比，并让上层忽略
            # 为确保 notes 被替换，这里返回半音和占比，同时将 best_notes 赋值到一个属性供上层读取
            self._auto_transposed_notes_cache = best_notes
            return best_s, best_r
        except Exception:
            self._auto_transposed_notes_cache = notes
            return 0, self._white_key_ratio(notes)
    
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
            # 增强检查：确保log_text存在且未被销毁
            if hasattr(self, 'log_text') and self.log_text is not None:
                # 尝试检查组件有效性
                try:
                    # 尝试一个简单的操作来验证组件是否仍然有效
                    self.log_text.winfo_exists()
                except Exception:
                    # 组件已不可用，直接返回
                    return
                    
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
                
                # 嵌套try-except以避免单个操作失败影响整体
                try:
                    self.log_text.insert(tk.END, formatted_message)
                    self.log_text.see(tk.END)  # 滚动到最新内容
                except Exception:
                    pass

                # 若原神简洁页存在，镜像输出到其日志
                try:
                    if getattr(self, 'yuanshen_page', None) and hasattr(self.yuanshen_page, 'append_log'):
                        self.yuanshen_page.append_log(formatted_message)
                except Exception:
                    pass
                
                # 限制日志行数，避免内存占用过大
                try:
                    lines = self.log_text.get("1.0", tk.END).split('\n')
                    if len(lines) > 1000:
                        self.log_text.delete("1.0", "500.0")
                except Exception:
                    pass
        except Exception as e:
            # 避免在关闭过程中产生过多错误输出
            pass
    
    def _add_test_playlist_data(self):
        """添加测试数据到播放列表"""
        try:
            if hasattr(self, 'playlist_tree'):
                # 添加一些测试项目
                test_items = [
                    ("1", "测试MIDI文件.mid", "MIDI文件", "02:30", "未播放"),
                    ("2", "示例音频.mp3", "音频文件", "03:45", "未播放")
                ]
                
                for item in test_items:
                    self.playlist_tree.insert('', 'end', values=item)
                
                self._log_message("已添加测试数据到播放列表", "INFO")
        except Exception as e:
            self._log_message(f"添加测试数据失败: {e}", "ERROR")
    
    def _on_closing(self):
        """应用程序关闭事件"""
        try:
            # 启动保护：启动后短时间内忽略关闭请求（防止误触发）
            if getattr(self, '_startup_protect', False):
                return
            # 关闭确认
            try:
                if not getattr(self, '_allow_close', False):
                    if messagebox.askokcancel("退出", "确定要退出 MeowField AutoPiano 吗？") is False:
                        return
                    else:
                        # 用户确认后，允许关闭
                        self._allow_close = True
                else:
                    # 已被 Ctrl+Q 授权关闭
                    pass
            except Exception:
                pass
            # 发布系统关闭事件
            self.event_bus.publish(Events.SYSTEM_SHUTDOWN, {}, 'App')
            
            # 销毁窗口
            self.root.destroy()
            
        except Exception as e:
            print(f"关闭应用程序时发生错误: {e}")
            self.root.destroy()

    def _request_close(self):
        """通过快捷键授权关闭（Ctrl+Q）。"""
        try:
            print("[DEBUG] 收到 Ctrl+Q，授权关闭")
            self._allow_close = True
            # 主动触发协议处理
            self._on_closing()
        except Exception:
            pass

    def _on_root_destroy(self, event=None):
        """根窗口销毁事件（用于调试 mainloop 提前退出）"""
        try:
            # 仅在调试模式下输出信息（可选）
            # widget = event.widget if event is not None else None
            # is_root = (widget is self.root) if widget is not None else True
            # name = str(widget) if widget is not None else 'root'
            # print(f"[DEBUG] <Destroy> 捕获: widget={name}, is_root={is_root}")
            
            # 避免在窗口销毁过程中记录日志，防止产生过多输出
            pass
        except Exception:
            pass
    
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
