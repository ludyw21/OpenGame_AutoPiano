import tkinter as tk
from tkinter import ttk


class SkyPage:
    """光遇简洁页面：仅保留导入与播放、日志。

    通过传入的 `controller` 访问应用层方法：
    - _browse_midi / _browse_score
    - _start_auto_play / _stop_playback / _play_midi
    - _log_message （由外部追加到下方日志区）
    """

    def __init__(self, parent, controller=None):
        self.controller = controller
        self.frame = ttk.Frame(parent, padding=8)

        # 标题
        ttk.Label(self.frame, text="光遇演奏(3x5)", font=(None, 12, "bold")).pack(anchor=tk.W, pady=(0, 6))
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 6))

        # 3x5 键位提示（示例：上/中/下各5键）
        hint = (
            "上排: 1 2 3 4 5\n"
            "中排: Q W E R T\n"
            "下排: A S D F G\n"
            "注: 以上为示意布局，具体按键以策略映射为准"
        )
        ttk.Label(self.frame, text=hint, foreground="#666").pack(anchor=tk.W)

        # 导入与播放
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(8, 4))
        ttk.Button(bar, text="选择MIDI", width=12, command=self._on_browse_midi).pack(side=tk.LEFT)
        ttk.Button(bar, text="播放MIDI", width=10, command=self._on_play_midi).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="自动弹琴", width=10, command=self._on_auto_play).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="停止", width=8, command=self._on_stop).pack(side=tk.LEFT, padx=(6, 0))

        # 日志区域（独立于主右侧日志）
        log_box = ttk.LabelFrame(self.frame, text="日志", padding=6)
        log_box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.log_text = tk.Text(log_box, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # —— 控件回调：委托到 controller ——
    def _on_browse_midi(self):
        if self.controller and hasattr(self.controller, '_browse_midi'):
            self.controller._browse_midi()

    def _on_play_midi(self):
        if self.controller and hasattr(self.controller, '_play_midi'):
            self.controller._play_midi()

    def _on_auto_play(self):
        if self.controller and hasattr(self.controller, '_start_auto_play'):
            self.controller._start_auto_play()

    def _on_stop(self):
        if self.controller and hasattr(self.controller, '_stop_playback'):
            # 同时停止自动弹琴与MIDI播放
            try:
                self.controller._stop_auto_play()
            except Exception:
                pass
            self.controller._stop_playback()

    # —— 供外部调用：写入本页日志 ——
    def append_log(self, text: str):
        try:
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
        except Exception:
            pass
