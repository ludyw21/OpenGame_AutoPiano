import tkinter as tk
from tkinter import ttk

try:
    from ttkbootstrap.tooltip import ToolTip
except Exception:
    ToolTip = None

class Sidebar:
    def __init__(self, parent, on_action=None, width=200):
        self.on_action = on_action or (lambda key: None)
        self.frame = ttk.Frame(parent)
        self._collapsed = False
        self._expanded_width = width

        # 容器
        self._container = ttk.Frame(self.frame)
        self._container.pack(fill=tk.Y)

        # 折叠/展开按钮
        self._toggle_btn = ttk.Button(self._container, text="≡", width=3, command=self.toggle)
        self._toggle_btn.pack(padx=4, pady=6)
        if ToolTip:
            ToolTip(self._toggle_btn, text="折叠/展开侧边栏")

        # 游戏区域
        game_label = ttk.Label(self._container, text="游戏", anchor=tk.W)
        game_label.pack(padx=6, pady=(4, 0), fill=tk.X)
        self._game_buttons = []
        btn_default = ttk.Button(self._container, text="开放空间", width=12, command=lambda: self.on_action("game-default"))
        btn_default.pack(padx=6, pady=4, fill=tk.X)
        self._game_buttons.append(btn_default)
        btn_ys = ttk.Button(self._container, text="原神", width=12, command=lambda: self.on_action("game-yuanshen"))
        btn_ys.pack(padx=6, pady=0, fill=tk.X)
        self._game_buttons.append(btn_ys)

        ttk.Separator(self._container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))

        # 常用按钮
        self._buttons = []
        about_btn = ttk.Button(self._container, text="关于", width=12, command=lambda: self.on_action("about"))
        about_btn.pack(padx=6, pady=4, fill=tk.X)
        if ToolTip:
            ToolTip(about_btn, text="查看项目说明")
        self._buttons.append(about_btn)

        # 初始宽度
        self.frame.update_idletasks()
        self.frame.configure(width=self._expanded_width)

    def attach(self, **grid_kwargs):
        self.frame.grid(**grid_kwargs)

    def toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            for b in self._buttons:
                b.pack_forget()
            for b in getattr(self, '_game_buttons', []):
                b.pack_forget()
            self.frame.configure(width=40)
        else:
            for b in getattr(self, '_game_buttons', []):
                b.pack(padx=6, pady=4, fill=tk.X)
            for b in self._buttons:
                b.pack(padx=6, pady=4, fill=tk.X)
            self.frame.configure(width=self._expanded_width)
        self.frame.update_idletasks()