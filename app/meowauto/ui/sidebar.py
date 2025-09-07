import tkinter as tk
from tkinter import ttk

try:
    from ttkbootstrap.tooltip import ToolTip
except Exception:
    ToolTip = None

class Sidebar:
    def __init__(self, parent, on_action=None, width=200, on_width=None):
        self.on_action = on_action or (lambda key: None)
        self.frame = ttk.Frame(parent)
        self._expanded_width = width
        # 固定宽度，常驻显示
        self._on_width = on_width or (lambda w: None)
        self._active_key = None
        self._inst_buttons = {}
        self._tool_buttons = {}

        # 容器
        self._container = ttk.Frame(self.frame)
        self._container.pack(fill=tk.BOTH, expand=True)

        # 不再提供折叠/展开按钮，侧边栏常驻显示

        # 模式切换（暂不提供：合奏后续实现）
        # 占位分隔
        ttk.Separator(self._container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))

        # 初始化样式（与分页标签栏一致的蓝白设计语言）
        try:
            style = ttk.Style()
            # 普通状态：浅蓝底蓝字
            style.configure('MF.Sidebar.TButton', 
                           font=("Segoe UI", 11, "normal"), 
                           padding=(10, 8),
                           foreground='#0A84FF', 
                           background='#E6F0FF',
                           relief='flat', 
                           borderwidth=0)
            style.map('MF.Sidebar.TButton', 
                     background=[('active', '#D9E8FF'), ('pressed', '#C8DCFF')])
            # 激活状态：蓝底白字
            style.configure('MF.Sidebar.Active.TButton', 
                           font=("Segoe UI", 11, "normal"), 
                           padding=(10, 8),
                           foreground='white', 
                           background='#0A84FF',
                           relief='flat', 
                           borderwidth=0)
            style.map('MF.Sidebar.Active.TButton', 
                     background=[('active', '#0A6DFF'), ('pressed', '#095EC8')])
        except Exception:
            pass

        # 乐器板块
        inst_label = ttk.Label(self._container, text="乐器板块", anchor=tk.W)
        inst_label.pack(padx=6, pady=(2, 0), fill=tk.X)
        self.inst_frame = ttk.Frame(self._container)
        self.inst_frame.pack(padx=6, pady=4, fill=tk.X)
        self._inst_buttons['inst-epiano'] = ttk.Button(self.inst_frame, text="电子琴", style='MF.Sidebar.TButton',
                                                       command=lambda: self._on_select('inst-epiano'))
        self._inst_buttons['inst-epiano'].pack(padx=0, pady=4, fill=tk.X)
        self._inst_buttons['inst-guitar'] = ttk.Button(self.inst_frame, text="吉他", style='MF.Sidebar.TButton',
                                                      command=lambda: self._on_select('inst-guitar'))
        self._inst_buttons['inst-guitar'].pack(padx=0, pady=4, fill=tk.X)
        self._inst_buttons['inst-bass'] = ttk.Button(self.inst_frame, text="贝斯", style='MF.Sidebar.TButton',
                                                    command=lambda: self._on_select('inst-bass'))
        self._inst_buttons['inst-bass'].pack(padx=0, pady=4, fill=tk.X)
        self._inst_buttons['inst-drums'] = ttk.Button(self.inst_frame, text="架子鼓", style='MF.Sidebar.TButton',
                                                     command=lambda: self._on_select('inst-drums'))
        self._inst_buttons['inst-drums'].pack(padx=0, pady=4, fill=tk.X)

        # 工具分组
        ttk.Separator(self._container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))
        tools_label = ttk.Label(self._container, text="工具", anchor=tk.W)
        tools_label.pack(padx=6, pady=(2, 0), fill=tk.X)
        self.tools_frame = ttk.Frame(self._container)
        self.tools_frame.pack(padx=6, pady=4, fill=tk.X)
        self._tool_buttons['tool-audio2midi'] = ttk.Button(
            self.tools_frame,
            text="音频转MIDI",
            style='MF.Sidebar.TButton',
            command=lambda: self._on_select('tool-audio2midi')
        )
        self._tool_buttons['tool-audio2midi'].pack(padx=0, pady=4, fill=tk.X)

        # 常用按钮（精简后暂留为空，保留结构便于后续扩展）
        self._buttons = []

        # 初始宽度
        self.frame.update_idletasks()
        self.frame.configure(width=self._expanded_width)
        try:
            self._on_width(self._expanded_width)
        except Exception:
            pass

    def attach(self, use_pack: bool = False, **grid_kwargs):
        """将侧边栏加入父容器。
        use_pack=True 时使用 pack(side=LEFT, fill=Y)，可减少 holder 内部的重布局闪烁。
        默认保持 grid 以兼容旧用法。
        """
        if use_pack:
            try:
                self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                return
            except Exception:
                pass
        # 兼容：回退到 grid
        self.frame.grid(**grid_kwargs)

    # --- 交互与高亮 ---
    def _on_select(self, key: str):
        self.set_active(key)
        self.on_action(key)

    def set_active(self, key: str):
        self._active_key = key
        for k, btn in self._inst_buttons.items():
            try:
                btn.configure(style='MF.Sidebar.Active.TButton' if k == key else 'MF.Sidebar.TButton')
            except Exception:
                pass
        for k, btn in self._tool_buttons.items():
            try:
                btn.configure(style='MF.Sidebar.Active.TButton' if k == key else 'MF.Sidebar.TButton')
            except Exception:
                pass