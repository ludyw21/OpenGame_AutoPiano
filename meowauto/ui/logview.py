import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from datetime import datetime

class LogView:
    def __init__(self, parent, theme_mode_getter):
        self.frame = ttk.LabelFrame(parent, text="操作日志", padding="12")
        self.frame.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        self.theme_mode_getter = theme_mode_getter
        self.text = scrolledtext.ScrolledText(self.frame, height=16, width=100)
        self.text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(toolbar, text="清空日志", command=self.clear).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="保存日志", command=self.save).pack(side=tk.LEFT, padx=(5, 0))
        # 初次配色
        self.apply_theme()

    def apply_theme(self):
        mode = 'light'
        try:
            mode = self.theme_mode_getter() or 'light'
        except Exception:
            pass
        if mode == 'dark':
            self.text.configure(bg="#22262A", fg="#D6DEE7", insertbackground="#D6DEE7")
        else:
            self.text.configure(bg="#FFFFFF", fg="#1F2D3D", insertbackground="#1F2D3D")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "SUCCESS": "✅"}
        emoji = level_emoji.get(level, "ℹ️")
        line = f"[{timestamp}] {emoji} {message}\n"
        try:
            self.text.insert(tk.END, line)
            self.text.see(tk.END)
            # 限制行数
            lines = self.text.get("1.0", tk.END).split('\n')
            if len(lines) > 1000:
                self.text.delete("1.0", f"{len(lines)-1000}.0")
        except Exception:
            try:
                print(line.strip())
            except Exception:
                pass

    def clear(self):
        try:
            self.text.delete("1.0", tk.END)
        except Exception:
            pass

    def save(self):
        try:
            filename = filedialog.asksaveasfilename(
                title="保存日志",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if not filename:
                return
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", tk.END))
        except Exception:
            pass 