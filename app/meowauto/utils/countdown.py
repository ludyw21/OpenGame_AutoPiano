import tkinter as tk
from typing import Callable, Optional

class CountdownTimer:
    def __init__(self, root: tk.Misc, seconds: int,
                 on_tick: Optional[Callable[[int], None]] = None,
                 on_finish: Optional[Callable[[], None]] = None,
                 on_cancel: Optional[Callable[[], None]] = None):
        self.root = root
        self.total = max(0, int(seconds))
        self.remaining = self.total
        self.on_tick = on_tick
        self.on_finish = on_finish
        self.on_cancel = on_cancel
        self._after_id: Optional[str] = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self):
        if self._active:
            return
        self._active = True
        self.remaining = self.total
        self._schedule_next()

    def cancel(self):
        if not self._active:
            return
        try:
            if self._after_id:
                self.root.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None
        self._active = False
        if self.on_cancel:
            try:
                self.on_cancel()
            except Exception:
                pass

    def _schedule_next(self):
        if not self._active:
            return
        if self.remaining <= 0:
            self._active = False
            if self.on_finish:
                try:
                    self.on_finish()
                except Exception:
                    pass
            return
        if self.on_tick:
            try:
                self.on_tick(self.remaining)
            except Exception:
                pass
        self.remaining -= 1
        self._after_id = self.root.after(1000, self._schedule_next) 