#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python 3.12兼容版自动弹琴软件 (PYW版本 - 无控制台窗口)
支持音频转MIDI、MIDI播放和自动弹琴功能
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
import sys
import subprocess
import json
import mido
import pygame
import numpy as np
from PIL import Image, ImageTk
import keyboard
import mouse
from datetime import datetime
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# 时间戳正则表达式：形如 [mm:ss.xxx]，毫秒 .xxx 可省略
TS_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")

# 允许的音符 token 正则表达式
TOKEN_NOTE_RE = re.compile(r"(?:(?:[LMH][1-7])|(?:C|Dm|Em|F|G|Am|G7))")

@dataclass
class Event:
    """乐谱事件"""
    start: float          # 按下时间（秒）
    end: float            # 释放时间（秒），若与 start 相同表示立刻松开（tap）
    keys: List[str]       # 同步触发的一组按键（和弦/多音）

def _ts_match_to_seconds(m: re.Match) -> float:
    """将时间戳匹配转换为秒数"""
    mm = int(m.group(1))
    ss = int(m.group(2))
    ms = int((m.group(3) or "0").ljust(3, "0"))
    return mm * 60 + ss + ms / 1000.0

def parse_line(line: str) -> List[Event]:
    """解析一行乐谱：
    1) 延长音： [start][end] TOKENS  -> 在 start 按下，在 end 释放
    2) 多个独立时间： [t1][t2] TOKENS 但若 t1==t2 或未按升序，可视为两个独立 tap
    3) 单时间戳： [t] TOKENS -> tap
    4) 兼容旧写法：多个时间戳后跟 token -> 分别 tap
    """
    ts = list(TS_RE.finditer(line))
    if not ts:
        return []
    
    tail_start = ts[-1].end()
    tokens_str = line[tail_start:].strip()
    if not tokens_str:
        return []
    
    tokens = tokens_str.split()
    valid_tokens = [tok for tok in tokens if TOKEN_NOTE_RE.fullmatch(tok)]
    if not valid_tokens:
        return []

    # token -> key 映射
    keys: List[str] = []
    for tok in valid_tokens:
        if tok[0] in ("L", "M", "H"):
            octave = tok[0]
            num = tok[1]
            if octave == "L": 
                keys.append('a' if num == '1' else 's' if num == '2' else 'd' if num == '3' else 
                           'f' if num == '4' else 'g' if num == '5' else 'h' if num == '6' else 'j')
            elif octave == "M": 
                keys.append('q' if num == '1' else 'w' if num == '2' else 'e' if num == '3' else 
                           'r' if num == '4' else 't' if num == '5' else 'y' if num == '6' else 'u')
            else:  # H
                keys.append('1' if num == '1' else '2' if num == '2' else '3' if num == '3' else 
                           '4' if num == '4' else '5' if num == '5' else '6' if num == '6' else '7')
        else:
            # 和弦→底栏单键（与游戏键位一致）
            chord_map = {"C": "z", "Dm": "x", "Em": "c", "F": "v", "G": "b", "Am": "n", "G7": "m"}
            key = chord_map.get(tok)
            if key:
                keys.append(key)

    events: List[Event] = []
    
    # 延长音情形：恰好两个时间戳且第二个时间 > 第一个
    if len(ts) == 2:
        t1 = _ts_match_to_seconds(ts[0])
        t2 = _ts_match_to_seconds(ts[1])
        if t2 > t1:  # 视为延长音
            events.append(Event(start=t1, end=t2, keys=keys.copy()))
            return events
    
    # 其它：全部视为独立 tap
    for m in ts:
        t = _ts_match_to_seconds(m)
        events.append(Event(start=t, end=t, keys=keys.copy()))
    
    return events

def parse_score(text: str) -> List[Event]:
    """解析整个乐谱文本"""
    events: List[Event] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        events.extend(parse_line(line))
    
    # 按开始时间排序
    events.sort(key=lambda e: e.start)
    return events

class KeySender:
    """按键发送器，管理按键状态"""
    def __init__(self):
        self.active_count = {}
    
    def press(self, keys):
        """按下按键"""
        for k in keys:
            cnt = self.active_count.get(k, 0) + 1
            self.active_count[k] = cnt
            if cnt == 1:  # 首次按下
                try:
                    keyboard.press(k)
                except Exception:
                    pass
    
    def release(self, keys):
        """释放按键"""
        for k in keys:
            cnt = self.active_count.get(k, 0)
            if cnt <= 0:
                continue
            cnt -= 1
            self.active_count[k] = cnt
            if cnt == 0:
                try:
                    keyboard.release(k)
                except Exception:
                    pass
    
    def release_all(self):
        """释放所有按键"""
        for k in list(self.active_count.keys()):
            while self.active_count.get(k, 0) > 0:
                self.release([k])

