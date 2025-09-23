#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播放列表侧栏组件
"""
import tkinter as tk
from tkinter import ttk

def create_playlist_sidebar(controller, parent_right):
    """创建右侧演奏列表侧栏"""
    try:
        # 创建侧栏容器（固定300px宽度）
        sidebar = ttk.Frame(parent_right, width=300)
        sidebar.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        sidebar.pack_propagate(False)  # 保持固定宽度
        
        # 演奏列表标题
        title_frame = ttk.Frame(sidebar)
        title_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(5, 2))
        ttk.Label(title_frame, text="演奏列表", font=('TkDefaultFont', 10, 'bold')).pack(side=tk.LEFT)
        
        # 移除重复控件，操作功能交由主页面处理
        
        # 播放模式选择
        mode_frame = ttk.Frame(sidebar)
        mode_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Label(mode_frame, text="模式:", font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
        controller.playlist_mode_var = tk.StringVar(value='顺序')
        mode_combo = ttk.Combobox(mode_frame, textvariable=controller.playlist_mode_var, 
                                  state='readonly', width=8, values=['单曲','顺序','循环','随机'],
                                  font=('TkDefaultFont', 8))
        mode_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # 播放列表树表（窄列显示）
        tree_frame = ttk.Frame(sidebar)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # 创建树表（紧凑列）
        columns = ("#", "文件", "状态")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)
        headers = ["#", "文件", "状态"]
        widths = [30, 120, 40]  # 窄列宽度
        
        for i, col in enumerate(columns):
            tree.heading(col, text=headers[i])
            tree.column(col, width=widths[i], anchor=tk.CENTER if i != 1 else tk.W)
        
        # 滚动条
        vbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vbar.set)
        
        # 布局
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 将句柄挂到 controller，供 app 工作流使用
        controller.playlist_tree = tree
        if not hasattr(controller, '_file_paths') or not isinstance(getattr(controller, '_file_paths'), dict):
            controller._file_paths = {}
        
        # 绑定双击事件：双击加载MID文件到主页面
        tree.bind('<Double-1>', controller._on_playlist_double_click)
        
        # 绑定模式变更事件
        try:
            controller.playlist_mode_var.trace_add('write', 
                lambda *args: getattr(controller, '_on_playlist_mode_changed', lambda *a, **k: None)())
        except Exception:
            pass
        
        return sidebar
        
    except Exception as e:
        try:
            controller._log_message(f"创建播放列表侧栏失败: {e}", "ERROR")
        except Exception:
            pass
        return None

