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

import ctypes

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

# 右侧面板入口已合并至左侧分页；保留占位以兼容旧代码，不再实际使用

try:

    from pages.components import right_pane as comp_right  # noqa: F401

except Exception:

    comp_right = None

from pages.components import bottom_progress as comp_bottom

# 新增：乐器板块页面 与 工具页面

try:

    from pages.instruments.epiano import EPianoPage  # type: ignore

    from pages.instruments.guitar import GuitarPage  # type: ignore

    from pages.instruments.bass import BassPage  # type: ignore

    from pages.instruments.drums_new import DrumsPage  # type: ignore

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

        # 检查管理员权限

        self._check_admin_privileges()

        
        
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

        # 尝试启用整窗毛玻璃（Acrylic）效果（Windows 10+）

        try:

            self._enable_acrylic()

        except Exception:

            pass
        
        
        
        # 设置窗口图标（如果存在）

        self._set_window_icon()

        
        
        # 初始化事件总线

        self.event_bus = event_bus

        
        
        # 初始化模块管理器

        self.module_manager = ModuleManager(self.event_bus)

        
        
        # 初始化UI管理器

        self.ui_manager = UIManager(self.root, self.event_bus)

        
        # 创建右侧播放列表侧栏
        self._create_playlist_sidebar()
        
        # 初始化共享变量（确保所有页面都能访问）
        self.midi_path_var = tk.StringVar(value="")
        self.tempo_var = tk.DoubleVar(value=1.0)
        self.volume_var = tk.DoubleVar(value=0.7)
        self.file_info_var = tk.StringVar(value="未选择文件")
        
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
                # 同步设置当前页面
                self.current_page = self.router._pages.get('inst:epiano')

            try:

                if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                    self.sidebar.set_active('inst-epiano')

            except Exception:

                pass

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

        # UI 调试输出开关（默认关闭，避免大量 [DEBUG] 噪声）

        self._ui_debug = False

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

        # 分组筛选复选框变量容器（兜底初始化，避免 AttributeError）

        try:

            if not hasattr(self, 'pitch_group_vars') or not isinstance(getattr(self, 'pitch_group_vars'), dict):

                self.pitch_group_vars = {}

        except Exception:

            self.pitch_group_vars = {}



    def _enable_acrylic(self):

        """启用整窗毛玻璃效果（Acrylic）。仅在 Windows 上有效，失败则静默忽略。"""

        try:

            import ctypes

            import platform

            if platform.system() != 'Windows':

                return

            user32 = ctypes.windll.user32

            hwnd = self.root.winfo_id()

            # 定义结构体

            class ACCENTPOLICY(ctypes.Structure):

                _fields_ = [("AccentState", ctypes.c_int),

                            ("AccentFlags", ctypes.c_int),

                            ("GradientColor", ctypes.c_uint32),

                            ("AnimationId", ctypes.c_int)]



            class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):

                _fields_ = [("Attribute", ctypes.c_int),

                            ("Data", ctypes.c_void_p),

                            ("SizeOfData", ctypes.c_size_t)]



            # 常量

            WCA_ACCENT_POLICY = 19

            ACCENT_ENABLE_ACRYLICBLURBEHIND = 4  # Acrylic（需要 Windows 10 RS4+）

            ACCENT_ENABLE_BLURBEHIND = 3



            # 颜色：0xAABBGGRR，使用 Win11 蓝白系的半透明白（略带蓝）

            # 例如 alpha=0xCC，颜色 #F8FAFF（接近白、偏蓝）：0xCCFFFAF8（注意顺序 BBGGRR）

            alpha = 0xCC

            bb = 0xFF  # B

            gg = 0xFA  # G

            rr = 0xF8  # R

            gradient_color = (alpha << 24) | (bb << 16) | (gg << 8) | rr



            accent = ACCENTPOLICY()

            accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND

            accent.AccentFlags = 0  # 可选：0x20 开启淡入淡出

            accent.GradientColor = ctypes.c_uint32(gradient_color)

            accent.AnimationId = 0



            data = WINDOWCOMPOSITIONATTRIBDATA()

            data.Attribute = WCA_ACCENT_POLICY

            data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)

            data.SizeOfData = ctypes.sizeof(accent)



            # 调用 API

            _SetWindowCompositionAttribute = ctypes.windll.user32.SetWindowCompositionAttribute

            _SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data))

        except Exception:

            # 回退：尝试普通模糊

            try:

                import ctypes

                class ACCENTPOLICY(ctypes.Structure):

                    _fields_ = [("AccentState", ctypes.c_int),

                                ("AccentFlags", ctypes.c_int),

                                ("GradientColor", ctypes.c_uint32),

                                ("AnimationId", ctypes.c_int)]

                class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):

                    _fields_ = [("Attribute", ctypes.c_int),

                                ("Data", ctypes.c_void_p),

                                ("SizeOfData", ctypes.c_size_t)]

                WCA_ACCENT_POLICY = 19

                ACCENT_ENABLE_BLURBEHIND = 3

                accent = ACCENTPOLICY()

                accent.AccentState = ACCENT_ENABLE_BLURBEHIND

                accent.AccentFlags = 0

                accent.GradientColor = 0

                accent.AnimationId = 0

                data = WINDOWCOMPOSITIONATTRIBDATA()

                data.Attribute = WCA_ACCENT_POLICY

                data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)

                data.SizeOfData = ctypes.sizeof(accent)

                hwnd = self.root.winfo_id()

                ctypes.windll.user32.SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data))

            except Exception:

                pass
    
    
    
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

            # 清理所有既有窗口级快捷键，避免与“仅保留 Ctrl+Shift+C”冲突

            try:

                for seq in ('<space>', '<Space>', '<Escape>', '<ESC>', '<Control-s>', '<Control-S>'):

                    try:

                        self.root.unbind_all(seq)

                    except Exception:

                        pass

            except Exception:

                pass

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

                        # 先清理所有已注册的全局热键，确保只保留我们需要的

                        try:

                            keyboard.clear_all_hotkeys()

                        except Exception:

                            pass

                        # 仅注册 Ctrl+Shift+C 用于停止所有播放

                        keyboard.add_hotkey('ctrl+shift+c', _hotkey_stop, suppress=False)

                    except Exception:

                        pass

                t = threading.Thread(target=_register_kb, daemon=True)

                t.start()

                self._log_message("全局热键已注册: Ctrl+Shift+C(停止所有播放)")

            except Exception:

                # 回退到窗口级绑定

                self.root.bind('<Control-Shift-C>', lambda e: (self._stop_auto_play(), self._stop_playback()))

                self._log_message("窗口热键已注册: Ctrl+Shift+C")
            
            
            
            self._log_message("热键绑定完成: 仅注册 Ctrl+Shift+C(停止所有播放)")

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

        """在 UIManager.left_sidebar_holder 中创建嵌入式侧边栏。"""

        try:

            self.sidebar_width_expanded = 200

            self.sidebar_width_collapsed = 40

            self.sidebar_current_width = self.sidebar_width_expanded

            # 启用外层壳层列宽动画，以获得平滑且现代的 UI 过渡

            self.sidebar_shrink_holder = True

            holder = getattr(self.ui_manager, 'left_sidebar_holder', None)

            if holder is None:

                # 兼容：若不存在 holder，则退回在 left_frame 左侧创建一个holder

                self.ui_manager.left_frame.pack_forget()

                shell = ttk.Frame(self.ui_manager.left_frame)

                shell.pack(fill=tk.BOTH, expand=True)

                holder = ttk.Frame(shell, width=self.sidebar_width_expanded)

                holder.pack(side=tk.LEFT, fill=tk.Y)

                self.ui_manager.left_content_frame = ttk.Frame(shell)

                self.ui_manager.left_content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            try:

                holder.pack_propagate(False)

            except Exception:

                pass

            # 初始化壳层列宽为展开宽度（通过 grid 列 minsize 控制）

            try:

                shell = getattr(self.ui_manager, 'left_shell', None)

                if shell is not None:

                    shell.grid_columnconfigure(0, minsize=self.sidebar_width_expanded)

            except Exception:

                pass

            # 在 holder 内创建侧边栏

            self.sidebar = Sidebar(

                holder,

                on_action=self._on_sidebar_action,

                width=self.sidebar_width_expanded,

                # 外层不缩放时，on_width 不触发外层宽度变化

                on_width=(lambda w: self._update_sidebar_width(w)) if self.sidebar_shrink_holder else (lambda w: None)

            )

            self.sidebar.attach(use_pack=True)

            # 设置初始宽度

            if self.sidebar_shrink_holder:

                self._update_sidebar_width(self.sidebar_width_expanded)

        except Exception as e:

            self._log_message(f"创建侧边栏失败: {e}", "ERROR")



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
                            # 同步设置当前页面
                            self.current_page = self.router._pages.get(cur)

                        else:

                            self.router.show('ensemble', title="合奏")
                            # 同步设置当前页面
                            self.current_page = self.router._pages.get('ensemble')

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
                        # 同步设置当前页面
                        self.current_page = self.router._pages.get('inst:epiano')

                    self.ui_manager.set_status('已切换至电子琴板块')

                    try:

                        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                            self.sidebar.set_active('inst-epiano')

                    except Exception:

                        pass

                except Exception:

                    pass

                return

            if key == 'inst-guitar':

                try:

                    self.current_instrument = '吉他'

                    title = f"{self.current_instrument}"

                    if getattr(self, 'router', None):

                        self.router.show('inst:guitar', title=title)
                        # 同步设置当前页面
                        self.current_page = self.router._pages.get('inst:guitar')

                    self.ui_manager.set_status('已切换至吉他板块')

                    try:

                        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                            self.sidebar.set_active('inst-guitar')

                    except Exception:

                        pass

                except Exception:

                    pass

                return

            if key == 'inst-bass':

                try:

                    self.current_instrument = '贝斯'

                    title = f"{self.current_instrument}"

                    if getattr(self, 'router', None):

                        self.router.show('inst:bass', title=title)
                        # 同步设置当前页面
                        self.current_page = self.router._pages.get('inst:bass')

                    self.ui_manager.set_status('已切换至贝斯板块（占位）')

                    try:

                        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                            self.sidebar.set_active('inst-bass')

                    except Exception:

                        pass

                except Exception:

                    pass

                return

            if key == 'inst-drums':

                try:

                    self.current_instrument = '架子鼓'

                    title = f"{self.current_instrument}"

                    if getattr(self, 'router', None):

                        self.router.show('inst:drums', title=title)
                        # 同步设置当前页面
                        self.current_page = self.router._pages.get('inst:drums')

                    self.ui_manager.set_status('已切换至架子鼓板块')

                    try:

                        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                            self.sidebar.set_active('inst-drums')

                    except Exception:

                        pass

                except Exception:

                    pass

                return

            if key == 'tool-audio2midi':

                try:

                    if getattr(self, 'router', None):

                        self.router.show('tool:audio2midi', title="音频转MIDI")
                        # 同步设置当前页面
                        self.current_page = self.router._pages.get('tool:audio2midi')

                    self.ui_manager.set_status('已切换至 音频转MIDI 工具')

                    try:

                        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):

                            self.sidebar.set_active('tool-audio2midi')

                    except Exception:

                        pass

                except Exception:

                    pass

                return

        except Exception:

            pass



    def _ui_parts_auto_select_by_channel(self):

        """仅根据通道自动勾选：

        - 若 MIDI 为单轨道：全选

        - 架子鼓：选择 channel==9 的分部

        - 其他乐器：优先按 GM Program 家族（若有）筛选；否则选择 channel!=9 的分部

        - 若无匹配：全选

        """

        try:

            tree = getattr(self, '_parts_tree', None)

            if tree is None:

                return

            midi_path = getattr(self, 'midi_path_var', None).get() if hasattr(self, 'midi_path_var') else ''

            single_track = False

            try:

                if midi_path and os.path.exists(midi_path):

                    res = analyzer.parse_midi(midi_path)

                    if res.get('ok') and isinstance(res.get('tracks'), list):

                        single_track = (len(res.get('tracks') or []) <= 1)

            except Exception:

                single_track = False

            if single_track:

                self._ui_parts_select_all()

                return

            # 遍历 tree，根据 _last_split_parts 的 meta.channel 进行匹配

            parts = getattr(self, '_last_split_parts', {}) or {}

            selected = 0

            self._parts_checked = {}



            # GM Program 家族范围（0-based）：

            # 参考：https://www.midi.org/specifications-old/item/gm-level-1-sound-set

            gm_families = {

                'piano': list(range(0, 8)),          # Acoustic/Electric Pianos 0-7

                'guitar': list(range(24, 32)),       # 24-31

                'bass': list(range(32, 40)),         # 32-39

                'strings': list(range(40, 48)),      # 40-47

            }

            inst = getattr(self, 'current_instrument', '')

            prefer_programs = None

            if inst == '电子琴':

                prefer_programs = set(gm_families['piano'])

            elif inst == '吉他':

                prefer_programs = set(gm_families['guitar'])

            elif inst == '贝斯':

                prefer_programs = set(gm_families['bass'])

            else:

                prefer_programs = None



            for iid in tree.get_children():

                # 读取分部名称与元信息

                vals = list(tree.item(iid, 'values'))

                if not vals or len(vals) < 2:

                    continue

                name = vals[1]

                sec = parts.get(name)

                chan = None

                program = None

                notes = []

                try:

                    if isinstance(sec, dict):

                        meta = sec.get('meta', {}) or {}

                        chan = meta.get('channel', None)

                        program = meta.get('program', None)

                        notes = sec.get('notes', [])

                    else:

                        meta = getattr(sec, 'meta', {}) or {}

                        chan = meta.get('channel', None)

                        program = meta.get('program', None)

                        notes = getattr(sec, 'notes', []) or []

                except Exception:

                    pass

                # 缺失时从事件推断主通道/主Program

                if (chan is None or program is None) and notes:

                    try:

                        from collections import Counter

                        chs = [int(ev.get('channel')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('channel') is not None]

                        progs = [int(ev.get('program')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('program') is not None]

                        if chan is None and chs:

                            chan = Counter(chs).most_common(1)[0][0]

                        if program is None and progs:

                            program = Counter(progs).most_common(1)[0][0]

                    except Exception:

                        pass

                # 命中判断

                hit = False

                if chan is not None:

                    if inst == '架子鼓':

                        hit = (int(chan) == 9)

                    else:

                        if prefer_programs is not None and program is not None:

                            try:

                                hit = (int(chan) != 9) and (int(program) in prefer_programs)

                            except Exception:

                                hit = (int(chan) != 9)

                        else:

                            hit = (int(chan) != 9)

                # 应用到 Tree 与缓存

                self._parts_checked[name] = bool(hit)

                vals[0] = '☑' if hit else '☐'

                tree.item(iid, values=vals)

                if hit:

                    selected += 1

            if selected == 0:

                # 无匹配则全选

                self._ui_parts_select_all()

        except Exception:

            # 异常兜底：全选

            try:

                self._ui_parts_select_all()

            except Exception:

                pass



    def _ui_parts_auto_select_by_instrument_cluster(self) -> bool:

        """在“智能聚类”模式下，仅选择与当前乐器匹配的分部。

        返回是否至少命中一个分部。规则：

        - 架子鼓：channel==9

        - 电子琴：program in 0..7（Acoustic/Electric Pianos）

        - 吉他：program in 24..31

        - 贝斯：program in 32..39

        其余：默认选择非鼓通道。

        若未命中则返回 False，由调用方回退通道逻辑。

        """

        try:

            tree = getattr(self, '_parts_tree', None)

            parts = getattr(self, '_last_split_parts', {}) or {}

            if tree is None or not parts:

                return False

            inst = str(getattr(self, 'current_instrument', '') or '')

            selected = 0

            self._parts_checked = {}

            # 定义家族

            fam = {

                '电子琴': set(range(0, 8)),

                '吉他': set(range(24, 32)),

                '贝斯': set(range(32, 40)),

            }

            for iid in tree.get_children():

                vals = list(tree.item(iid, 'values'))

                if not vals or len(vals) < 2:

                    continue

                name = vals[1]

                sec = parts.get(name)

                chan = None

                prog = None

                notes = []

                try:

                    if isinstance(sec, dict):

                        meta = sec.get('meta', {}) or {}

                        chan = meta.get('channel')

                        prog = meta.get('program')

                        notes = sec.get('notes', [])

                    else:

                        meta = getattr(sec, 'meta', {}) or {}

                        chan = meta.get('channel')

                        prog = meta.get('program')

                        notes = getattr(sec, 'notes', []) or []

                except Exception:

                    pass

                # 若元数据缺失则从事件推断主通道与主 Program

                if (chan is None or prog is None) and notes:

                    try:

                        from collections import Counter

                        chs = [int(ev.get('channel')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('channel') is not None]

                        progs = [int(ev.get('program')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('program') is not None]

                        if chan is None:

                            chan = Counter(chs).most_common(1)[0][0] if chs else None

                        if prog is None:

                            prog = Counter(progs).most_common(1)[0][0] if progs else None

                    except Exception:

                        pass

                hit = False

                if inst == '架子鼓':

                    hit = (chan is not None and int(chan) == 9)

                elif inst in ('电子琴','吉他','贝斯'):

                    if prog is not None and isinstance(prog, (int, float)):

                        try:

                            hit = (int(chan) != 9) and (int(prog) in fam[inst])

                        except Exception:

                            hit = False

                    else:

                        hit = False

                else:

                    # 其他未知乐器：默认非鼓

                    hit = (chan is not None and int(chan) != 9)

                self._parts_checked[name] = bool(hit)

                vals[0] = '☑' if hit else '☐'

                tree.item(iid, values=vals)

                if hit:

                    selected += 1

            if selected == 0:

                return False

            return True

        except Exception:

            return False





    def _on_root_unmap(self, event=None):

        return



    def _on_root_map(self, event=None):

        return



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



    def _create_playback_control_component(self, parent_left=None, include_ensemble: bool = True, instrument: str | None = None):

        """创建播放控制组件（委托组件模块）"""

        try:

            target = parent_left if parent_left is not None else self.ui_manager.left_frame

            comp_playback.create_playback_controls(self, target, include_ensemble=include_ensemble, instrument=instrument)

        except Exception as e:

            self.event_bus.publish(Events.SYSTEM_ERROR, {'message': f'创建播放控制组件失败: {e}'}, 'App')



    def _create_playlist_sidebar(self):
        """创建右侧播放列表侧栏"""
        try:
            from pages.components.playlist_sidebar import create_playlist_sidebar
            
            # 在UIManager的页面容器中添加右侧播放列表
            if hasattr(self.ui_manager, 'page_container'):
                # 创建右侧播放列表容器
                self.right_frame = ttk.Frame(self.ui_manager.page_container)
                self.right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(10, 0))
                
                # 创建播放列表侧栏
                create_playlist_sidebar(self, self.right_frame)
                
                self._log_message("右侧播放列表侧栏创建成功", "INFO")
            else:
                self._log_message("无法创建播放列表侧栏：页面容器不存在", "ERROR")
        except Exception as e:
            self._log_message(f"创建播放列表侧栏失败: {e}", "ERROR")

    def _create_right_pane(self, parent_right=None, *, show_midi_parse: bool = True, show_events: bool = True, show_logs: bool = True):

        """右侧入口已移除：不再创建右侧解析面板（改为左侧分页）。"""

        return





    def _create_auto_play_controls(self, parent):

        """在播放控制区域创建“自动弹琴/暂停”按钮。

        该方法由 `pages/components/playback_controls.py` 调用。

        """

        try:

            # 行容器

            row = ttk.Frame(parent)

            row.pack(side=tk.TOP, anchor=tk.W, pady=(0, 6))



            # 开始演奏按钮（开始/停止由内部逻辑切换文案）
            self.auto_play_button = ttk.Button(row, text="开始演奏", command=self._start_auto_play)
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

            # 检查是否在倒计时期间
            if hasattr(self, '_countdown_after_id') and self._countdown_after_id:
                # 取消倒计时
                self.root.after_cancel(self._countdown_after_id)
                self._countdown_after_id = None
                try:
                    if hasattr(self, 'countdown_label'):
                        self.countdown_label.configure(text="")
                    if hasattr(self, 'auto_play_button'):
                        self.auto_play_button.configure(state=tk.NORMAL)
                    if hasattr(self, 'pause_button'):
                        self.pause_button.configure(state=tk.DISABLED)
                except Exception:
                    pass
                self._log_message("倒计时已取消")
                return
            
            # 正常暂停/恢复逻辑
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

            # 应用分部过滤（若已识别分部且存在选择），使右侧解析与事件表与播放保持一致

            try:

                parts = getattr(self, '_last_split_parts', {}) or {}

                sels = list(getattr(self, '_selected_part_names', set()) or [])

                if parts and sels and getattr(self, 'playback_service', None):

                    ps = self.playback_service

                    # 下发选择条件

                    if hasattr(ps, 'set_selected_parts_filter'):

                        ps.set_selected_parts_filter(parts, sels)

                    # 应用过滤（服务内部带有分层匹配与鼓保护、并输出诊断日志）

                    try:

                        filt = ps._apply_parts_filter(notes) if hasattr(ps, '_apply_parts_filter') else None

                    except Exception:

                        filt = None

                    if isinstance(filt, list) and filt:

                        self._log_message(f"[DEBUG] 分部过滤生效于解析: 输入={len(notes)} 输出={len(filt)}", "DEBUG")

                        notes = filt

                    else:

                        # 若过滤为空，保留原始以避免界面空表，但给出提示

                        try:

                            self._log_message("[DEBUG] 分部过滤为空，解析界面回退为全曲事件", "WARN")

                        except Exception:

                            pass

                else:

                    # 无分部或未选择：记录全量

                    self._log_message(f"使用pretty_midi完整解析: {len(notes)} 个音符")

            except Exception:

                self._log_message(f"使用pretty_midi完整解析: {len(notes)} 个音符")

            # 预处理：整曲移调（手动优先；否则自动；否则按手动值）

            if bool(getattr(self, 'enable_preproc_var', tk.BooleanVar(value=False)).get()) and notes:

                try:

                    # 确保 UI 变量存在

                    if not hasattr(self, 'pretranspose_semitones_var'):

                        self.pretranspose_semitones_var = tk.IntVar(value=0)

                    if not hasattr(self, 'pretranspose_white_ratio_var'):

                        self.pretranspose_white_ratio_var = tk.StringVar(value="-")

                    manual_val = 0

                    try:

                        manual_val = int(self.pretranspose_semitones_var.get())

                    except Exception:

                        manual_val = 0

                    auto_enabled = bool(getattr(self, 'pretranspose_auto_var', tk.BooleanVar(value=True)).get())



                    if manual_val != 0:

                        # 手动半音优先（即使自动开启）

                        chosen = manual_val

                        notes = self._transpose_notes(notes, chosen)

                        ratio = self._white_key_ratio(notes)

                        self.pretranspose_white_ratio_var.set(f"{ratio*100:.1f}%")

                        self._log_message(f"预处理移调(手动优先): {chosen} 半音 | 白键占比: {ratio*100:.1f}%")

                    elif auto_enabled:

                        # 自动选择

                        chosen, best_ratio = self._auto_choose_best_transpose(notes)

                        auto_notes = getattr(self, '_auto_transposed_notes_cache', None)

                        notes = auto_notes if auto_notes else self._transpose_notes(notes, chosen)

                        self.pretranspose_semitones_var.set(chosen)

                        self.pretranspose_white_ratio_var.set(f"{best_ratio*100:.1f}%")

                        self._log_message(f"预处理移调(自动): {chosen} 半音 | 白键占比: {best_ratio*100:.1f}%")

                    else:

                        # 手动值（可能为0）

                        chosen = manual_val

                        notes = self._transpose_notes(notes, chosen)

                        ratio = self._white_key_ratio(notes)

                        self.pretranspose_white_ratio_var.set(f"{ratio*100:.1f}%")

                        self._log_message(f"预处理移调(手动): {chosen} 半音 | 白键占比: {ratio*100:.1f}%")

                except Exception as exp:

                    self._log_message(f"预处理移调失败: {exp}", "WARNING")



            # 预处理：最短音长过滤（仅非架子鼓；在整曲移调之后、其他解析前）

            try:

                if (getattr(self, 'current_instrument', '') != '架子鼓') and notes:

                    # 确保正确获取UI设置的短音过滤阈值

                    if hasattr(self, 'min_note_duration_ms_var') and self.min_note_duration_ms_var is not None:

                        try:

                            min_ms = int(self.min_note_duration_ms_var.get())

                        except Exception:

                            min_ms = 0

                    else:

                        min_ms = 0

                    self._log_message(f"短音过滤阈值: {min_ms}ms (乐器: {getattr(self, 'current_instrument', '')})", "INFO")

                    if min_ms > 0:

                        thr = max(0, min_ms) / 1000.0

                        before_cnt = len(notes)

                        filtered = []

                        dropped = 0

                        
                        
                        # 添加音符时长分析

                        durations = []

                        for n in notes[:10]:  # 分析前10个音符的时长

                            try:

                                dur = float(n.get('duration', 0.0))

                                if dur <= 0:

                                    start_time = float(n.get('start_time', 0.0))

                                    end_time = float(n.get('end_time', start_time))

                                    dur = max(0.0, end_time - start_time)

                                durations.append(dur * 1000)  # 转换为毫秒

                            except Exception:

                                pass
                        
                        
                        
                        if durations:

                            avg_dur = sum(durations) / len(durations)

                            min_dur = min(durations)

                            max_dur = max(durations)

                            self._log_message(f"[DEBUG] 音符时长分析: 平均{avg_dur:.1f}ms, 最短{min_dur:.1f}ms, 最长{max_dur:.1f}ms, 阈值{min_ms}ms", "DEBUG")
                        
                        
                        
                        for n in notes:

                            try:

                                # pretty_midi直接提供准确的duration字段（秒）

                                dur = float(n.get('duration', 0.0))

                                if dur <= 0:

                                    # 如果duration字段无效，尝试计算

                                    start_time = float(n.get('start_time', 0.0))

                                    end_time = float(n.get('end_time', start_time))

                                    dur = max(0.0, end_time - start_time)
                                
                                
                                
                                if dur >= thr:

                                    filtered.append(n)

                                else:

                                    dropped += 1

                            except Exception:

                                # 异常情况下保留

                                filtered.append(n)

                                continue

                        notes = filtered

                        self._log_message(f"最短音长过滤: 丢弃 {dropped} / {before_cnt} (<{min_ms}ms), 剩余 {len(notes)} 个音符")

                        # 自验证：检查是否仍存在小于阈值的音符

                        try:

                            remain_viol = 0

                            samples = 0

                            for n in notes:

                                try:

                                    # 使用pretty_midi的准确duration字段验证

                                    dur = float(n.get('duration', 0.0))

                                    if dur <= 0:

                                        start_time = float(n.get('start_time', 0.0))

                                        end_time = float(n.get('end_time', start_time))

                                        dur = max(0.0, end_time - start_time)
                                    
                                    
                                    
                                    if dur < thr:

                                        remain_viol += 1

                                        if samples < 3:

                                            self._log_message(f"[验证] 仍存在短音符: note={n.get('note')} dur={dur*1000:.1f}ms < {min_ms}ms", "WARNING")

                                            samples += 1

                                except Exception:

                                    pass
                            
                            
                            
                            if remain_viol > 0:

                                self._log_message(f"[验证] 过滤后仍检测到 {remain_viol} 条短音 (<{min_ms}ms)", "WARNING")

                            else:

                                self._log_message(f"[验证] 过滤校验通过：未发现 <{min_ms}ms 的音符", "INFO")

                        except Exception:

                            pass

            except Exception as exp:

                self._log_message(f"最短音长过滤失败: {exp}", "WARNING")



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

            self._log_message(f"[DEBUG] 保存解析结果: analysis_notes={len(self.analysis_notes)}, analysis_file={self.analysis_file}", "DEBUG")

            self._populate_event_table()

            self._log_message(

                f"MIDI解析完成: {len(notes)} 条音符；分组筛选: {len(selected)} 组；主旋律提取: {'开启' if self.enable_melody_extract_var.get() else '关闭'}")

        except Exception as e:

            self._log_message(f"MIDI解析异常: {e}", "ERROR")

            # 确保异常时也清空解析结果

            self.analysis_notes = []

            self.analysis_file = ""

            self._log_message(f"[DEBUG] 异常后清空解析结果: analysis_notes={len(self.analysis_notes)}", "DEBUG")



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
            # 统计超限音符数量
            out_of_range_count = 0
            # 获取是否仅显示超限音符的开关状态，默认为True
            show_only_out_of_range = getattr(self, 'show_only_out_of_range_var', tk.BooleanVar(value=True)).get()

            for n in sorted(notes, key=lambda x: (x.get('start_time', 0.0), x.get('note', 0))):

                st = round(float(n.get('start_time', 0.0)), 3)

                et = round(float(n.get('end_time', n.get('start_time', 0.0))), 3)

                dur = round(max(0.0, et - st), 3)

                ch = n.get('channel', 0)

                note = n.get('note', 0)
                # 检查是否为超限音符（<48 或 >83）
                is_out_of_range = note < 48 or note > 83
                if is_out_of_range:
                    out_of_range_count += 1
                
                # 根据开关状态决定是否添加此行
                if show_only_out_of_range and not is_out_of_range:
                    continue

                grp = n.get('group', groups.group_for_note(note))

                chord_col = ''

                if n.get('is_chord'):

                    chord_col = f"{int(n.get('chord_size', 0))}声部"

                # 在 note_on 行展示结束时间与时长；note_off 行仅展示结束时间

                rows.append((seq, st, 'note_on', note, ch, grp, et, dur, chord_col, is_out_of_range))

                seq += 1

                rows.append((seq, et, 'note_off', note, ch, grp, et, '', '', is_out_of_range))

                seq += 1

            # 尝试获取warning样式
            warning_style = None
            try:
                from pages.components.playback_controls import _init_button_styles
                styles = _init_button_styles(getattr(self, 'root', None))
                warning_style = styles['warning']
            except Exception:
                pass

            for r in rows:
                # 获取行数据（移除最后一个元素is_out_of_range）
                row_data = r[:-1]
                # 获取是否超限标记
                is_out_of_range = r[-1]
                # 插入行
                item_id = self.event_tree.insert('', tk.END, values=row_data)
                # 如果是超限音符，尝试应用warning样式
                if is_out_of_range:
                    try:
                        # 使用Treeview的tag功能
                        self.event_tree.item(item_id, tags=('warning',))
                    except:
                        pass

            # 更新超限音符数量显示
            try:
                # 尝试直接通过self访问变量
                self.out_of_range_count_var.set(f"超限音符数量：{out_of_range_count}")
            except (AttributeError, tk.TclError):
                # 如果失败，尝试通过ui_manager访问
                try:
                    if hasattr(self, 'ui_manager') and hasattr(self.ui_manager, 'out_of_range_count_var'):
                        self.ui_manager.out_of_range_count_var.set(f"超限音符数量：{out_of_range_count}")
                except:
                    # 如果所有方法都失败，记录错误但继续执行
                    self._log_message("更新超限音符数量显示失败", "DEBUG")

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

            # 调试输出：捕获到 SYSTEM_SHUTDOWN 事件

            print("[DEBUG] 收到 SYSTEM_SHUTDOWN 事件，准备调用 root.quit()")

            try:

                self._log_message("收到 SYSTEM_SHUTDOWN 事件", "INFO")

            except Exception:

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

            # 自动解析分部（除了架子鼓）

            if getattr(self, 'current_instrument', '') != '架子鼓':

                try:

                    self._log_message("正在自动解析分部...", "INFO")

                    # 自动识别分部（内部将基于当前拆分模式与乐器进行自动勾选）

                    self._ui_select_partitions()

                    # 若无任何被勾选的分部，兜底为全选后继续

                    try:

                        sels = self._get_parts_checked_names()

                    except Exception:

                        sels = []

                    if not sels:

                        self._log_message("未检测到已勾选分部，兜底为全选", "WARNING")

                        self._ui_parts_select_all()

                    # 自动应用解析设置

                    self._ui_apply_selected_parts_and_analyze()

                    # 记录解析文件

                    try:

                        self.analysis_file = file_path

                    except Exception:

                        pass

                    self._log_message("自动解析完成，已应用所选分部", "SUCCESS")

                    self.ui_manager.set_status("已自动解析并应用设置")

                except Exception as e:

                    self._log_message(f"自动解析失败: {e}", "ERROR")

                    # 失败时回退到手动模式

                    try:

                        self._ui_select_partitions()

                        self.ui_manager.set_status("自动解析失败，请手动选择分部后解析")

                    except Exception:

                        pass

            else:

                self._log_message("架子鼓模式：无需解析，可直接播放", "INFO")

                self.ui_manager.set_status("架子鼓模式：可直接播放")
    
    
    
    def _convert_mp3_to_midi(self):

        """转换音频到MIDI"""

        audio_path = self.mp3_path_var.get()

        if not audio_path:

            messagebox.showerror("错误", "请先选择音频文件")

            return
        
        
        
        if not os.path.exists(audio_path):

            messagebox.showerror("错误", "音频文件不存在")

            return
        
        
        
        # 防并发

        if getattr(self, '_audio_convert_running', False):

            messagebox.showwarning("提示", "正在转换中，请稍候...")

            return

        self._audio_convert_running = True

        self._log_message("开始转换音频到MIDI...")

        try:

            self.ui_manager.set_status("正在转换...")

        except Exception:

            pass



        def _worker():

            try:

                # 统一入口：调用 meowauto.audio.audio2midi.convert_audio_to_midi

                try:

                    from meowauto.audio.audio2midi import convert_audio_to_midi

                except Exception as e:

                    def _import_err():

                        self._log_message("音频转换入口不可用", "ERROR")

                        messagebox.showerror("错误", f"音频转换入口不可用：{e}")

                        try:

                            self.ui_manager.set_status("音频转换失败")

                        except Exception:

                            pass

                        self._audio_convert_running = False

                    self.root.after(0, _import_err)

                    return



                ok, out_path, err_msg, logs = convert_audio_to_midi(audio_path, None, pianotrans_dir="PianoTrans-v1.0")



                # 记录日志

                try:

                    if logs.get('stdout'):

                        self._log_message(f"PianoTrans输出: {logs['stdout']}", "INFO")

                    if logs.get('stderr'):

                        self._log_message(f"PianoTrans错误: {logs['stderr']}", "ERROR")

                    if logs.get('elapsed'):

                        self._log_message(f"转换耗时: {logs['elapsed']:.1f}s", "INFO")

                except Exception:

                    pass



                def _finish():

                    try:

                        if ok and out_path and os.path.exists(out_path):

                            self._log_message(f"音频转换成功: {out_path}", "SUCCESS")

                            try:

                                self.ui_manager.set_status("音频转换完成")

                            except Exception:

                                pass

                            messagebox.showinfo("成功", f"音频文件已转换为MIDI格式\n保存位置: {out_path}")

                            try:

                                self._add_file_to_playlist(out_path, "MIDI文件")

                            except Exception:

                                pass

                        else:

                            em = err_msg or "转换失败"

                            self._log_message(f"音频转换失败: {em}", "ERROR")

                            try:

                                self.ui_manager.set_status("音频转换失败")

                            except Exception:

                                pass

                            messagebox.showerror("错误", f"音频转换失败：{em}\n请检查文件与模型")

                    finally:

                        self._audio_convert_running = False



                self.root.after(0, _finish)

            except Exception as e:

                def _fail():

                    self._log_message(f"音频转换异常: {e}", "ERROR")

                    try:

                        self.ui_manager.set_status("音频转换失败")

                    except Exception:

                        pass

                    messagebox.showerror("错误", f"音频转换过程中发生错误:\n{e}")

                    self._audio_convert_running = False

                self.root.after(0, _fail)



        import threading

        threading.Thread(target=_worker, daemon=True).start()
    
    
    
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

    def _select_all_partitions(self):

        """默认全选所有分部"""

        try:

            # 使用正确的全选方法

            self._ui_parts_select_all()

        except Exception as e:

            self._log_message(f"全选分部失败: {e}", "ERROR")
    
    
    
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

            # 根据拆分模式选择策略（默认：仅通道）

            split_mode = '仅通道'

            try:

                if hasattr(self, 'partition_split_mode_var'):

                    split_mode = str(self.partition_split_mode_var.get()) or '仅通道'

            except Exception:

                split_mode = '仅通道'

            parts = None

            if split_mode == '仅通道':

                # 直接按轨/通道拆分

                parts = TrackChannelPartitioner(include_meta=True).split(events)

            else:  # 智能聚类

                parts = CombinedInstrumentPartitioner().split(events)

                if not parts:

                    parts = TrackChannelPartitioner(include_meta=True).split(events)

            if not parts:

                messagebox.showwarning("提示", "未能识别到可用分部")

                return

            self._last_split_parts = parts

            # 若 Treeview 尚未创建，执行“无界面自动勾选”：仅更新 _parts_checked，待 Treeview 创建后由 _populate_parts_tree 渲染

            tree_exists = bool(getattr(self, '_parts_tree', None))

            if not tree_exists:

                try:

                    self._parts_checked = {}

                    inst = str(getattr(self, 'current_instrument', '') or '')

                    from collections import Counter

                    # 定义 GM 家族

                    fam = {

                        '电子琴': set(range(0, 8)),

                        '吉他': set(range(24, 32)),

                        '贝斯': set(range(32, 40)),

                    }

                    selected = 0

                    for name, sec in parts.items():

                        # 读取 meta 与 notes

                        try:

                            if isinstance(sec, dict):

                                meta = sec.get('meta', {}) or {}

                                chan = meta.get('channel')

                                prog = meta.get('program')

                                notes = sec.get('notes', []) or []

                            else:

                                meta = getattr(sec, 'meta', {}) or {}

                                chan = meta.get('channel')

                                prog = meta.get('program')

                                notes = getattr(sec, 'notes', []) or []

                        except Exception:

                            chan = None; prog = None; notes = []

                        # 缺失时，从事件推断主通道/主 Program

                        if (chan is None or prog is None) and notes:

                            try:

                                chs = [int(ev.get('channel')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('channel') is not None]

                                progs = [int(ev.get('program')) for ev in notes if isinstance(ev, dict) and ev.get('type') in ('note_on','note_off') and ev.get('program') is not None]

                                if chan is None and chs:

                                    chan = Counter(chs).most_common(1)[0][0]

                                if prog is None and progs:

                                    prog = Counter(progs).most_common(1)[0][0]

                            except Exception:

                                pass

                        hit = False

                        if split_mode == '智能聚类':

                            if inst == '架子鼓':

                                hit = (chan is not None and int(chan) == 9)

                            elif inst in ('电子琴','吉他','贝斯'):

                                famset = fam.get(inst)

                                if prog is not None and isinstance(prog, (int, float)):

                                    try:

                                        hit = (int(chan) != 9) and (int(prog) in famset)

                                    except Exception:

                                        hit = False

                                else:

                                    hit = False

                            else:

                                hit = (chan is not None and int(chan) != 9)

                        else:

                            # 仅通道模式：优先家族，退化为“非鼓”

                            if inst == '架子鼓':

                                hit = (chan is not None and int(chan) == 9)

                            else:

                                prefer = None

                                if inst == '电子琴':

                                    prefer = fam['电子琴']

                                elif inst == '吉他':

                                    prefer = fam['吉他']

                                elif inst == '贝斯':

                                    prefer = fam['贝斯']

                                if prefer is not None and prog is not None:

                                    try:

                                        hit = (int(chan) != 9) and (int(prog) in prefer)

                                    except Exception:

                                        hit = (int(chan) != 9)

                                else:

                                    hit = (chan is not None and int(chan) != 9)

                        self._parts_checked[name] = bool(hit)

                        if hit:

                            selected += 1

                    if selected == 0:

                        # 无匹配：全选

                        for name in parts.keys():

                            self._parts_checked[name] = True

                        try:

                            self._log_message("[DEBUG] Headless 自动勾选兜底为全选", "DEBUG")

                        except Exception:

                            pass

                except Exception:

                    # 异常兜底：全选

                    self._parts_checked = {name: True for name in parts.keys()}

                # 无 Tree 时只更新状态与日志

                self._log_message("分部识别完成：已根据乐器在后台完成自动勾选（等待界面渲染）")

            else:

                # 填充左侧 Treeview 并执行可视化自动勾选

                self._populate_parts_tree(parts)

                if split_mode == '智能聚类':

                    matched = self._ui_parts_auto_select_by_instrument_cluster()

                    if not matched:

                        self._ui_parts_auto_select_by_channel()

                else:

                    self._ui_parts_auto_select_by_channel()

            self._log_message("分部识别完成：请在左侧勾选需要的分部，然后点击‘应用所选分部并解析’。")

        except Exception as e:

            # 失败：记录错误并尽量不选中任何分部，避免误触发

            try:

                self._ui_parts_select_none()

            except Exception:

                pass

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

                tempo=float(getattr(self, 'tempo_var', tk.DoubleVar(value=1.0)).get()),

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
            first_file = None

            for root, _, files in os.walk(folder):

                for name in files:

                    if os.path.splitext(name)[1].lower() in exts:

                        p = os.path.join(root, name)

                        if self.playlist and self.playlist.add_item(p):

                            self._append_playlist_tree_row(p)
                            
                            # 记录第一个文件用于自动加载
                            if first_file is None:
                                first_file = p

            # 自动加载第一个文件到主页面
            if first_file:
                # 检查当前页面是否为架子鼓页面
                current_page = getattr(self, 'current_page', None)
                if current_page and hasattr(current_page, '_load_midi_from_playlist'):
                    # 架子鼓页面：使用架子鼓专属的加载方法
                    success = current_page._load_midi_from_playlist(first_file)
                    if success:
                        self._log_message(f"已加载文件夹中的第一个文件到架子鼓页面: {os.path.basename(first_file)}", "SUCCESS")
                    else:
                        self._log_message("加载文件到架子鼓页面失败", "ERROR")
                else:
                    # 其他页面：使用通用的加载方法
                    # self.playback_mode.set("midi")  # 变量不存在，已注释
                    self.midi_path_var.set(first_file)
                    
                    # 更新文件信息显示
                    if hasattr(self, '_update_file_info_display'):
                        self._update_file_info_display(first_file)
                    
                    # 解析MIDI文件
                    try:
                        self._analyze_current_midi()
                        self._log_message(f"已加载文件夹中的第一个文件到主页面: {os.path.basename(first_file)}", "SUCCESS")
                    except Exception as e:
                        self._log_message(f"解析失败: {e}", "ERROR")

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

            
            # 插入树项并获取item_id
            item_id = self.playlist_tree.insert('', 'end', values=values)
            
            # 将完整文件路径存储到字典中
            if not hasattr(self, '_file_paths'):
                self._file_paths = {}
            self._file_paths[item_id] = os.path.abspath(file_path)
        except Exception:

            pass



    def _rebuild_playlist_tree(self):

        try:

            if not hasattr(self, 'playlist_tree') or not self.playlist:

                return

            for iid in self.playlist_tree.get_children():

                self.playlist_tree.delete(iid)

            
            # 重新初始化文件路径字典
            if not hasattr(self, '_file_paths'):
                self._file_paths = {}
            self._file_paths.clear()
            
            for i, it in enumerate(self.playlist.playlist_items, start=1):

                item_id = self.playlist_tree.insert('', 'end', values=(i, it.get('name'), it.get('type'), it.get('duration'), it.get('status')))
                # 存储完整文件路径
                self._file_paths[item_id] = os.path.abspath(it.get('path', ''))
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

            # 直接走统一入口，保证触发解析与预处理

            self._play_selected_playlist_item()

        except Exception as e:

            self._log_message(f"播放选中失败: {e}", "ERROR")



    def _play_next_from_playlist(self):

        try:

            if not self.playlist:

                return

            next_item = self.playlist.play_next()

            if next_item and next_item.get('path'):

                # 同步UI选中到当前索引并走统一入口

                try:

                    self._rebuild_playlist_tree()

                except Exception:

                    pass

                try:

                    if hasattr(self, 'playlist_tree') and hasattr(self.playlist, 'current_index'):

                        items = list(self.playlist_tree.get_children())

                        ci = getattr(self.playlist, 'current_index', -1)

                        if 0 <= ci < len(items):

                            self.playlist_tree.selection_set(items[ci])

                            self.playlist_tree.see(items[ci])

                except Exception:

                    pass

                self._play_selected_playlist_item()

        except Exception as e:

            self._log_message(f"下一首失败: {e}", "ERROR")



    def _play_prev_from_playlist(self):

        try:

            if not self.playlist:

                return

            prev_item = self.playlist.play_previous()

            if prev_item and prev_item.get('path'):

                # 同步UI选中到当前索引并走统一入口

                try:

                    self._rebuild_playlist_tree()

                except Exception:

                    pass

                try:

                    if hasattr(self, 'playlist_tree') and hasattr(self.playlist, 'current_index'):

                        items = list(self.playlist_tree.get_children())

                        ci = getattr(self.playlist, 'current_index', -1)

                        if 0 <= ci < len(items):

                            self.playlist_tree.selection_set(items[ci])

                            self.playlist_tree.see(items[ci])

                except Exception:

                    pass

                self._play_selected_playlist_item()

        except Exception as e:

            self._log_message(f"上一首失败: {e}", "ERROR")



    def _apply_player_options(self):

        """将 UI 的高级设置应用到 AutoPlayer"""

        try:

            # 基础：键位回退 & 回放层禁用黑键移调

            enable_key_fallback = bool(self.r_enable_key_fallback_var.get()) if hasattr(self, 'r_enable_key_fallback_var') else True

            enable_black_transpose = False

            black_transpose_strategy = (

                'down' if (

                    hasattr(self, 'black_transpose_strategy_var') and 

                    str(self.black_transpose_strategy_var.get()) in ('向下', '向下优先')

                ) else 'nearest'

            )



            # 和弦伴奏（非鼓可见）

            enable_chord_accomp = bool(getattr(self, 'enable_chord_accomp_var', tk.BooleanVar(value=True)).get()) if hasattr(self, 'enable_chord_accomp_var') else True

            chord_min_sustain_ms = int(getattr(self, 'chord_min_sustain_ms_var', tk.IntVar(value=1500)).get() if hasattr(self, 'chord_min_sustain_ms_var') else 1500)

            chord_replace_melody = bool(getattr(self, 'chord_replace_melody_var', tk.BooleanVar(value=False)).get() if hasattr(self, 'chord_replace_melody_var') else False)

            chord_block_window_ms = int(getattr(self, 'chord_block_window_ms_var', tk.IntVar(value=50)).get() if hasattr(self, 'chord_block_window_ms_var') else 50)



            # 多键/防重触发（默认原样）

            mode_disp = str(getattr(self, 'multi_key_mode_var', tk.StringVar(value='原样')).get()) if hasattr(self, 'multi_key_mode_var') else '原样'

            mode_map = {'原样': 'original', '合并(块和弦)': 'merge', '琶音': 'arpeggio'}

            multi_key_cluster_mode = mode_map.get(mode_disp, 'original')

            multi_key_cluster_window_ms = int(getattr(self, 'multi_key_window_var', tk.IntVar(value=50)).get() if hasattr(self, 'multi_key_window_var') else 50)





            # 针对架子鼓和贝斯：禁用和弦功能
            cur_inst = getattr(self, 'current_instrument', '电子琴')

            if cur_inst == '架子鼓':

                enable_chord_accomp = False

                chord_replace_melody = False

                multi_key_cluster_mode = 'original'

            elif cur_inst == '贝斯':
                enable_chord_accomp = False
                chord_replace_melody = False


            # 下发到 AutoPlayer 的选项（包含回放期望的移调开关与半音）

            # 说明：enable_pretranspose 为 True 时，AutoPlayer 会在事件映射前对 note 应用 pretranspose_semitones 偏移

            # 若使用“自动选择白键占比”，建议先在解析时运行一次获取最佳半音并写回 pretranspose_semitones_var

            # 若未解析，半音默认为 0（不移调）

            try:

                enable_preproc = bool(getattr(self, 'enable_preproc_var', tk.BooleanVar(value=True)).get())

            except Exception:

                enable_preproc = True

            try:

                manual_semitones = int(getattr(self, 'pretranspose_semitones_var', tk.IntVar(value=0)).get())

            except Exception:

                manual_semitones = 0

            # 短音过滤已在MIDI解析阶段(_analyze_current_midi)完成，此处不再处理

            min_note_duration_ms = 0



            options = {

                'enable_key_fallback': enable_key_fallback,

                'enable_black_transpose': enable_black_transpose,

                'black_transpose_strategy': black_transpose_strategy,

                'enable_chord_accomp': enable_chord_accomp,

                'chord_min_sustain_ms': chord_min_sustain_ms,

                'chord_block_window_ms': chord_block_window_ms,

                'chord_replace_melody': chord_replace_melody,

                'multi_key_cluster_mode': multi_key_cluster_mode,

                'multi_key_cluster_window_ms': multi_key_cluster_window_ms,

                # 新增：回放阶段的整曲移调（手动/自动结果均通过该半音值体现）

                'enable_pretranspose': enable_preproc,

                'pretranspose_semitones': manual_semitones,

                # 新增：高密度事件时序参数（鼓直通等场景优化）

                # 适度提前发送，降低Windows调度抖动带来的卡音感

                'send_ahead_ms': 10,

                # 忙等阈值（毫秒），平衡CPU与精度

                'spin_threshold_ms': 1,

                # 单次按键动作后的微睡眠（毫秒），缓解驱动黏连

                'post_action_sleep_ms': 0.5,

                # 重触发最小间隔（毫秒），鼓连击更顺

                'retrigger_min_gap_ms': 30,

                # 短音过滤已在MIDI解析阶段完成，此处不再传递

            }



            # 通过服务层下发，兼容未来替换播放器

            try:

                if getattr(self, 'playback_service', None) and hasattr(self.playback_service, 'configure_auto_player'):

                    self.playback_service.configure_auto_player(options=options)

                    return

            except Exception:

                pass

            # 回退：直接对现有 auto_player 下发

            if hasattr(self, 'auto_player') and self.auto_player and hasattr(self.auto_player, 'set_options'):

                self.auto_player.set_options(**options)

        except Exception as e:

            self._log_message(f"应用回放设置失败: {str(e)}", "ERROR")
    
    
    
    def _start_auto_play(self):

        """开始自动弹琴（仅MIDI模式）"""

        try:

            # 在开始任何播放前，先应用一次回放相关设置，确保最新参数下发到 AutoPlayer

            try:

                if hasattr(self, '_apply_player_options'):

                    self._apply_player_options()

            except Exception as exp:

                try:

                    self._log_message(f"应用回放设置时出现警告: {exp}", "WARNING")

                except Exception:

                    pass

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

                # 倒计时期间：禁用开始按钮，启用暂停按钮
                try:
                    if hasattr(self, 'auto_play_button'):
                        self.auto_play_button.configure(state=tk.DISABLED)
                    if hasattr(self, 'pause_button'):
                        self.pause_button.configure(state=tk.NORMAL)
                except Exception:
                    pass
                
                def _tick(n: int):

                    if n <= 0:

                        self._log_message("开始！", "SUCCESS")

                        # 倒计时结束：恢复按钮状态
                        try:
                            if hasattr(self, 'auto_play_button'):
                                self.auto_play_button.configure(state=tk.NORMAL)
                            if hasattr(self, 'pause_button'):
                                self.pause_button.configure(state=tk.DISABLED)
                        except Exception:
                            pass
                        _do_start()

                        return

                    # 可视更新 + 日志

                    try:

                        if getattr(self, 'countdown_label', None):

                            self.countdown_label.configure(text=f"{n} 秒后开始...")
                    except Exception:

                        pass

                    self._log_message(f"倒计时: {n}", "INFO")

                    if hasattr(self, 'root'):

                        self._countdown_after_id = self.root.after(1000, lambda: _tick(n - 1))

                self._countdown_after_id = self.root.after(0, lambda: _tick(sec))

            else:

                _do_start()

        except Exception as e:

            self._log_message(f"启动演奏失败: {str(e)}", "ERROR")
            messagebox.showerror("错误", f"启动演奏失败:\n{str(e)}")
    
    
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

                    # 尝试从播放列表管理器中获取完整路径
                    try:
                        playlist_item = self.playlist.playlist_items[selected[0]]
                        midi_path = playlist_item.get('path', '')
                        if midi_path and os.path.exists(midi_path):
                            # 更新_file_paths字典以避免下次查找失败
                            self._file_paths[selected[0]] = os.path.abspath(midi_path)
                        else:
                            midi_path = file_name
                            self._log_message(f"警告: 无法获取播放列表项的完整路径，使用文件名: {file_name}", "WARNING")
                    except Exception as e:
                        midi_path = file_name
                        self._log_message(f"获取播放列表项路径失败: {e}，使用文件名: {file_name}", "ERROR")
            
            
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

                    chord_replace_melody = False

                    try:

                        # 获取和弦伴奏设置

                        if hasattr(self, 'enable_chord_accomp_var'):

                            enable_chord_accomp = bool(self.enable_chord_accomp_var.get())

                        if hasattr(self, 'chord_accomp_mode_var'):

                            chord_accomp_mode = str(self.chord_accomp_mode_var.get()) or 'triad'

                        if hasattr(self, 'chord_accomp_min_sustain_var'):

                            chord_accomp_min_sustain_ms = int(self.chord_accomp_min_sustain_var.get())

                        if hasattr(self, 'chord_replace_melody_var'):

                            chord_replace_melody = bool(self.chord_replace_melody_var.get())
                        
                        
                        
                        if enable_chord_accomp:

                            self._log_message(f"和弦伴奏已启用: 模式={chord_accomp_mode}, 持续={chord_accomp_min_sustain_ms}ms", "INFO")

                    except Exception as e:

                        self._log_message(f"获取和弦设置失败: {e}", "ERROR")

                    try:

                        # 从统一解析设置控件获取参数（确保每次播放前下发）

                        auto_tx = True

                        manual_k = 0

                        min_ms = 0

                        try:

                            if hasattr(self, 'auto_transpose_enabled_var'):

                                auto_tx = bool(self.auto_transpose_enabled_var.get())

                        except Exception:

                            pass

                        try:

                            if hasattr(self, 'manual_transpose_semi_var'):

                                manual_k = int(self.manual_transpose_semi_var.get())

                        except Exception:

                            pass

                        try:

                            if hasattr(self, 'min_note_duration_ms_var'):

                                min_ms = int(self.min_note_duration_ms_var.get())

                        except Exception:

                            pass



                        # 先更新 AutoPlayer 的通用选项（不再传递旧的整体移调开关，避免冲突）

                        self.playback_service.configure_auto_player(

                            debug=(bool(self.debug_var.get()) if hasattr(self, 'debug_var') else None),

                            options=dict(

                                enable_key_fallback=enable_key_fallback,

                                enable_black_transpose=enable_black_transpose,

                                black_transpose_strategy=black_transpose_strategy,

                                enable_chord_accomp=enable_chord_accomp,

                                chord_accomp_mode=chord_accomp_mode,

                                chord_accomp_min_sustain_ms=chord_accomp_min_sustain_ms,

                                chord_replace_melody=chord_replace_melody,

                            ),

                        )

                        # 再下发解析前置设置（短音过滤 + 自动/手动移调）到服务层

                        if hasattr(self, 'playback_service') and self.playback_service:

                            self.playback_service.configure_analysis_settings(

                                auto_transpose=auto_tx,

                                manual_semitones=manual_k,

                                min_note_duration_ms=min_ms,

                            )

                        if enable_chord_accomp:

                            self._log_message("已向AutoPlayer传递和弦伴奏设置", "INFO")

                        # 记录本次设置快照

                        self._log_message(f"[DEBUG] 解析设置: auto_transpose={auto_tx}, manual_k={manual_k}, min_ms={min_ms}", "DEBUG")

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



                    # 架子鼓直接播放，其他乐器使用解析设置（兼容中文/英文标识）

                    if self.current_instrument in ('drums', '架子鼓'):

                        # 架子鼓直接使用 DrumsController

                        try:

                            if not hasattr(self, 'drums_controller') or not self.drums_controller:

                                from meowauto.app.controllers.drums_controller import DrumsController

                                self.drums_controller = DrumsController(self.playback_service)

                            success = bool(self.drums_controller.start_from_file(

                                midi_path, 

                                tempo=self.tempo_var.get()

                            ))

                        except Exception as e:

                            self._log_message(f"架子鼓播放失败: {e}", "ERROR")

                            success = False

                    else:

                        # 其他乐器使用解析设置流程

                        try:

                            strategy_name = self._resolve_strategy_name()

                        except Exception:

                            strategy_name = "strategy_21key"

                        use_analyzed = False

                        try:

                            # 检查是否有解析结果且文件匹配

                            self._log_message(f"[DEBUG] 检查解析结果: hasattr(analysis_notes)={hasattr(self, 'analysis_notes')}, analysis_notes={len(getattr(self, 'analysis_notes', []))}, analysis_file={getattr(self, 'analysis_file', 'None')}", "DEBUG")

                            
                            
                            if (hasattr(self, 'analysis_notes') and self.analysis_notes and 

                                hasattr(self, 'analysis_file') and self.analysis_file):

                                if os.path.abspath(self.analysis_file) == os.path.abspath(midi_path):

                                    use_analyzed = True

                                    self._log_message(f"使用已解析结果播放，事件数: {len(self.analysis_notes)}", "INFO")

                                else:

                                    self._log_message(f"解析文件不匹配: {self.analysis_file} vs {midi_path}", "WARNING")

                            else:

                                # 未加载右侧解析结果：走统一管线的 pretty_midi 解析播放

                                self._log_message("未加载右侧解析结果，将直接解析当前文件并播放（统一管线）", "INFO")

                        except Exception as e:

                            self._log_message(f"检查解析结果时出错: {e}", "ERROR")

                            use_analyzed = False



                        # 添加调试信息

                        tempo_value = self.tempo_var.get()

                        self._log_message(f"启动播放: tempo={tempo_value}, use_analyzed={use_analyzed}", "DEBUG")

                        
                        
                        success = bool(self.playback_service.start_auto_play_from_path(

                            midi_path,

                            tempo=tempo_value,

                            key_mapping=default_key_mapping,

                            strategy_name=strategy_name,

                            use_analyzed=use_analyzed,

                            analyzed_notes=(self.analysis_notes if use_analyzed else None),

                        ))

                else:

                    success = False



                if success:

                    # 更新按钮状态

                    self.auto_play_button.configure(text="停止演奏", command=self._stop_auto_play)
                    self.pause_button.configure(text="暂停", state="normal")

                    self.ui_manager.set_status(f"开始演奏: {file_name}")
                    self._log_message(f"开始演奏: {file_name} ({file_type})", "SUCCESS")
                    

                    # 更新播放列表状态（统一设置为正在演奏）
                    try:

                        selected = self.playlist_tree.selection()

                        if selected:

                            self.playlist_tree.set(selected[0], "状态", "正在演奏")
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

                    self._log_message("演奏启动失败，自动跳过到下一首", "ERROR")
                    try:

                        selected = self.playlist_tree.selection()

                        if selected:

                            self.playlist_tree.set(selected[0], "演奏状态", "错误")
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

            self.auto_play_button.configure(text="开始演奏", command=self._start_auto_play)
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

            self.ui_manager.set_status("演奏已停止")
            self._log_message("演奏已停止")
            # 关闭watchdog

            try:

                self._cancel_auto_next_watchdog()

            except Exception:

                pass
            
            
            
            # 无进度模拟逻辑

            
            
            # 更新播放列表状态

            selected = self.playlist_tree.selection()

            if selected:

                self.playlist_tree.set(selected[0], "演奏状态", "已停止")
            
            
        except Exception as e:

            self._log_message(f"停止演奏失败: {str(e)}", "ERROR")
    

    
    
    

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
                # 检查当前页面是否为架子鼓页面
                current_page = getattr(self, 'current_page', None)
                if current_page and hasattr(current_page, '_load_midi_from_playlist'):
                    # 架子鼓页面：使用架子鼓专属的加载方法
                    success = current_page._load_midi_from_playlist(full_path)
                    if success:
                        self._log_message(f"已加载文件到架子鼓页面: {os.path.basename(full_path)}", "SUCCESS")
                    else:
                        self._log_message("加载文件到架子鼓页面失败", "ERROR")
                else:
                    # 其他页面：使用通用的加载方法
                    # self.playback_mode.set("midi")  # 变量不存在，已注释
                    self.midi_path_var.set(full_path)

                    # 解析（会应用预处理与后处理）
                    try:
                        self._analyze_current_midi()
                    except Exception as e:
                        self._log_message(f"解析失败: {e}", "ERROR")

                    # 若仍在播放，先停止，避免"仍在播放"导致无法启动下一首
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

            # 重置开始演奏按钮文本
            if hasattr(self, 'auto_play_button'):

                try:

                    self.auto_play_button.configure(text="开始演奏", command=self._start_auto_play)
                except Exception:
                    pass
            # 重置MIDI播放按钮文本
            if hasattr(self, 'midi_play_button'):
                try:
                    self.midi_play_button.configure(text="播放MIDI音频", style="MF.Info.TButton")
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

                    self.playlist_tree.set(selected[0], "演奏状态", "已停止")
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

        """播放MIDI音频（纯音频播放，不触发自动演奏）"""
        try:

            midi_path = self.midi_path_var.get() if hasattr(self, 'midi_path_var') else ''

            if not midi_path:

                messagebox.showerror("错误", "请先选择MIDI文件")

                return

            if not os.path.exists(midi_path):

                messagebox.showerror("错误", "MIDI文件不存在")

                return

            
            # 纯音频播放：不使用AutoPlayer，直接播放MIDI音频
            self.ui_manager.set_status("正在播放MIDI音频...")
            self._log_message("开始播放MIDI音频（不触发自动演奏）")
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

                self._log_message(f"启动MIDI音频播放失败: {e}", "ERROR")
            if ok:

                self._log_message("MIDI音频播放成功", "SUCCESS")
                self.ui_manager.set_status("MIDI音频播放中...")
                if hasattr(self, 'pause_button'):

                    self.pause_button.configure(text="暂停", state="正常" if hasattr(self.pause_button, 'state') else "normal")

                    try:

                        self.pause_button.configure(state="normal")

                    except Exception:

                        pass

                # 更新MIDI播放按钮状态
                if hasattr(self, 'midi_play_button'):
                    try:
                        self.midi_play_button.configure(text="停止音频", style="danger")
                    except Exception:
                        pass
            else:

                self._log_message("MIDI音频播放失败", "ERROR")
                self.ui_manager.set_status("MIDI音频播放失败")
                messagebox.showerror("错误", "MIDI音频播放失败，请检查文件格式")
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

            item_id = self.playlist_tree.insert("", "end", values=(item_count, file_name, file_type, duration, "未演奏"))
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

        self._load_selected_playlist_item_to_main()

    def _load_selected_playlist_item_to_main(self):
        """将选中的演奏列表项加载到主页面"""
        try:
            selected = self.playlist_tree.selection()
            if not selected:
                return

            item_id = selected[0]
            item = self.playlist_tree.item(item_id)
            filename = item['values'][1] if item['values'] else "未知文件"

            # 获取完整路径
            full_path = None
            try:
                if hasattr(self, '_file_paths'):
                    full_path = self._file_paths.get(item_id)
            except Exception:
                full_path = None

            if not full_path:
                full_path = filename

            # 通过文件扩展名判断文件类型
            file_ext = os.path.splitext(full_path)[1].lower()
            if file_ext in ['.mid', '.midi']:
                ftype = "MIDI文件"
            elif file_ext == '.lrcp':
                ftype = "LRCp乐谱"
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                ftype = "音频文件"
            else:
                ftype = "未知类型"

            self._log_message(f"[双击加载] 文件={filename} 路径={full_path} 类型={ftype}", "INFO")

            if ftype == "MIDI文件" and full_path:
                # 检查当前页面是否为架子鼓页面
                current_page = getattr(self, 'current_page', None)
                if current_page and hasattr(current_page, '_load_midi_from_playlist'):
                    # 架子鼓页面：使用架子鼓专属的加载方法
                    success = current_page._load_midi_from_playlist(full_path)
                    if success:
                        self._log_message(f"已加载文件到架子鼓页面: {os.path.basename(full_path)}", "SUCCESS")
                    else:
                        self._log_message("加载文件到架子鼓页面失败", "ERROR")
                else:
                    # 其他页面：使用通用的加载方法
                    # self.playback_mode.set("midi")  # 变量不存在，已注释
                    self.midi_path_var.set(full_path)
                    
                    # 更新文件信息显示
                    if hasattr(self, '_update_file_info_display'):
                        self._update_file_info_display(full_path)
                    
                    # 解析MIDI文件
                    try:
                        self._analyze_current_midi()
                        self._log_message(f"已加载并解析文件到主页面: {os.path.basename(full_path)}", "SUCCESS")
                    except Exception as e:
                        self._log_message(f"解析失败: {e}", "ERROR")
                        
        except Exception as e:
            self._log_message(f"双击加载失败: {e}", "ERROR")

    def _update_file_info_display(self, file_path):
        """更新文件信息显示"""
        try:
            if not file_path or not os.path.exists(file_path):
                if hasattr(self, 'file_info_var'):
                    self.file_info_var.set("未选择文件")
                return
            
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f} MB"
            
            # 获取文件类型
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.mid', '.midi']:
                file_type = "MIDI文件"
            elif file_ext == '.lrcp':
                file_type = "LRCp乐谱"
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                file_type = "音频文件"
            else:
                file_type = "未知类型"
            
            info_text = f"已选择: {file_name} ({file_type}, {file_size_str})"
            
            # 对于MIDI文件，添加音高信息
            if file_ext in ['.mid', '.midi']:
                try:
                    from meowauto.midi import analyzer
                    # 解析MIDI获取音高信息
                    res = analyzer.parse_midi(file_path)
                    if res.get('ok'):
                        # 检查返回结果中是否包含音高信息
                        if 'max_note' in res and 'min_note' in res:
                            # 如果结果中已有音高信息，直接使用
                            max_note = res.get('max_note', 0)
                            min_note = res.get('min_note', 127)
                            max_group = res.get('max_group', '未知')
                            min_group = res.get('min_group', '未知')
                            max_status = res.get('max_status', '未超限')
                            min_status = res.get('min_status', '未超限')
                            above_83_count = res.get('above_83_count', 0)
                            below_48_count = res.get('below_48_count', 0)
                        else:
                            # 如果结果中没有音高信息，手动计算
                            notes = res.get('notes', [])
                            if notes:
                                note_values = [n.get('note', 0) for n in notes if 'note' in n]
                                if note_values:
                                    max_note = max(note_values)
                                    min_note = min(note_values)
                                    # 简单的音组判断
                                    if max_note > 83:
                                        max_group = "小字三组及以上"
                                        max_status = "已超限"
                                    elif max_note > 71:
                                        max_group = "小字二组"
                                        max_status = "未超限"
                                    else:
                                        max_group = "小字一组及以下"
                                        max_status = "未超限"
                                    
                                    if min_note < 48:
                                        min_group = "小字组以下"
                                        min_status = "已超限"
                                    elif min_note < 60:
                                        min_group = "小字组"
                                        min_status = "未超限"
                                    else:
                                        min_group = "小字一组及以上"
                                        min_status = "未超限"
                                    
                                    above_83_count = len([note for note in note_values if note > 83])
                                    below_48_count = len([note for note in note_values if note < 48])
                                else:
                                    max_note, min_note = 0, 127
                                    max_group, min_group = "未知", "未知"
                                    max_status, min_status = "未超限", "未超限"
                                    above_83_count, below_48_count = 0, 0
                            else:
                                max_note, min_note = 0, 127
                                max_group, min_group = "未知", "未知"
                                max_status, min_status = "未超限", "未超限"
                                above_83_count, below_48_count = 0, 0
                        
                        # 添加音高信息到显示文本
                        info_text += f"\n最高音：{max_note}  {max_group}  {max_status} 超限数量 {above_83_count}"
                        info_text += f"\n最低音：{min_note} {min_group}  {min_status} 超限数量 {below_48_count}"
                except Exception as e:
                    # 如果解析失败，不影响基本信息显示
                    self._log_message(f"获取音高信息失败: {e}", "DEBUG")
            
            if hasattr(self, 'file_info_var'):
                self.file_info_var.set(info_text)
                
        except Exception as e:
            if hasattr(self, 'file_info_var'):
                self.file_info_var.set("文件信息获取失败")
            self._log_message(f"更新文件信息显示失败: {e}", "ERROR")

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



                # 若原神简洁页存在，镜像输出到其日志

                try:

                    if getattr(self, 'yuanshen_page', None) and hasattr(self.yuanshen_page, 'append_log'):

                        self.yuanshen_page.append_log(formatted_message)

                except Exception:

                    pass
                
                
                
                # 限制日志行数，避免内存占用过大

                lines = self.log_text.get("1.0", tk.END).split('\n')

                if len(lines) > 1000:

                    self.log_text.delete("1.0", "500.0")

        except Exception:

            # 静默忽略日志失败，避免噪声

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

                print("[DEBUG] 启动保护启用，忽略关闭请求")

                return

            # 关闭确认

            try:

                if not getattr(self, '_allow_close', False):

                    if messagebox.askokcancel("退出", "确定要退出 MeowField AutoPiano 吗？") is False:

                        print("[DEBUG] 用户取消关闭")

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

            print("[DEBUG] 触发 _on_closing，发布 SYSTEM_SHUTDOWN 并销毁 root")

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

            widget = event.widget if event is not None else None

            is_root = (widget is self.root) if widget is not None else True

            name = str(widget) if widget is not None else 'root'

            if getattr(self, '_ui_debug', False):

                print(f"[DEBUG] <Destroy> 捕获: widget={name}, is_root={is_root}")

            try:

                self._log_message(f"窗口销毁事件: {name}, is_root={is_root}", "INFO")

            except Exception:

                pass

        except Exception:

            pass
    
    
    
    def _check_admin_privileges(self):

        """检查管理员权限"""

        try:

            is_admin = ctypes.windll.shell32.IsUserAnAdmin()

            if not is_admin:

                print("⚠️  警告: 程序未以管理员权限运行")

                print("某些功能可能无法正常工作，建议以管理员身份运行")

                # 不强制退出，只是警告

            else:

                print("✅ 检测到管理员权限")

        except Exception as e:

            print(f"⚠️  无法检查管理员权限: {e}")
    
    
    
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
