import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

try:
	from ttkbootstrap.tooltip import ToolTip
except Exception:
	ToolTip = None

class CountdownSettings:
	def __init__(self, parent, app, min_sec: int = 0, max_sec: int = 15):
		self.app = app
		self.min_sec = int(min_sec)
		self.max_sec = int(max_sec)
		self.frame = ttk.Frame(parent)
		# 读取默认值
		default = 5
		try:
			default = int(app.config.get('settings', {}).get('countdown_secs', 5))
		except Exception:
			default = 5
		default = max(self.min_sec, min(self.max_sec, default))
		self.var = tk.IntVar(value=default)
		self._last_valid = default
		# UI
		label = ttk.Label(self.frame, text="倒计时(s):")
		label.pack(side=tk.LEFT, padx=(8, 4))
		spin = ttk.Spinbox(self.frame, from_=self.min_sec, to=self.max_sec, width=4, textvariable=self.var, wrap=True)
		spin.pack(side=tk.LEFT)
		if ToolTip is not None:
			ToolTip(spin, text="自动弹琴前的准备时间")
		# 绑定变化，写入配置
		def _on_change(*_):
			try:
				raw = str(self.var.get())
				val = int(raw)
				if val < self.min_sec or val > self.max_sec:
					messagebox.showwarning("数值范围", f"请输入 {self.min_sec}-{self.max_sec} 的整数")
					val = max(self.min_sec, min(self.max_sec, val))
					self.var.set(val)
				self._last_valid = val
				app.config.setdefault('settings', {})['countdown_secs'] = val
				app.log(f"倒计时已设置为 {val} 秒", "INFO")
			except Exception:
				messagebox.showwarning("格式错误", f"请输入 {self.min_sec}-{self.max_sec} 的整数")
				self.var.set(self._last_valid)
		self.var.trace_add('write', _on_change)
		# 不在此处pack，由调用方决定
	
	def attach(self, **pack_kwargs):
		self.frame.pack(**pack_kwargs) 