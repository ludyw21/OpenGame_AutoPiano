from tkinter import ttk

def style_table(style: ttk.Style, density: str = "comfortable"):
    row_h = 28 if density != "compact" else 24
    try:
        style.configure("Treeview", rowheight=row_h)
        # 头部字体略加粗
        style.configure("Treeview.Heading", font=(None, 10, "bold"))
    except Exception:
        pass


def apply_striped(tree: ttk.Treeview):
    # 通过 tag 实现隔行着色
    try:
        tree.tag_configure("oddrow", background="")
        tree.tag_configure("evenrow", background="#F7F7F7")
        # 重新标记已有行
        for i, iid in enumerate(tree.get_children("")):
            tree.item(iid, tags=("evenrow" if i % 2 == 0 else "oddrow",))
    except Exception:
        pass


def bind_hover_highlight(tree: ttk.Treeview):
    # 简单悬停高亮：进入时设置 selection 到当前 pointer row
    def on_motion(event):
        try:
            row = tree.identify_row(event.y)
            if row:
                tree.selection_set(row)
        except Exception:
            pass
    tree.bind("<Motion>", on_motion) 