class Py312AutoPiano:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Python 3.12兼容版自动弹琴软件 v1.0 (管理员模式)")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # 初始化配置
        self.config = self.load_config()
        
        # 设置图标和样式
        self.setup_ui()
        
        # 初始化变量
        self.midi_file = None
        self.is_playing = False
        self.is_auto_playing = False
        self.playback_thread = None
        self.auto_play_thread = None
        self.current_tempo = 120
        self.current_volume = 0.7
        
        # 加载键位映射
        self.load_key_mappings()
        
        # 初始化pygame音频
        try:
            pygame.mixer.init()
        except:
            pass
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 创建输出目录
        self.create_directories()
        
        # 显示管理员权限提示
        self.show_admin_notice()
        
    def show_admin_notice(self):
        """显示管理员权限提示"""
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                self.log("✓ 已获得管理员权限，自动弹琴功能可用", "SUCCESS")
            else:
                self.log("⚠️ 未获得管理员权限，自动弹琴功能可能受限", "WARNING")
                messagebox.showwarning("权限提示", "建议以管理员权限运行以获得最佳体验")
        except:
            pass
        
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                # 创建默认配置
                default_config = {
                    "key_mapping": {
                        "low_octave": {"L1": "a", "L2": "s", "L3": "d", "L4": "f", "L5": "g", "L6": "h", "L7": "j"},
                        "middle_octave": {"M1": "q", "M2": "w", "M3": "e", "M4": "r", "M5": "t", "M6": "y", "M7": "u"},
                        "high_octave": {"H1": "1", "H2": "2", "H3": "3", "H4": "4", "H5": "5", "H6": "6", "H7": "7"},
                        "chords": {"C": "z", "Dm": "x", "Em": "c", "F": "v", "G": "b", "Am": "n", "G7": "m"}
                    },
                    "settings": {
                        "auto_play_delay": 0.001,
                        "note_duration_multiplier": 1.0,
                        "enable_logging": True,
                        "default_volume": 0.7
                    }
                }
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
    
    def create_directories(self):
        """创建必要的目录"""
        dirs = ['output', 'temp', 'logs']
        for dir_name in dirs:
            if not os.path.exists(dir_name):
                os.makedirs(dir_name)
    
    def load_key_mappings(self):
        """加载键位映射"""
        if 'key_mapping' in self.config:
            self.key_mapping = {}
            for category, mappings in self.config['key_mapping'].items():
                self.key_mapping.update(mappings)
        else:
            # 默认键位映射
            self.key_mapping = {
                'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
                'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
                'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7',
                'C': 'z', 'Dm': 'x', 'Em': 'c', 'F': 'v', 'G': 'b', 'Am': 'n', 'G7': 'm'
            }
        
        # 音符到键位的映射
        self.note_mapping = {
            'C': 'L1', 'C#': 'L1', 'Db': 'L1',
            'D': 'L2', 'D#': 'L2', 'Eb': 'L2',
            'E': 'L3',
            'F': 'L4', 'F#': 'L4', 'Gb': 'L4',
            'G': 'L5', 'G#': 'L5', 'Ab': 'L5',
            'A': 'L6', 'A#': 'L6', 'Bb': 'L6',
            'B': 'L7',
            'C4': 'M1', 'C#4': 'M1', 'Db4': 'M1',
            'D4': 'M2', 'D#4': 'M2', 'Eb4': 'M2',
            'E4': 'M3',
            'F4': 'M4', 'F#4': 'M4', 'Gb4': 'M4',
            'G4': 'M5', 'G#4': 'M5', 'Ab4': 'M5',
            'A4': 'M6', 'A#4': 'M6', 'Bb4': 'M6',
            'B4': 'M7',
            'C5': 'H1', 'C#5': 'H1', 'Db5': 'H1',
            'D5': 'H2', 'D#5': 'H2', 'Eb5': 'H2',
            'E5': 'H3',
            'F5': 'H4', 'F#5': 'H4', 'Gb5': 'H4',
            'G5': 'H5', 'G#5': 'H5', 'Ab5': 'H5',
            'A5': 'H6', 'A#5': 'H6', 'Bb5': 'H6',
            'B5': 'H7'
        }
        
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="🎹 Python 3.12兼容版自动弹琴软件 (管理员模式)", font=("Microsoft YaHei", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="文件选择", padding="10")
        file_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="MP3文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.mp3_path_var = tk.StringVar()
        mp3_entry = ttk.Entry(file_frame, textvariable=self.mp3_path_var, width=60)
        mp3_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="浏览", command=self.browse_mp3).grid(row=0, column=2)
        
        # 转换按钮
        convert_frame = ttk.Frame(file_frame)
        convert_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(convert_frame, text="音频转MIDI", command=self.convert_mp3_to_midi).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="选择MIDI文件", command=self.browse_midi).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="加载乐谱文件", command=self.load_score_file).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="检查PianoTrans", command=self.check_pianotrans).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="批量转换", command=self.batch_convert).pack(side=tk.LEFT, padx=(0, 10))
        
        # MIDI文件信息
        midi_frame = ttk.LabelFrame(main_frame, text="MIDI文件信息", padding="10")
        midi_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        midi_frame.columnconfigure(1, weight=1)
        
        ttk.Label(midi_frame, text="MIDI文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.midi_path_var = tk.StringVar()
        midi_entry = ttk.Entry(midi_frame, textvariable=self.midi_path_var, width=60)
        midi_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 播放控制区域
        control_frame = ttk.LabelFrame(main_frame, text="播放控制", padding="10")
        control_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 播放控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.play_button = ttk.Button(button_frame, text="播放", command=self.play_midi)
        self.play_button.pack(pady=(0, 5))
        
        self.pause_button = ttk.Button(button_frame, text="暂停", command=self.pause_midi, state=tk.DISABLED)
        self.pause_button.pack(pady=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_midi, state=tk.DISABLED)
        self.stop_button.pack(pady=(0, 5))
        
        self.auto_play_button = ttk.Button(button_frame, text="自动弹琴", command=self.toggle_auto_play)
        self.auto_play_button.pack(pady=(0, 5))
        
        # 控制参数
        param_frame = ttk.Frame(control_frame)
        param_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))
        
        ttk.Label(param_frame, text="速度:").pack()
        self.tempo_var = tk.DoubleVar(value=1.0)
        tempo_scale = ttk.Scale(param_frame, from_=0.5, to=2.0, variable=self.tempo_var, orient=tk.HORIZONTAL)
        tempo_scale.pack()
        
        ttk.Label(param_frame, text="音量:").pack()
        self.volume_var = tk.DoubleVar(value=0.7)
        volume_scale = ttk.Scale(param_frame, from_=0.0, to=1.0, variable=self.volume_var, orient=tk.HORIZONTAL)
        volume_scale.pack()
        
        # 进度条
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(20, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # 时间显示
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        time_label = ttk.Label(progress_frame, textvariable=self.time_var)
        time_label.pack()
        
        # 键位映射显示
        mapping_frame = ttk.LabelFrame(main_frame, text="键位映射", padding="10")
        mapping_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 创建键位映射表格
        self.create_key_mapping_table(mapping_frame)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="10")
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        # 日志工具栏
        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(log_toolbar, text="清空日志", command=self.clear_log).pack(side=tk.LEFT)
        ttk.Button(log_toolbar, text="保存日志", command=self.save_log).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(log_toolbar, text="导出配置", command=self.export_config).pack(side=tk.LEFT, padx=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=100)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def create_key_mapping_table(self, parent):
        """创建键位映射表格"""
        # 低音
        ttk.Label(parent, text="低音 (L1-L7):", font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        for i, (note, key) in enumerate([('L1', 'a'), ('L2', 's'), ('L3', 'd'), ('L4', 'f'), ('L5', 'g'), ('L6', 'h'), ('L7', 'j')]):
            ttk.Label(parent, text=f"{note}→{key}").grid(row=0, column=i+1, padx=5)
        
        # 中音
        ttk.Label(parent, text="中音 (M1-M7):", font=("Microsoft YaHei", 10, "bold")).grid(row=1, column=0, sticky=tk.W, padx=(0, 20), pady=(10, 0))
        for i, (note, key) in enumerate([('M1', 'q'), ('M2', 'w'), ('M3', 'e'), ('M4', 'r'), ('M5', 't'), ('M6', 'y'), ('M7', 'u')]):
            ttk.Label(parent, text=f"{note}→{key}").grid(row=1, column=i+1, padx=5, pady=(10, 0))
        
        # 高音
        ttk.Label(parent, text="高音 (H1-H7):", font=("Microsoft YaHei", 10, "bold")).grid(row=2, column=0, sticky=tk.W, padx=(0, 20), pady=(10, 0))
        for i, (note, key) in enumerate([('H1', '1'), ('H2', '2'), ('H3', '3'), ('H4', '4'), ('H5', '5'), ('H6', '6'), ('H7', '7')]):
            ttk.Label(parent, text=f"{note}→{key}").grid(row=2, column=i+1, padx=5, pady=(10, 0))
        
        # 和弦
        ttk.Label(parent, text="和弦:", font=("Microsoft YaHei", 10, "bold")).grid(row=3, column=0, sticky=tk.W, padx=(0, 20), pady=(10, 0))
        for i, (chord, key) in enumerate([('C', 'z'), ('Dm', 'x'), ('Em', 'c'), ('F', 'v'), ('G', 'b'), ('Am', 'n'), ('G7', 'm')]):
            ttk.Label(parent, text=f"{chord}→{key}").grid(row=3, column=i+1, padx=5, pady=(10, 0))
    
    def log(self, message, level="INFO"):
        """添加日志信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "SUCCESS": "✅"}
        emoji = level_emoji.get(level, "ℹ️")
        
        log_message = f"[{timestamp}] {emoji} {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        
        # 限制日志行数
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 1000:
            self.log_text.delete("1.0", f"{len(lines)-1000}.0")
        
        self.root.update_idletasks()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", tk.END)
        self.log("日志已清空", "INFO")
    
    def save_log(self):
        """保存日志到文件"""
        try:
            filename = f"logs/log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", tk.END))
            self.log(f"日志已保存到: {filename}", "SUCCESS")
        except Exception as e:
            self.log(f"保存日志失败: {str(e)}", "ERROR")
    
    def export_config(self):
        """导出配置"""
        try:
            filename = filedialog.asksaveasfilename(
                title="导出配置",
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
            )
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
                self.log(f"配置已导出到: {filename}", "SUCCESS")
        except Exception as e:
            self.log(f"导出配置失败: {str(e)}", "ERROR")
    
    def browse_mp3(self):
        """浏览MP3文件"""
        file_path = filedialog.askopenfilename(
            title="选择MP3文件",
            filetypes=[("MP3文件", "*.mp3"), ("所有文件", "*.*")]
        )
        if file_path:
            self.mp3_path_var.set(file_path)
            self.log(f"已选择MP3文件: {file_path}", "INFO")
    
    def browse_midi(self):
        """浏览MIDI文件"""
        file_path = filedialog.askopenfilename(
            title="选择MIDI文件",
            filetypes=[("MIDI文件", "*.mid;*.midi"), ("所有文件", "*.*")]
        )
        if file_path:
            self.midi_path_var.set(file_path)
            self.midi_file = file_path
            self.log(f"已选择MIDI文件: {file_path}", "INFO")
            self.analyze_midi_file(file_path)
            
            # 询问是否转换为LRCp格式
            if messagebox.askyesno("转换提示", "是否将MIDI文件转换为LRCp乐谱格式？"):
                self.convert_midi_to_lrcp(file_path)
    
    def convert_midi_to_lrcp(self, midi_path):
        """将MIDI文件转换为LRCp格式"""
        try:
            self.log("开始转换MIDI到LRCp格式...", "INFO")
            self.status_var.set("正在转换MIDI...")
            
            # 在新线程中执行转换
            convert_thread = threading.Thread(target=self._convert_midi_thread, args=(midi_path,))
            convert_thread.daemon = True
            convert_thread.start()
            
        except Exception as e:
            self.log(f"转换失败: {str(e)}", "ERROR")
    
    def _convert_midi_thread(self, midi_path):
        """在后台线程中转换MIDI - 使用改进的解析方法"""
        try:
            # 尝试使用pretty_midi库（如果可用）
            try:
                import pretty_midi
                self._convert_with_pretty_midi(midi_path)
                return
            except ImportError:
                self.log("pretty_midi库不可用，使用mido库", "INFO")
                self._convert_with_mido(midi_path)
                
        except Exception as e:
            error_msg = f"MIDI转换失败: {str(e)}"
            self.root.after(0, lambda: self._conversion_error(error_msg))
    
    def _convert_with_pretty_midi(self, midi_path):
        """使用pretty_midi库转换MIDI"""
        try:
            import pretty_midi
            
            pm = pretty_midi.PrettyMIDI(midi_path)
            blocks = []
            
            # 提取音符块
            for inst in pm.instruments:
                for note in inst.notes:
                    # 使用半音折叠 3×7 映射
                    token = self._token_from_midi_note(note.pitch)
                    if token:
                        start = round(note.start, 3)
                        end = round(note.end, 3)
                        if end < start:
                            end = start
                        blocks.append((start, end, token))
            
            # 分组处理
            groups = {}
            for start, end, token in blocks:
                key = (start, end)
                groups.setdefault(key, []).append(token)
            
            # 和弦识别：基于度数集合
            def _detect_chord_label(tokens: List[str]) -> Optional[str]:
                digits = {t[1] for t in tokens if isinstance(t, str) and len(t) == 2 and t[0] in ('L','M','H') and t[1].isdigit()}
                if not digits:
                    return None
                if digits == {'1','3','5'}:
                    return 'C'
                if digits == {'2','4','6'}:
                    return 'Dm'
                if digits == {'3','5','7'}:
                    return 'Em'
                if digits == {'4','6','1'}:
                    return 'F'
                if digits == {'5','7','2'}:
                    return 'G'
                if digits == {'6','1','3'}:
                    return 'Am'
                if digits == {'5','7','2','4'}:
                    return 'G7'
                return None
            
            # 生成LRCp内容
            lrcp_content = f"# 从MIDI文件转换: {os.path.basename(midi_path)}\n"
            lrcp_content += f"# 转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            lrcp_content += "# 格式: [开始时间][结束时间] 音符\n\n"
            
            # 按时间排序
            sorted_groups = sorted(groups.items(), key=lambda x: (x[0][0], x[0][1]))
            
            for (start, end), tokens in sorted_groups:
                tokens.sort()
                start_str = self._seconds_to_timestamp(start)
                end_str = self._seconds_to_timestamp(end)
                label = _detect_chord_label(tokens)
                payload = label if label else ' '.join(tokens)
                if abs(end - start) < 0.001:  # 短音
                    line = f"[{start_str}] {payload}\n"
                else:  # 延长音
                    line = f"[{start_str}][{end_str}] {payload}\n"
                lrcp_content += line
            
            # 保存LRCp文件
            output_dir = os.path.dirname(midi_path)
            output_name = os.path.splitext(os.path.basename(midi_path))[0]
            lrcp_output = os.path.join(output_dir, f"{output_name}.lrcp")
            
            with open(lrcp_output, "w", encoding="utf-8") as f:
                f.write(lrcp_content)
            
            # 转换完成
            self.root.after(0, lambda: self._midi_conversion_complete(lrcp_output, len(blocks)))
            
        except Exception as e:
            error_msg = f"pretty_midi转换失败: {str(e)}"
            self.root.after(0, lambda: self._conversion_error(error_msg))
    
    def _convert_with_mido(self, midi_path):
        """使用mido库转换MIDI（备用方法）"""
        try:
            midi = mido.MidiFile(midi_path)
            
            # 解析MIDI事件
            events = []
            tempo = 500000  # 默认120 BPM
            ticks_per_beat = midi.ticks_per_beat
            
            for track in midi.tracks:
                track_time = 0
                active_notes = {}
                
                for msg in track:
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    
                    track_time += msg.time
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        active_notes[msg.note] = {
                            'start_time': track_time,
                            'velocity': msg.velocity
                        }
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        note = msg.note
                        if note in active_notes:
                            start_info = active_notes[note]
                            events.append({
                                'start_time': start_info['start_time'],
                                'end_time': track_time,
                                'note': note,
                                'velocity': start_info['velocity']
                            })
                            del active_notes[note]
                
                # 处理未结束的音符
                for note, info in active_notes.items():
                    events.append({
                        'start_time': info['start_time'],
                        'end_time': info['start_time'] + 0.5,
                        'note': note,
                        'velocity': info['velocity']
                    })
            
            # 转换为绝对时间
            for event in events:
                event['start_time'] = mido.tick2second(event['start_time'], ticks_per_beat, tempo)
                event['end_time'] = mido.tick2second(event['end_time'], ticks_per_beat, tempo)
            
            # 按时间排序
            events.sort(key=lambda x: x['start_time'])
            
            # 生成LRCp内容
            lrcp_content = self._generate_lrcp_content(events, midi_path)
            
            # 保存LRCp文件
            output_dir = os.path.dirname(midi_path)
            output_name = os.path.splitext(os.path.basename(midi_path))[0]
            lrcp_output = os.path.join(output_dir, f"{output_name}.lrcp")
            
            with open(lrcp_output, "w", encoding="utf-8") as f:
                f.write(lrcp_content)
            
            # 转换完成
            self.root.after(0, lambda: self._midi_conversion_complete(lrcp_output, len(events)))
            
        except Exception as e:
            error_msg = f"mido转换失败: {str(e)}"
            self.root.after(0, lambda: self._conversion_error(error_msg))
    
    def _generate_lrcp_content(self, events, midi_path):
        """生成LRCp内容 - 使用正确的音符映射"""
        content = f"# 从MIDI文件转换: {os.path.basename(midi_path)}\n"
        content += f"# 转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "# 格式: [开始时间][结束时间] 音符\n\n"
        
        # 使用参考项目的正确音符映射表（C4=60基准）
        NOTE_MAP = {
            # 低音区 (C3-B3)
            48: 'L1', 50: 'L2', 52: 'L3', 53: 'L4', 55: 'L5', 57: 'L6', 59: 'L7',
            # 中音区 (C4-B4)
            60: 'M1', 62: 'M2', 64: 'M3', 65: 'M4', 67: 'M5', 69: 'M6', 71: 'M7',
            # 高音区 (C5-B5)
            72: 'H1', 74: 'H2', 76: 'H3', 77: 'H4', 79: 'H5', 81: 'H6', 83: 'H7',
        }
        
        # 生成LRCp行
        for event in events:
            note = event['note']
            start_time = event['start_time']
            end_time = event['end_time']
            
            # 使用正确的映射表
            if note in NOTE_MAP:
                key = NOTE_MAP[note]
                start_str = self._seconds_to_timestamp(start_time)
                end_str = self._seconds_to_timestamp(end_time)
                
                if abs(end_time - start_time) < 0.001:  # 短音（1毫秒以内）
                    content += f"[{start_str}] {key}\n"
                else:  # 延长音
                    content += f"[{start_str}][{end_str}] {key}\n"
        
        return content
    
    def _seconds_to_timestamp(self, seconds):
        """将秒数转换为时间戳格式"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{minutes:02d}:{secs:02d}.{millisecs:03d}"
    
    def _midi_conversion_complete(self, lrcp_path, events):
        """MIDI转换完成处理"""
        self.log(f"MIDI转换完成: {lrcp_path}", "SUCCESS")
        self.status_var.set("MIDI转换完成")
        
        # 自动加载转换后的LRCp文件
        try:
            with open(lrcp_path, "r", encoding="utf-8") as f:
                score_text = f.read()
            self.score_events = parse_score(score_text)
            self.score_path_var.set(lrcp_path)
            self.analyze_score_file()
            
            messagebox.showinfo("转换完成", f"MIDI文件已成功转换为LRCp格式！\n文件路径: {lrcp_path}\n共转换 {events} 个音符事件")
        except Exception as e:
            self.log(f"自动加载LRCp文件失败: {str(e)}", "ERROR")
    
    def load_score_file(self):
        """加载乐谱文件"""
        file_path = filedialog.askopenfilename(
            title="选择乐谱文件",
            filetypes=[("乐谱文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    score_text = f.read()
                self.log(f"成功加载乐谱文件: {file_path}", "INFO")
                self.score_text_var.set(score_text)
                self.parse_and_play_score(score_text)
            except Exception as e:
                self.log(f"加载乐谱文件失败: {str(e)}", "ERROR")
                messagebox.showerror("错误", f"加载乐谱文件失败: {str(e)}")
    
    def batch_convert(self):
        """批量转换MP3文件"""
        folder_path = filedialog.askdirectory(title="选择包含MP3文件的文件夹")
        if not folder_path:
            return
        
        mp3_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.mp3')]
        if not mp3_files:
            messagebox.showinfo("提示", "所选文件夹中没有MP3文件")
            return
        
        # 创建输出目录
        output_dir = os.path.join(folder_path, "converted_midi")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self.log(f"开始批量转换 {len(mp3_files)} 个MP3文件...", "INFO")
        
        # 在新线程中执行批量转换
        batch_thread = threading.Thread(target=self._batch_convert_thread, args=(folder_path, mp3_files, output_dir))
        batch_thread.daemon = True
        batch_thread.start()
    
    def _batch_convert_thread(self, folder_path, mp3_files, output_dir):
        """批量转换线程"""
        try:
            # 修复PianoTrans路径问题
            piano_trans_path = os.path.join("PianoTrans-v1.0", "PianoTrans.exe")
            if not os.path.exists(piano_trans_path):
                # 尝试其他可能的路径
                alt_paths = [
                    "PianoTrans-v1.0/PianoTrans.exe",
                    "PianoTrans-v1.0/PianoTrans.exe",
                    "PianoTrans.exe"
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        piano_trans_path = alt_path
                        break
                
                if not os.path.exists(piano_trans_path):
                    self.root.after(0, lambda: messagebox.showerror("错误", "找不到PianoTrans.exe"))
                    return
            
            success_count = 0
            for i, mp3_file in enumerate(mp3_files):
                if not os.path.exists(piano_trans_path):
                    break
                
                mp3_path = os.path.join(folder_path, mp3_file)
                output_name = os.path.splitext(mp3_file)[0] + ".mid"
                midi_output = os.path.join(output_dir, output_name)
                
                self.root.after(0, lambda msg=f"正在转换 {mp3_file} ({i+1}/{len(mp3_files)})": self.status_var.set(msg))
                
                try:
                    # 使用正确的PianoTrans路径
                    cmd = [piano_trans_path, mp3_path, "-o", midi_output]
                    result = subprocess.run(cmd, capture_output=True, text=False, cwd=os.path.dirname(piano_trans_path), timeout=300)
                    
                    # 处理输出
                    stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
                    stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                    
                    if result.returncode == 0 and os.path.exists(midi_output):
                        success_count += 1
                        self.root.after(0, lambda msg=f"转换成功: {mp3_file}": self.log(msg, "SUCCESS"))
                    else:
                        error_detail = stderr if stderr else stdout
                        self.root.after(0, lambda msg=f"转换失败: {mp3_file} - {error_detail}": self.log(msg, "ERROR"))
                
                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda msg=f"转换超时: {mp3_file}": self.log(msg, "WARNING"))
                except Exception as e:
                    self.root.after(0, lambda msg=f"转换错误 {mp3_file}: {str(e)}": self.log(msg, "ERROR"))
            
            self.root.after(0, lambda: self._batch_convert_complete(success_count, len(mp3_files), output_dir))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"批量转换失败: {str(e)}", "ERROR"))
    
    def _batch_convert_complete(self, success_count, total_count, output_dir):
        """批量转换完成"""
        self.status_var.set("批量转换完成")
        messagebox.showinfo("批量转换完成", 
                          f"转换完成！\n成功: {success_count}/{total_count}\n输出目录: {output_dir}")
        self.log(f"批量转换完成: {success_count}/{total_count} 成功", "SUCCESS")
    
    def convert_mp3_to_midi(self):
        """使用PianoTrans转换MP3到MIDI"""
        mp3_path = self.mp3_path_var.get()
        if not mp3_path:
            messagebox.showerror("错误", "请先选择MP3文件")
            return
        
        if not os.path.exists(mp3_path):
            messagebox.showerror("错误", "MP3文件不存在")
            return
        
        # 检查PianoTrans是否存在，尝试多个路径
        piano_trans_path = os.path.join("PianoTrans-v1.0", "PianoTrans.exe")
        if not os.path.exists(piano_trans_path):
            # 尝试其他可能的路径
            alt_paths = [
                "PianoTrans-v1.0/PianoTrans.exe",
                "PianoTrans-v1.0/PianoTrans.exe",
                "PianoTrans.exe"
            ]
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    piano_trans_path = alt_path
                    break
            
            if not os.path.exists(piano_trans_path):
                messagebox.showerror("错误", "找不到PianoTrans.exe，请确保PianoTrans-v1.0文件夹存在")
                return
        
        self.log("开始转换MP3到MIDI...", "INFO")
        self.status_var.set("正在转换...")
        
        # 在新线程中执行转换
        convert_thread = threading.Thread(target=self._convert_mp3_thread, args=(mp3_path, piano_trans_path))
        convert_thread.daemon = True
        convert_thread.start()
    
    def _convert_mp3_thread(self, mp3_path, piano_trans_path):
        """在后台线程中转换MP3"""
        try:
            # 获取输出目录
            output_dir = os.path.dirname(mp3_path)
            output_name = os.path.splitext(os.path.basename(mp3_path))[0]
            
            # 构建输出路径
            midi_output = os.path.join(output_dir, f"{output_name}.mid")
            
            # 调用PianoTrans
            cmd = [piano_trans_path, mp3_path, "-o", midi_output]
            result = subprocess.run(cmd, capture_output=True, text=False, cwd=os.path.dirname(piano_trans_path), timeout=300)
            
            # 处理输出
            stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
            
            if result.returncode == 0 and os.path.exists(midi_output):
                self.root.after(0, lambda: self._conversion_complete(midi_output))
            else:
                error_msg = f"转换失败: {stderr}"
                self.root.after(0, lambda: self._conversion_error(error_msg))
                
        except subprocess.TimeoutExpired:
            error_msg = "转换超时，请检查文件大小和系统性能"
            self.root.after(0, lambda: self._conversion_error(error_msg))
        except Exception as e:
            error_msg = f"转换过程中发生错误: {str(e)}"
            self.root.after(0, lambda: self._conversion_error(error_msg))
    
    def _conversion_complete(self, midi_path):
        """转换完成处理"""
        self.midi_path_var.set(midi_path)
        self.midi_file = midi_path
        self.log(f"MP3转换完成: {midi_path}", "SUCCESS")
        self.status_var.set("转换完成")
        self.analyze_midi_file(midi_path)
        messagebox.showinfo("成功", "MP3转换完成！")
    
    def _conversion_error(self, error_msg):
        """转换错误处理"""
        self.log(f"转换错误: {error_msg}", "ERROR")
        self.status_var.set("转换失败")
        messagebox.showerror("转换失败", error_msg)
    
    def analyze_midi_file(self, midi_path):
        """分析MIDI文件"""
        try:
            midi = mido.MidiFile(midi_path)
            self.log(f"MIDI文件分析完成:", "INFO")
            self.log(f"  轨道数: {len(midi.tracks)}")
            self.log(f"  总时长: {midi.length:.2f}秒")
            self.log(f"  时间分辨率: {midi.ticks_per_beat}")
            
            # 分析音符
            note_count = 0
            for track in midi.tracks:
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        note_count += 1
            
            self.log(f"  音符总数: {note_count}")
            
        except Exception as e:
            self.log(f"MIDI文件分析失败: {str(e)}", "ERROR")
    
    def play_midi(self):
        """播放MIDI文件"""
        if not self.midi_file or not os.path.exists(self.midi_file):
            messagebox.showerror("错误", "请先选择MIDI文件")
            return
        
        if self.is_playing:
            return
        
        self.is_playing = True
        self.play_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("正在播放...")
        
        # 在新线程中播放
        self.playback_thread = threading.Thread(target=self._play_midi_thread)
        self.playback_thread.daemon = True
        self.playback_thread.start()
    
    def _play_midi_thread(self):
        """在后台线程中播放MIDI"""
        try:
            midi = mido.MidiFile(self.midi_file)
            start_time = time.time()
            
            # 计算总时长
            total_time = midi.length
            
            for msg in midi.play():
                if not self.is_playing:
                    break
                
                # 更新进度条和时间显示
                current_time = time.time() - start_time
                progress = min(100, (current_time / total_time) * 100)
                
                current_str = time.strftime("%M:%S", time.gmtime(current_time))
                total_str = time.strftime("%M:%S", time.gmtime(total_time))
                
                self.root.after(0, lambda p=progress, c=current_str, t=total_str: self._update_progress(p, c, t))
                
                # 处理音符消息
                if msg.type == 'note_on' and msg.velocity > 0:
                    self.log(f"播放音符: {msg.note} (通道 {msg.channel})", "INFO")
                
                time.sleep(0.01)  # 小延迟避免界面卡顿
            
            # 播放完成
            self.root.after(0, self._playback_complete)
            
        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.root.after(0, lambda: self._playback_error(error_msg))
    
    def _update_progress(self, progress, current_time, total_time):
        """更新进度条和时间显示"""
        self.progress_var.set(progress)
        self.time_var.set(f"{current_time} / {total_time}")
    
    def _playback_complete(self):
        """播放完成处理"""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.time_var.set("00:00 / 00:00")
        self.status_var.set("播放完成")
        self.log("MIDI播放完成", "SUCCESS")
    
    def _playback_error(self, error_msg):
        """播放错误处理"""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("播放失败")
        self.log(f"播放错误: {error_msg}", "ERROR")
        messagebox.showerror("播放失败", error_msg)
    
    def stop_midi(self):
        """停止播放"""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.time_var.set("00:00 / 00:00")
        self.status_var.set("已停止")
        self.log("MIDI播放已停止", "INFO")
    
    def toggle_auto_play(self):
        """切换自动弹琴模式"""
        if not self.midi_file or not os.path.exists(self.midi_file):
            messagebox.showerror("错误", "请先选择MIDI文件")
            return
        
        if self.is_auto_playing:
            self.stop_auto_play()
        else:
            self.start_auto_play()
    
    def start_auto_play(self):
        """开始自动弹琴"""
        self.is_auto_playing = True
        self.auto_play_button.config(text="停止弹琴")
        self.status_var.set("自动弹琴中...")
        self.log("开始自动弹琴", "INFO")
        
        # 在新线程中执行自动弹琴
        self.auto_play_thread = threading.Thread(target=self._auto_play_thread)
        self.auto_play_thread.daemon = True
        self.auto_play_thread.start()
    
    def stop_auto_play(self):
        """停止自动弹琴"""
        self.is_auto_playing = False
        self.auto_play_button.config(text="自动弹琴")
        self.status_var.set("自动弹琴已停止")
        self.log("自动弹琴已停止", "INFO")
    
    def _auto_play_thread(self):
        """自动弹琴线程"""
        try:
            midi = mido.MidiFile(self.midi_file)
            
            # 解析MIDI事件
            events = []
            for track in midi.tracks:
                current_time = 0
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        events.append({
                            'time': current_time,
                            'note': msg.note,
                            'duration': msg.time,
                            'velocity': msg.velocity
                        })
                    current_time += msg.time
            
            # 按时间排序
            events.sort(key=lambda x: x['time'])
            
            # 开始自动弹琴
            start_time = time.time()
            current_time = 0
            
            for event in events:
                if not self.is_auto_playing:
                    break
                
                # 等待到指定时间
                target_time = event['time'] / 1000.0  # 转换为秒
                while current_time < target_time and self.is_auto_playing:
                    time.sleep(0.001)
                    current_time = time.time() - start_time
                
                if not self.is_auto_playing:
                    break
                
                # 发送按键
                self._send_note_key(event['note'])
                self.log(f"弹奏音符: {event['note']}", "INFO")
                
                # 等待音符持续时间
                duration = event['duration'] / 1000.0
                time.sleep(duration)
            
            # 自动弹琴完成
            self.root.after(0, self._auto_play_complete)
            
        except Exception as e:
            error_msg = f"自动弹琴失败: {str(e)}"
            self.root.after(0, lambda: self._auto_play_error(error_msg))
    
    def _send_note_key(self, note):
        """根据音符发送对应的按键"""
        try:
            # 将MIDI音符转换为键位
            note_name = self._midi_note_to_name(note)
            key = self._note_to_key(note_name)
            
            if key:
                # 模拟按键按下和释放
                keyboard.press_and_release(key)
                self.log(f"发送按键: {note_name} -> {key}", "INFO")
            
        except Exception as e:
            self.log(f"发送按键失败: {str(e)}", "ERROR")
    
    def _midi_note_to_name(self, midi_note):
        """将MIDI音符数字转换为音符名称"""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_note // 12) - 1
        note_name = note_names[midi_note % 12]
        
        if octave == 4:
            return note_name + '4'  # 中音
        elif octave == 5:
            return note_name + '5'  # 高音
        else:
            return note_name  # 低音
    
    def _note_to_key(self, note_name):
        """将音符名称转换为对应的键位"""
        # 直接查找音符映射
        if note_name in self.note_mapping:
            mapped_note = self.note_mapping[note_name]
            if mapped_note in self.key_mapping:
                return self.key_mapping[mapped_note]
        
        # 如果没有找到，尝试基础音符
        base_note = note_name.rstrip('0123456789')
        if base_note in self.note_mapping:
            mapped_note = self.note_mapping[base_note]
            if mapped_note in self.key_mapping:
                return self.key_mapping[mapped_note]
        
        return None
    
    def _auto_play_complete(self):
        """自动弹琴完成处理"""
        self.is_auto_playing = False
        self.auto_play_button.config(text="自动弹琴")
        self.status_var.set("自动弹琴完成")
        self.log("自动弹琴完成", "SUCCESS")
    
    def _auto_play_error(self, error_msg):
        """自动弹琴错误处理"""
        self.is_auto_playing = False
        self.auto_play_button.config(text="自动弹琴")
        self.status_var.set("自动弹琴失败")
        self.log(f"自动弹琴错误: {error_msg}", "ERROR")
        messagebox.showerror("自动弹琴失败", error_msg)
    
    def on_closing(self):
        """关闭程序时的处理"""
        if self.is_playing:
            self.stop_midi()
        if self.is_auto_playing:
            self.stop_auto_play()
        
        # 保存配置
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except:
            pass
        
        self.root.destroy()
    
    def run(self):
        """运行程序"""
        self.log("Python 3.12兼容版自动弹琴软件启动成功 (管理员模式)", "SUCCESS")
        self.log("支持功能: MP3转MIDI、MIDI播放、自动弹琴、批量转换", "INFO")
        self.root.mainloop()

    def check_pianotrans(self):
        """检查PianoTrans配置和模型文件"""
        try:
            self.log("开始检查PianoTrans配置...", "INFO")
            
            # 检查PianoTrans.exe
            piano_trans_paths = [
                os.path.join("PianoTrans-v1.0", "PianoTrans.exe"),
                os.path.join("PianoTrans-v1.0", "PianoTrans-v1.0", "PianoTrans.exe"),
                "PianoTrans.exe"
            ]
            
            piano_trans_found = False
            piano_trans_path = None
            
            for path in piano_trans_paths:
                if os.path.exists(path):
                    piano_trans_found = True
                    piano_trans_path = os.path.abspath(path)
                    self.log(f"✓ 找到PianoTrans.exe: {piano_trans_path}", "SUCCESS")
                    break
            
            if not piano_trans_found:
                self.log("❌ 未找到PianoTrans.exe", "ERROR")
                messagebox.showerror("检查结果", "未找到PianoTrans.exe，请确保PianoTrans-v1.0文件夹存在")
                return
            
            # 检查模型文件
            model_file = "note_F1=0.9677_pedal_F1=0.9186.pth"
            model_paths = [
                os.path.join(os.path.dirname(piano_trans_path), "piano_transcription_inference_data", model_file),
                os.path.join(os.path.dirname(piano_trans_path), "PianoTrans-v1.0", "piano_transcription_inference_data", model_file),
                os.path.join("piano_transcription_inference_data", model_file),
                os.path.join(os.getcwd(), "PianoTrans-v1.0", "piano_transcription_inference_data", model_file),
                os.path.join(os.getcwd(), "piano_transcription_inference_data", model_file),
            ]
            
            model_found = False
            model_path = None
            
            for path in model_paths:
                if os.path.exists(path):
                    model_found = True
                    model_path = os.path.abspath(path)
                    self.log(f"✓ 找到模型文件: {model_path}", "SUCCESS")
                    break
            
            if not model_found:
                # 搜索整个PianoTrans目录
                piano_trans_dir = os.path.dirname(piano_trans_path)
                for root, dirs, files in os.walk(piano_trans_dir):
                    if model_file in files:
                        model_found = True
                        model_path = os.path.abspath(os.path.join(root, model_file))
                        self.log(f"✓ 搜索到模型文件: {model_path}", "SUCCESS")
                        break
            
            if not model_found:
                self.log("❌ 未找到模型文件", "ERROR")
                
                # 显示详细的检查结果
                check_result = f"""PianoTrans检查结果:

✓ PianoTrans.exe: {piano_trans_path}
❌ 模型文件: {model_file}

已尝试的路径:
"""
                for path in model_paths:
                    check_result += f"  {path}\n"
                
                check_result += f"\n建议解决方案:\n"
                check_result += f"1. 确保模型文件存在于piano_transcription_inference_data文件夹中\n"
                check_result += f"2. 检查文件夹结构是否正确\n"
                check_result += f"3. 重新下载PianoTrans完整版本\n"
                
                messagebox.showinfo("检查结果", check_result)
                return
            
            # 检查文件大小
            try:
                model_size = os.path.getsize(model_path)
                model_size_mb = model_size / (1024 * 1024)
                self.log(f"模型文件大小: {model_size_mb:.1f} MB", "INFO")
                
                if model_size_mb < 100:
                    self.log("⚠️ 模型文件可能不完整（小于100MB）", "WARNING")
            except:
                pass
            
            # 检查目录结构
            piano_trans_dir = os.path.dirname(piano_trans_path)
            self.log(f"PianoTrans目录: {piano_trans_dir}", "INFO")
            
            try:
                for root, dirs, files in os.walk(piano_trans_dir):
                    level = root.replace(piano_trans_dir, '').count(os.sep)
                    indent = ' ' * 2 * level
                    self.log(f"{indent}{os.path.basename(root)}/", "INFO")
                    subindent = ' ' * 2 * (level + 1)
                    for file in files[:10]:  # 只显示前10个文件
                        self.log(f"{subindent}{file}", "INFO")
                    if len(files) > 10:
                        self.log(f"{subindent}... 还有 {len(files) - 10} 个文件", "INFO")
            except Exception as e:
                self.log(f"遍历目录失败: {str(e)}", "WARNING")
            
            # 显示成功结果
            success_msg = f"""PianoTrans检查完成！

✓ PianoTrans.exe: {piano_trans_path}
✓ 模型文件: {model_path}
✓ 配置正常，可以开始转换

注意：首次使用需要等待模型加载（约165MB）"""
            
            messagebox.showinfo("检查结果", success_msg)
            self.log("PianoTrans检查完成，配置正常", "SUCCESS")
            
        except Exception as e:
            error_msg = f"检查PianoTrans时发生错误: {str(e)}"
            self.log(error_msg, "ERROR")
            messagebox.showerror("检查失败", error_msg)

def main():
    """主函数"""
    try:
        app = Py312AutoPiano()
        app.run()
    except Exception as e:
        # 在PYW模式下，使用messagebox显示错误
        try:
            import tkinter.messagebox as msgbox
            msgbox.showerror("程序启动失败", f"程序启动失败: {str(e)}")
        except:
            pass

if __name__ == "__main__":
    main() 