#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    # 复用 Router 的 BasePage（若不可用，则使用内部占位类）
    from .. import BasePage  # type: ignore
except Exception:
    class BasePage:  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...


class Audio2MidiPage(BasePage):
    """音频转MIDI 独立工具页面"""
    def __init__(self, controller):
        self.controller = controller
        self._mounted = False
        self._widgets = {}
        self.converter = None

    # --- 内部：工具依赖 ---
    def _ensure_converter(self):
        if self.converter is not None:
            return
        try:
            from meowauto.core import Logger
            from meowauto.audio.converter import AudioConverter
            logger = getattr(self.controller, 'logger', None) or Logger()
            self.converter = AudioConverter(logger)
        except Exception as e:
            try:
                self.controller._log_message(f"初始化音频转换器失败: {e}", "ERROR")
            except Exception:
                pass
            self.converter = None

    # --- 事件回调 ---
    def _browse_audio_file(self):
        patterns = [
            ("音频文件", ".mp3 .wav .flac .m4a .aac .ogg"),
            ("所有文件", "*.*"),
        ]
        path = filedialog.askopenfilename(title="选择音频文件", filetypes=patterns)
        if path:
            self._widgets['audio_path_var'].set(path)



    def _do_convert(self):
        # 统一入口：严格校验后再提示
        audio = self._widgets['audio_path_var'].get().strip()
        if not audio:
            messagebox.showwarning("提示", "请先选择音频文件")
            return
        
        # 自动生成输出路径
        base = os.path.splitext(os.path.basename(audio))[0] + ".mid"
        output = os.path.join(os.path.dirname(audio), base)

        btn: ttk.Button = self._widgets['btn_convert']
        try:
            btn.configure(state=tk.DISABLED)
        except Exception:
            pass
        try:
            if hasattr(self.controller, '_log_message'):
                self.controller._log_message(f"开始转换: {audio}", "INFO")
                try:
                    if hasattr(self.controller, 'ui_manager'):
                        self.controller.ui_manager.set_status("正在转换...")
                except Exception:
                    pass
        except Exception:
            pass

        def _worker():
            ok = False
            outp = output
            err_msg = None
            logs = {}
            try:
                try:
                    from meowauto.audio.audio2midi import convert_audio_to_midi
                    ok, outp, err_msg, logs = convert_audio_to_midi(audio, output, pianotrans_dir="PianoTrans-v1.0")
                except Exception as e:
                    ok = False
                    err_msg = f"入口不可用: {e}"
            finally:
                def _finish():
                    try:
                        try:
                            btn.configure(state=tk.NORMAL)
                        except Exception:
                            pass
                        # 打印日志
                        try:
                            if hasattr(self.controller, '_log_message'):
                                if logs.get('stdout'):
                                    self.controller._log_message(f"PianoTrans输出: {logs['stdout']}", "INFO")
                                if logs.get('stderr'):
                                    self.controller._log_message(f"PianoTrans错误: {logs['stderr']}", "ERROR")
                                if logs.get('elapsed'):
                                    self.controller._log_message(f"转换耗时: {logs['elapsed']:.1f}s", "INFO")
                        except Exception:
                            pass

                        if ok and outp and os.path.exists(outp):
                            try:
                                if hasattr(self.controller, '_log_message'):
                                    self.controller._log_message(f"转换完成: {outp}", "SUCCESS")
                                if hasattr(self.controller, 'ui_manager'):
                                    self.controller.ui_manager.set_status("音频转换完成")
                            except Exception:
                                pass
                            messagebox.showinfo("完成", f"转换成功:\n{outp}")
                        else:
                            if hasattr(self.controller, '_log_message'):
                                self.controller._log_message(f"转换失败: {err_msg or '未知错误'}", "ERROR")
                            try:
                                if hasattr(self.controller, 'ui_manager'):
                                    self.controller.ui_manager.set_status("音频转换失败")
                            except Exception:
                                pass
                            messagebox.showerror("失败", f"转换失败，请查看日志\n{err_msg or ''}")
                    except Exception:
                        pass
                try:
                    # 回到主线程
                    if hasattr(self.controller, 'root') and self.controller.root:
                        self.controller.root.after(0, _finish)
                    else:
                        # 若无法回调到主线程，也直接调用
                        _finish()
                except Exception:
                    _finish()

        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:
            try:
                if hasattr(self.controller, '_log_message'):
                    self.controller._log_message(f"启动转换失败: {e}", "ERROR")
            except Exception:
                pass
            try:
                btn.configure(state=tk.NORMAL)
            except Exception:
                pass


    # --- 页面装载 ---
    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # 左侧：单文件转换
        header = ttk.Frame(left)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="音频转MIDI", font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)

        content = ttk.Frame(left)
        content.pack(fill=tk.BOTH, expand=True)
        try:
            content.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        # 单文件转换
        single = ttk.LabelFrame(content, text="音频转MIDI", padding=10)
        single.grid(row=0, column=0, sticky=tk.NSEW, padx=6, pady=6)
        ttk.Label(single, text="音频文件:").grid(row=0, column=0, sticky=tk.W)
        audio_path_var = tk.StringVar()
        audio_entry = ttk.Entry(single, textvariable=audio_path_var, width=52)
        audio_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6,6))
        ttk.Button(single, text="浏览", command=self._browse_audio_file).grid(row=0, column=2)
        
        # 添加说明文本
        info_label = ttk.Label(single, text="输出文件将自动生成在音频文件同目录下", 
                              font=("Microsoft YaHei", 9), foreground="gray")
        info_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(8,0))
        
        btn_convert = ttk.Button(single, text="开始转换", command=self._do_convert)
        btn_convert.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(10,0))

        single.columnconfigure(1, weight=1)

        # 保存句柄
        self._widgets['audio_path_var'] = audio_path_var
        self._widgets['btn_convert'] = btn_convert

        # 右侧：仅保留“系统日志”，隐藏“MIDI解析/事件表”
        try:
            self.controller._create_right_pane(right, show_midi_parse=False, show_events=False, show_logs=True)
        except Exception:
            pass

        self._mounted = True

    def unmount(self):
        self._mounted = False
