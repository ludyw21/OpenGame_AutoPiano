import tkinter as tk
from tkinter import ttk

try:
    from meowauto.widgets.table import style_table as _tbl_style, apply_striped as _tbl_striped, bind_hover_highlight as _tbl_hover
except Exception:
    _tbl_style = _tbl_striped = _tbl_hover = None

class PlaylistView:
    def __init__(self, parent, style: ttk.Style | None = None, density: str = "comfortable"):
        self.frame = ttk.LabelFrame(parent, text="自动演奏列表", padding="12")
        self.frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.frame.columnconfigure(0, weight=1)

        # 暴露工具栏
        self.toolbar = ttk.Frame(self.frame)
        self.toolbar.pack(fill=tk.X, pady=(0, 5))

        display_frame = ttk.Frame(self.frame)
        display_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('序号', '文件名', '类型', '时长', '状态')
        self.tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=6)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        vsb = ttk.Scrollbar(display_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 默认隐藏滚动条，保留滚轮
        try:
            vsb.pack_forget()
            def _on_mousewheel(e):
                try:
                    delta = int(-1 * (e.delta / 120))
                    self.tree.yview_scroll(delta, "units")
                    return "break"
                except Exception:
                    return
            self.tree.bind("<MouseWheel>", _on_mousewheel)
        except Exception:
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 样式
        try:
            if _tbl_style and style:
                _tbl_style(style, density)
            if _tbl_hover:
                _tbl_hover(self.tree)
        except Exception:
            pass

    def refresh_items(self, items: list[dict], current_index: int = -1):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for i, item in enumerate(items):
            status = "当前播放" if i == current_index else item.get('status', '')
            self.tree.insert("", "end", values=(
                i + 1,
                item.get('name', ''),
                item.get('type', ''),
                item.get('duration', ''),
                status
            ))
        try:
            if _tbl_striped:
                _tbl_striped(self.tree)
        except Exception:
            pass 