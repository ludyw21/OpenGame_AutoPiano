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

    def _browse_audio_folder(self):
        folder = filedialog.askdirectory(title="选择批量转换的音频文件夹")
        if folder:
            self._widgets['batch_folder_var'].set(folder)

    def _browse_output_file(self):
        init = self._widgets['audio_path_var'].get().strip()
        suggested = ""
        if init:
            base = os.path.splitext(os.path.basename(init))[0] + ".mid"
            suggested = os.path.join(os.path.dirname(init), base)
        path = filedialog.asksaveasfilename(
            title="选择MIDI输出文件",
            defaultextension=".mid",
            initialfile=os.path.basename(suggested) if suggested else None,
            filetypes=[("MIDI文件", ".mid"), ("所有文件", "*.*")]
        )
        if path:
            self._widgets['output_path_var'].set(path)

    def _do_convert(self):
        self._ensure_converter()
        if not self.converter:
            messagebox.showerror("错误", "音频转换器未初始化")
            return
        audio = self._widgets['audio_path_var'].get().strip()
        output = self._widgets['output_path_var'].get().strip()
        if not audio:
            messagebox.showwarning("提示", "请先选择音频文件")
            return
        if not output:
            # 若未指定，默认与音频同目录同名 .mid
            base = os.path.splitext(os.path.basename(audio))[0] + ".mid"
            output = os.path.join(os.path.dirname(audio), base)
            self._widgets['output_path_var'].set(output)
        btn: ttk.Button = self._widgets['btn_convert']
        btn.configure(state=tk.DISABLED)
        try:
            def _done(success: bool, outp: str | None):
                try:
                    btn.configure(state=tk.NORMAL)
                except Exception:
                    pass
                if success:
                    try:
                        self.controller._log_message(f"转换完成: {outp}", "SUCCESS")
                    except Exception:
                        pass
                    messagebox.showinfo("完成", f"转换成功:\n{outp}")
                else:
                    try:
                        self.controller._log_message("转换失败", "ERROR")
                    except Exception:
                        pass
                    messagebox.showerror("失败", "转换失败，请查看右侧日志")

            # 异步转换
            self.converter.convert_audio_to_midi_async(audio, output, complete_callback=_done)
            try:
                self.controller._log_message(f"开始转换: {audio}", "INFO")
            except Exception:
                pass
        except Exception as e:
            try:
                self.controller._log_message(f"启动转换失败: {e}", "ERROR")
            except Exception:
                pass
            btn.configure(state=tk.NORMAL)

    def _do_batch_convert(self):
        self._ensure_converter()
        if not self.converter:
            messagebox.showerror("错误", "音频转换器未初始化")
            return
        folder = self._widgets['batch_folder_var'].get().strip()
        if not folder:
            messagebox.showwarning("提示", "请先选择批量转换的文件夹")
            return
        try:
            result = self.converter.batch_convert(folder)
            if result.get("success"):
                succ = result.get("success_count", 0)
                total = result.get("total", 0)
                outdir = result.get("output_dir", folder)
                try:
                    self.controller._log_message(f"批量转换完成: {succ}/{total} -> {outdir}", "SUCCESS")
                except Exception:
                    pass
                messagebox.showinfo("完成", f"批量转换完成: {succ}/{total}\n输出目录: {outdir}")
            else:
                msg = result.get("error", "批量转换失败")
                try:
                    self.controller._log_message(msg, "ERROR")
                except Exception:
                    pass
                messagebox.showerror("失败", msg)
        except Exception as e:
            try:
                self.controller._log_message(f"批量转换失败: {e}", "ERROR")
            except Exception:
                pass
            messagebox.showerror("失败", f"批量转换失败: {e}")

    # --- 页面装载 ---
    def mount(self, left: ttk.Frame, right: ttk.Frame):
        # 左侧：单文件转换、批量转换
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
        single = ttk.LabelFrame(content, text="单文件转换", padding=10)
        single.grid(row=0, column=0, sticky=tk.NSEW, padx=6, pady=6)
        ttk.Label(single, text="音频文件:").grid(row=0, column=0, sticky=tk.W)
        audio_path_var = tk.StringVar()
        audio_entry = ttk.Entry(single, textvariable=audio_path_var, width=52)
        audio_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6,6))
        ttk.Button(single, text="浏览", command=self._browse_audio_file).grid(row=0, column=2)
        ttk.Label(single, text="输出MIDI:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
        output_path_var = tk.StringVar()
        output_entry = ttk.Entry(single, textvariable=output_path_var, width=52)
        output_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(6,6), pady=(8,0))
        ttk.Button(single, text="选择", command=self._browse_output_file).grid(row=1, column=2, pady=(8,0))
        btn_convert = ttk.Button(single, text="开始转换", command=self._do_convert)
        btn_convert.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(10,0))

        single.columnconfigure(1, weight=1)

        # 批量转换
        batch = ttk.LabelFrame(content, text="批量转换", padding=10)
        batch.grid(row=1, column=0, sticky=tk.NSEW, padx=6, pady=(0,6))
        ttk.Label(batch, text="音频文件夹:").grid(row=0, column=0, sticky=tk.W)
        batch_folder_var = tk.StringVar()
        batch_entry = ttk.Entry(batch, textvariable=batch_folder_var, width=52)
        batch_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6,6))
        ttk.Button(batch, text="浏览", command=self._browse_audio_folder).grid(row=0, column=2)
        ttk.Button(batch, text="开始批量转换", command=self._do_batch_convert).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(10,0))

        batch.columnconfigure(1, weight=1)

        # 保存句柄
        self._widgets['audio_path_var'] = audio_path_var
        self._widgets['output_path_var'] = output_path_var
        self._widgets['batch_folder_var'] = batch_folder_var
        self._widgets['btn_convert'] = btn_convert

        # 右侧：仅保留“系统日志”，隐藏“MIDI解析/事件表”
        try:
            self.controller._create_right_pane(right, show_midi_parse=False, show_events=False, show_logs=True)
        except Exception:
            pass

        self._mounted = True

    def unmount(self):
        self._mounted = False
