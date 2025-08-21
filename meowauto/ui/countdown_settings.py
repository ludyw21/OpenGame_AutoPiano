import tkinter as tk
from tkinter import ttk

try:
	from ttkbootstrap.tooltip import ToolTip
except Exception:
	ToolTip = None

class CountdownSettings:
	def __init__(self, parent, app, min_sec: int = 0, max_sec: int = 15):
		self.app = app
		self.frame = ttk.Frame(parent)
		# 读取默认值
		default = 5
		try:
			default = int(app.config.get('settings', {}).get('countdown_secs', 5))
		except Exception:
			default = 5
		self.var = tk.IntVar(value=default)
		# UI
		label = ttk.Label(self.frame, text="倒计时(s):")
		label.pack(side=tk.LEFT, padx=(8, 4))
		spin = ttk.Spinbox(self.frame, from_=min_sec, to=max_sec, width=4, textvariable=self.var, wrap=True)
		spin.pack(side=tk.LEFT)
		if ToolTip is not None:
			ToolTip(spin, text="自动弹琴前的准备时间")
		# 绑定变化，写入配置
		def _on_change(*_):
			try:
				val = int(self.var.get())
				val = max(min_sec, min(max_sec, val))
				self.var.set(val)
				app.config.setdefault('settings', {})['countdown_secs'] = val
				# 反馈日志
				app.log(f"倒计时已设置为 {val} 秒", "INFO")
			except Exception:
				pass
		self.var.trace_add('write', _on_change)
		# 自身打包交给调用方
		self.frame.pack(side=tk.LEFT) 