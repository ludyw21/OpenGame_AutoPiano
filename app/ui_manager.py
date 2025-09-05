#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI管理器
负责界面布局、主题管理和组件协调
"""

import tkinter as tk
from tkinter import ttk
import ctypes
from typing import Dict, Any, Optional, Callable
import threading


class UIManager:
    """UI管理器"""
    
    def __init__(self, root: tk.Tk, event_bus=None):
        self.root = root
        self.event_bus = event_bus
        self.components: Dict[str, Any] = {}
        self.themes = {
            'light': ['pink', 'flatly', 'litera', 'cosmo', 'sandstone'],
            'dark': ['darkly', 'superhero', 'cyborg', 'solar']
        }
        self.current_theme = 'pink'
        self.current_mode = 'light'
        self.scaling_factor = 1.0
        self.density = 'compact'
        
        # 初始化样式
        self._init_styles()
        
        # 创建主布局
        self._create_main_layout()
        
        # 绑定窗口事件
        self._bind_window_events()
    
    def _init_styles(self):
        """初始化样式系统"""
        try:
            import ttkbootstrap as tb
            self.style = tb.Style(theme="pink")
            self.use_ttkbootstrap = True
        except ImportError:
            self.style = ttk.Style()
            self.use_ttkbootstrap = False
        
        # 设置按钮样式
        self.accent_button_style = "Accent.TButton" if self.use_ttkbootstrap else "TButton"
        self.secondary_button_style = "Secondary.TButton" if self.use_ttkbootstrap else "TButton"
    
    def _create_main_layout(self):
        """创建主布局"""
        # 主容器
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_container.columnconfigure(1, weight=1)
        self.main_container.columnconfigure(2, weight=0)
        
        # 创建标题栏
        self._create_title_bar()
        
        # 创建内容区域
        self._create_content_area()
        
        # 创建状态栏
        self._create_status_bar()
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_frame = ttk.Frame(self.main_container)
        title_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 标题
        title_font = ("Microsoft YaHei", 18, "bold")
        # 只显示游戏名（由 App 通过 set_title_suffix 传入），默认显示“开放空间”
        self._base_title = ""
        self.title_label = ttk.Label(title_frame, text="开放空间", font=title_font)
        self.title_label.pack(side=tk.LEFT)
        
        # 外观控制
        self._create_appearance_controls(title_frame)
    
    def _create_appearance_controls(self, parent):
        """创建外观控制组件"""
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(side=tk.RIGHT)
        
        # 主题选择
        ttk.Label(controls_frame, text="主题:").pack(side=tk.LEFT)
        self.theme_var = tk.StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(
            controls_frame, 
            width=12, 
            state="readonly", 
            textvariable=self.theme_var,
            values=self.themes['light'] + self.themes['dark']
        )
        theme_combo.pack(side=tk.LEFT, padx=(4, 8))
        theme_combo.bind('<<ComboboxSelected>>', self._on_theme_change)
        
        # 模式选择
        ttk.Label(controls_frame, text="模式:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=self.current_mode)
        mode_combo = ttk.Combobox(
            controls_frame, 
            width=7, 
            state="readonly", 
            textvariable=self.mode_var,
            values=["light", "dark"]
        )
        mode_combo.pack(side=tk.LEFT, padx=(4, 8))
        mode_combo.bind('<<ComboboxSelected>>', self._on_mode_change)
        
        # 密度选择
        ttk.Label(controls_frame, text="密度:").pack(side=tk.LEFT)
        self.density_var = tk.StringVar(value=self.density)
        density_combo = ttk.Combobox(
            controls_frame, 
            width=10, 
            state="readonly", 
            textvariable=self.density_var,
            values=["comfortable", "compact"]
        )
        density_combo.pack(side=tk.LEFT, padx=(4, 0))
        density_combo.bind('<<ComboboxSelected>>', self._on_density_change)
    
    def _create_content_area(self):
        """创建内容区域"""
        # 页面容器
        self.page_container = ttk.Frame(self.main_container)
        self.page_container.grid(row=1, column=0, columnspan=3, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.main_container.rowconfigure(1, weight=1)
        self.page_container.columnconfigure(0, weight=1)
        self.page_container.rowconfigure(0, weight=1)
        
        # 创建主内容区域
        content_frame = ttk.Frame(self.page_container)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 使用Panedwindow创建可调整大小的左右分栏
        self.paned_window = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # 左侧框架 - 主要功能区域（内含：侧边栏容器 + 左侧内容容器）
        self.left_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.left_frame, weight=2)
        # 在 left_frame 内构建一个左右壳层：左为侧边栏、右为实际页面内容
        self.left_shell = ttk.Frame(self.left_frame)
        self.left_shell.pack(fill=tk.BOTH, expand=True)
        # 使用 grid 将 sidebar 与内容分两列布置
        self.left_shell.grid_rowconfigure(0, weight=1)
        # 列0为侧边栏，使用 minsize 控制宽度以实现动画
        self.left_shell.grid_columnconfigure(0, weight=0, minsize=200)
        # 列1为内容区，填充扩展
        self.left_shell.grid_columnconfigure(1, weight=1)
        # 侧边栏容器（列0）
        self.left_sidebar_holder = ttk.Frame(self.left_shell)
        self.left_sidebar_holder.grid(row=0, column=0, sticky=tk.NSEW)
        try:
            # 防止子组件压缩父容器尺寸，确保列最小宽度生效
            self.left_sidebar_holder.grid_propagate(False)
        except Exception:
            pass
        # 页面内容容器（列1）：供 Router 左侧内容挂载
        self.left_content_frame = ttk.Frame(self.left_shell)
        self.left_content_frame.grid(row=0, column=1, sticky=tk.NSEW)
        
        # 右侧框架 - 日志和状态区域
        self.right_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.right_frame, weight=1)
        
        # 配置左右框架的网格权重，确保子组件能正确扩展
        try:
            self.left_frame.columnconfigure(0, weight=1)
            self.left_frame.rowconfigure(0, weight=1)
        except Exception:
            pass
        
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self.main_container, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN
        )
        status_bar.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))

    def set_title_suffix(self, suffix: str | None):
        """设置标题后缀（例如当前游戏名）"""
        try:
            # 简化：仅显示游戏名
            text = suffix if (suffix and suffix.strip()) else "开放空间"
            if hasattr(self, 'title_label'):
                self.title_label.configure(text=text)
        except Exception:
            pass
    
    def _bind_window_events(self):
        """绑定窗口事件"""
        self.root.bind('<Configure>', self._on_window_resize)
        self.root.bind('<Key>', self._on_key_press)
    
    def _on_window_resize(self, event):
        """窗口大小改变事件"""
        if event.widget == self.root:
            self._update_layout(event.width, event.height)
    
    def _on_key_press(self, event):
        """键盘按键事件"""
        # 快捷键处理
        if event.state & 0x4:  # Ctrl
            if event.keysym == 't':
                self._toggle_theme()
            elif event.keysym == 'd':
                self._toggle_density()
    
    def _on_theme_change(self, event=None):
        """主题改变事件"""
        new_theme = self.theme_var.get()
        if new_theme != self.current_theme:
            self.switch_theme(new_theme)
    
    def _on_mode_change(self, event=None):
        """模式改变事件"""
        new_mode = self.mode_var.get()
        if new_mode != self.current_mode:
            self.switch_mode(new_mode)
    
    def _on_density_change(self, event=None):
        """密度改变事件"""
        new_density = self.density_var.get()
        if new_density != self.density:
            self.set_density(new_density)
    
    def _toggle_theme(self):
        """切换主题"""
        current_index = (self.themes['light'] + self.themes['dark']).index(self.current_theme)
        themes_list = self.themes['light'] + self.themes['dark']
        next_index = (current_index + 1) % len(themes_list)
        next_theme = themes_list[next_index]
        self.theme_var.set(next_theme)
        self.switch_theme(next_theme)
    
    def _toggle_density(self):
        """切换密度"""
        new_density = 'compact' if self.density == 'comfortable' else 'comfortable'
        self.density_var.set(new_density)
        self.set_density(new_density)
    
    def switch_theme(self, theme_name: str):
        """切换主题"""
        try:
            if self.use_ttkbootstrap:
                self.style.theme_use(theme_name)
            
            self.current_theme = theme_name
            
            # 更新模式
            if theme_name in self.themes['dark']:
                self.current_mode = 'dark'
                self.mode_var.set('dark')
            else:
                self.current_mode = 'light'
                self.mode_var.set('light')
            
            # 应用主题到所有组件
            self._apply_theme_to_components()
            
            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    'ui.theme_changed',
                    {'theme': theme_name, 'mode': self.current_mode},
                    'UIManager'
                )
            
            self._log_info(f"主题已切换为: {theme_name}")
            
        except Exception as e:
            self._log_error(f"切换主题失败: {e}")
    
    def switch_mode(self, mode: str):
        """切换明暗模式"""
        try:
            if mode == 'dark':
                # 选择深色主题
                dark_themes = self.themes['dark']
                if self.current_theme in dark_themes:
                    target_theme = self.current_theme
                else:
                    target_theme = dark_themes[0]
            else:
                # 选择浅色主题
                light_themes = self.themes['light']
                if self.current_theme in light_themes:
                    target_theme = self.current_theme
                else:
                    target_theme = light_themes[0]
            
            self.theme_var.set(target_theme)
            self.switch_theme(target_theme)
            
        except Exception as e:
            self._log_error(f"切换模式失败: {e}")
    
    def set_density(self, density: str):
        """设置控件密度"""
        try:
            self.density = density
            
            # 应用密度设置
            if density == "compact":
                row_height = 24
                padding = 4
            else:
                row_height = 28
                padding = 6
            
            # 更新样式
            self.style.configure('TFrame', padding=padding)
            self.style.configure('TLabel', padding=padding)
            self.style.configure('TButton', padding=padding)
            
            # 应用密度到所有组件
            self._apply_density_to_components()
            
            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    'ui.density_changed',
                    {'density': density},
                    'UIManager'
                )
            
            self._log_info(f"密度已设置为: {density}")
            
        except Exception as e:
            self._log_error(f"设置密度失败: {e}")
    
    def apply_scaling(self, mode_or_factor):
        """应用DPI缩放"""
        try:
            if isinstance(mode_or_factor, (int, float)):
                factor = float(mode_or_factor)
            else:
                # 自动检测DPI
                try:
                    shcore = ctypes.windll.shcore
                    shcore.SetProcessDpiAwareness(2)
                    user32 = ctypes.windll.user32
                    dc = user32.GetDC(0)
                    LOGPIXELSX = 88
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
                    factor = max(0.75, dpi / 96.0)
                except Exception:
                    px_per_inch = self.root.winfo_fpixels('1i')
                    factor = max(0.75, float(px_per_inch) / 96.0)
            
            self.root.tk.call('tk', 'scaling', factor)
            self.scaling_factor = factor
            
            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    'ui.scaling_changed',
                    {'factor': factor},
                    'UIManager'
                )
            
            self._log_info(f"DPI缩放已设置为: {factor:.2f}")
            
        except Exception as e:
            self._log_error(f"设置DPI缩放失败: {e}")
            self.scaling_factor = 1.0
    
    def _update_layout(self, width: int, height: int):
        """更新布局"""
        try:
            # 根据窗口大小调整组件布局
            if width < 800:
                # 小窗口：紧凑布局
                self._apply_compact_layout()
            elif width < 1200:
                # 中等窗口：标准布局
                self._apply_standard_layout()
            else:
                # 大窗口：宽松布局
                self._apply_relaxed_layout()
            
            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    'ui.layout_changed',
                    {'width': width, 'height': height},
                    'UIManager'
                )
            
        except Exception as e:
            self._log_error(f"更新布局失败: {e}")
    
    def _apply_compact_layout(self):
        """应用紧凑布局"""
        # 减小间距和字体大小
        self.style.configure('TFrame', padding=2)
        self.style.configure('TLabel', padding=2)
        self.style.configure('TButton', padding=2)
    
    def _apply_standard_layout(self):
        """应用标准布局"""
        # 标准间距和字体大小
        padding = 6 if self.density == 'comfortable' else 4
        self.style.configure('TFrame', padding=padding)
        self.style.configure('TLabel', padding=padding)
        self.style.configure('TButton', padding=padding)
    
    def _apply_relaxed_layout(self):
        """应用宽松布局"""
        # 增加间距和字体大小
        padding = 8 if self.density == 'comfortable' else 6
        self.style.configure('TFrame', padding=padding)
        self.style.configure('TLabel', padding=padding)
        self.style.configure('TButton', padding=padding)
    
    def _apply_theme_to_components(self):
        """将主题应用到所有组件"""
        for component_name, component in self.components.items():
            try:
                if hasattr(component, 'apply_theme'):
                    component.apply_theme(self.current_theme)
                elif hasattr(component, 'update_theme'):
                    component.update_theme(self.current_theme)
            except Exception:
                continue
    
    def _apply_density_to_components(self):
        """将密度设置应用到所有组件"""
        for component_name, component in self.components.items():
            try:
                if hasattr(component, 'apply_density'):
                    component.apply_density(self.density)
                elif hasattr(component, 'update_density'):
                    component.update_density(self.density)
            except Exception:
                continue
    
    def register_component(self, name: str, component: Any):
        """注册UI组件"""
        self.components[name] = component
        
        # 应用当前设置
        try:
            if hasattr(component, 'apply_theme'):
                component.apply_theme(self.current_theme)
            if hasattr(component, 'apply_density'):
                component.apply_density(self.density)
        except Exception:
            pass
    
    def unregister_component(self, name: str):
        """注销UI组件"""
        if name in self.components:
            del self.components[name]
    
    def get_component(self, name: str) -> Optional[Any]:
        """获取UI组件"""
        return self.components.get(name)
    
    def set_status(self, message: str):
        """设置状态栏消息"""
        self.status_var.set(message)
    
    def _log_info(self, message: str):
        """记录信息日志"""
        if self.event_bus:
            self.event_bus.publish('system.info', {'message': message}, 'UIManager')
        else:
            print(f"[UIManager] {message}")
    
    def _log_error(self, message: str):
        """记录错误日志"""
        if self.event_bus:
            self.event_bus.publish('system.error', {'message': message}, 'UIManager')
        else:
            print(f"[UIManager] {message}") 
