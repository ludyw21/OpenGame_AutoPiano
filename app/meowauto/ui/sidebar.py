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
        self._collapsed = False
        self._expanded_width = width
        self._anim_job = None  # 动画句柄
        self._animating = False
        # 新增：宽度回调（供父窗口同步 Toplevel 几何，实现真正的窗口动画）
        self._on_width = on_width or (lambda w: None)

        # 容器
        self._container = ttk.Frame(self.frame)
        self._container.pack(fill=tk.BOTH, expand=True)

        # 折叠/展开按钮
        self._toggle_btn = ttk.Button(self._container, text="≡", width=3, command=self.toggle)
        self._toggle_btn.pack(padx=4, pady=6)
        if ToolTip:
            ToolTip(self._toggle_btn, text="折叠/展开侧边栏")

        # 模式切换（暂不提供：合奏后续实现）
        # 占位分隔
        ttk.Separator(self._container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))

        # 乐器板块
        inst_label = ttk.Label(self._container, text="乐器板块", anchor=tk.W)
        inst_label.pack(padx=6, pady=(2, 0), fill=tk.X)
        self.inst_frame = ttk.Frame(self._container)
        self.inst_frame.pack(padx=6, pady=4, fill=tk.X)
        ttk.Button(self.inst_frame, text="电子琴", command=lambda: self.on_action("inst-epiano")).pack(padx=0, pady=4, fill=tk.X)
        ttk.Button(self.inst_frame, text="吉他", command=lambda: self.on_action("inst-guitar")).pack(padx=0, pady=4, fill=tk.X)
        ttk.Button(self.inst_frame, text="贝斯", command=lambda: self.on_action("inst-bass")).pack(padx=0, pady=4, fill=tk.X)
        ttk.Button(self.inst_frame, text="架子鼓", command=lambda: self.on_action("inst-drums")).pack(padx=0, pady=4, fill=tk.X)

        # 工具分组
        ttk.Separator(self._container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))
        tools_label = ttk.Label(self._container, text="工具", anchor=tk.W)
        tools_label.pack(padx=6, pady=(2, 0), fill=tk.X)
        self.tools_frame = ttk.Frame(self._container)
        self.tools_frame.pack(padx=6, pady=4, fill=tk.X)
        ttk.Button(self.tools_frame, text="音频转MIDI", command=lambda: self.on_action("tool-audio2midi")).pack(padx=0, pady=4, fill=tk.X)

        # 常用按钮（精简后暂留为空，保留结构便于后续扩展）
        self._buttons = []

        # 初始宽度
        self.frame.update_idletasks()
        self.frame.configure(width=self._expanded_width)

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

    def toggle(self):
        # 取消未完成动画
        if self._anim_job is not None:
            try:
                self.frame.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

        self._collapsed = not self._collapsed
        start_w = max(1, int(self.frame.winfo_width() or (self._expanded_width if not self._collapsed else 40)))
        end_w = 40 if self._collapsed else self._expanded_width

        # 折叠前隐藏内容；展开则动画结束后再恢复
        if self._collapsed:
            self._hide_contents()
        else:
            # 先确保容器可见，内容稍后恢复
            pass

        self._animate_width(start_w, end_w, duration_ms=160, steps=8, on_done=self._on_anim_done)

    # --- 内部：动画与内容显示控制 ---
    def _hide_contents(self):
        for b in self._buttons:
            try:
                b.pack_forget()
            except Exception:
                pass
        for w in (getattr(self, 'inst_frame', None), getattr(self, 'tools_frame', None)):
            try:
                if w:
                    w.pack_forget()
            except Exception:
                pass

    def _show_contents(self):
        try:
            self.inst_frame.pack(padx=6, pady=4, fill=tk.X)
        except Exception:
            pass
        try:
            self.tools_frame.pack(padx=6, pady=4, fill=tk.X)
        except Exception:
            pass
        for b in self._buttons:
            try:
                b.pack(padx=6, pady=4, fill=tk.X)
            except Exception:
                pass

    def _on_anim_done(self):
        if not self._collapsed:
            self._show_contents()
        self.frame.update_idletasks()
        self._animating = False
        self._anim_job = None
        try:
            # 动画结束后回报最终宽度
            w = int(self.frame.winfo_width() or (self._expanded_width if not self._collapsed else 40))
            self._on_width(w)
        except Exception:
            pass

    def _animate_width(self, start: int, end: int, *, duration_ms: int = 160, steps: int = 8, on_done=None):
        if start == end:
            if on_done:
                on_done()
            return
        self._animating = True
        delta = (end - start) / float(max(1, steps))
        cur = {'i': 0, 'w': float(start)}

        def _step():
            if cur['i'] >= steps:
                # 动画结束：一次性通知外部更新容器宽度，避免频繁重排
                try:
                    self._on_width(int(end))
                except Exception:
                    pass
                if on_done:
                    on_done()
                return
            cur['w'] += delta
            cur['i'] += 1
            # 内部帧宽度渐变
            try:
                self.frame.configure(width=int(cur['w']))
            except Exception:
                pass
            # 每步通知外部更新容器列宽，实现平滑动画
            try:
                self._on_width(int(cur['w']))
            except Exception:
                pass
            self._anim_job = self.frame.after(int(duration_ms / max(1, steps)), _step)

        _step()