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

        # 菜单按钮（使用文字代替图标）
        self._buttons = []
        for key, text, tip in [
            ("files", "文件", "打开音频/加载资源"),
            ("playlist", "列表", "管理自动演奏列表"),
            ("convert", "转换", "音频转MIDI / MIDI转LRCp"),
            ("auto", "自动", "开始/停止自动弹琴"),
            ("settings", "设置", "外观与偏好"),
            ("help", "帮助", "查看帮助")
        ]:
            b = ttk.Button(self._container, text=text, width=12, command=lambda k=key: self.on_action(k))
            b.pack(padx=6, pady=4, fill=tk.X)
            if ToolTip:
                ToolTip(b, text=tip)
            self._buttons.append(b)

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
            self.frame.configure(width=40)
        else:
            for b in self._buttons:
                b.pack(padx=6, pady=4, fill=tk.X)
            self.frame.configure(width=self._expanded_width)
        self.frame.update_idletasks() 