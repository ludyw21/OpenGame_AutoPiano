import tkinter as tk
from tkinter import ttk

class YuanShenPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=8)
        ttk.Label(self.frame, text="圆神", font=(None, 12, "bold")).pack(anchor=tk.W, pady=(0, 6))
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 6))
        ttk.Label(self.frame, text="空白页 · 敬请期待", foreground="#888").pack(anchor=tk.W) 