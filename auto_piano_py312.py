#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField_AutoPiano
支持MP3转MIDI、MIDI播放和自动弹琴功能
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
# 新增：字体与主题库（安全导入）
from tkinter import font as tkfont
try:
    import ttkbootstrap as tb  # 可选主题库
except Exception:
    tb = None
# Toast 与 ToolTip（可选）
try:
    from ttkbootstrap.toast import ToastNotification
except Exception:
    ToastNotification = None
try:
    from ttkbootstrap.tooltip import ToolTip
except Exception:
    ToolTip = None
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
import ctypes
# 新增：模块化日志视图
try:
    from meowauto.ui.logview import LogView
except Exception:
    LogView = None
# 新增：表格样式工具（斑马纹/悬停）
try:
    from meowauto.widgets.table import style_table as _tbl_style, apply_striped as _tbl_striped, bind_hover_highlight as _tbl_hover
except Exception:
    _tbl_style = _tbl_striped = _tbl_hover = None
# 新增：外观管理器
try:
    from meowauto.ui.appearance import AppearanceManager as _AppearanceManager
except Exception:
    _AppearanceManager = None
# 新增：播放列表视图
try:
    from meowauto.ui.playlist import PlaylistView as _PlaylistView
except Exception:
    _PlaylistView = None
# 倒计时
try:
    from meowauto import CountdownTimer as _CountdownTimer
except Exception:
    _CountdownTimer = None

# 导入音频转换模块
try:
    from audio_to_midi_converter import AudioToMidiConverter
    AUDIO_CONVERTER_AVAILABLE = True
except ImportError:
    AUDIO_CONVERTER_AVAILABLE = False

# 导入PianoTrans配置模块
try:
    from pianotrans_config import PianoTransConfig
    PIANOTRANS_CONFIG_AVAILABLE = True
except ImportError:
    PIANOTRANS_CONFIG_AVAILABLE = False

# 时间戳正则表达式：形如 [mm:ss.xxx]，毫秒 .xxx 可省略
TS_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")

# 允许的音符 token 正则表达式
TOKEN_RE = re.compile(r"(?:(?:[LMH][1-7])|(?:C|Dm|Em|F|G|Am|G7))")

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
    valid_tokens = [tok for tok in tokens if TOKEN_RE.fullmatch(tok)]
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
            if not k:  # 跳过空键
                continue
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
            if not k:  # 跳过空键
                continue
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
        self.root.title("MeowField_AutoPiano v1.0.2")
        self.root.geometry("1400x900")
        self.root.resizable(True, True)
        
        # 初始化配置
        self.config = self.load_config()
        
        # 先设定按钮风格默认值，防止外观初始化失败导致属性缺失
        self.accent_button_style = "TButton"
        self.secondary_button_style = "TButton"
        
        # 外观初始化（主题/缩放/密度）
        try:
            if _AppearanceManager is not None:
                self._appearance = _AppearanceManager(self, self.config, self.log)
                self._appearance.init()
            else:
                self._init_appearance()
        except Exception as _e:
            # 外观失败不影响功能
            pass
        
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
        # 倒计时状态
        self._countdown_active = False
        self._countdown_after_id = None
        # 自动弹琴暂停状态
        self.is_auto_paused = False
        
        # 加载键位映射
        self.load_key_mappings()
        
        # 初始化pygame音频
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(self.current_volume)
            self.log("音频系统初始化成功", "SUCCESS")
        except Exception as e:
            self.log(f"音频系统初始化失败: {e}", "WARNING")
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 创建输出目录
        self.create_directories()
        
        # 初始化播放列表
        self.playlist_items = []
        self.current_playlist_index = -1
        self.random_play = False
        self.loop_play = False
        
        # 初始化音频转换器
        if AUDIO_CONVERTER_AVAILABLE:
            self.audio_converter = AudioToMidiConverter(self.log)
            self.log("音频转换模块已加载", "SUCCESS")
        else:
            self.audio_converter = None
            self.log("音频转换模块未加载，将使用传统方法", "WARNING")
        
        # 初始化PianoTrans配置器
        if PIANOTRANS_CONFIG_AVAILABLE:
            self.pianotrans_config = PianoTransConfig(self.log)
            self.log("PianoTrans配置模块已加载", "SUCCESS")
        else:
            self.pianotrans_config = None
            self.log("PianoTrans配置模块未加载", "WARNING")
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                # 兼容注入 UI 默认项
                ui_default = {
                    "theme_name": "flatly",
                    "theme_mode": "light",
                    "density": "comfortable",
                    "scaling": "auto",
                    "sidebar_stub": True
                }
                if "ui" not in cfg or not isinstance(cfg.get("ui"), dict):
                    cfg["ui"] = ui_default
                else:
                    for k, v in ui_default.items():
                        cfg["ui"].setdefault(k, v)
                return cfg
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
                    },
                    "ui": {
                        "theme_name": "flatly",
                        "theme_mode": "light",
                        "density": "comfortable",
                        "scaling": "auto",
                        "sidebar_stub": True
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
        
        # 音符到键位的映射 - 基于标准MIDI音符编号
        # MIDI音符编号: C0=12, C1=24, C2=36, C3=48, C4=60, C5=72, C6=84, C7=96, C8=108
        self.note_mapping = {}
        
        # 低音八度 (C2-B2, 音符编号36-47)
        low_notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        for i, note in enumerate(low_notes):
            midi_note = 36 + i
            if note in ['C', 'C#']: self.note_mapping[midi_note] = 'L1'  # C2, C#2 -> L1
            elif note in ['D', 'D#']: self.note_mapping[midi_note] = 'L2'  # D2, D#2 -> L2
            elif note == 'E': self.note_mapping[midi_note] = 'L3'  # E2 -> L3
            elif note in ['F', 'F#']: self.note_mapping[midi_note] = 'L4'  # F2, F#2 -> L4
            elif note in ['G', 'G#']: self.note_mapping[midi_note] = 'L5'  # G2, G#2 -> L5
            elif note in ['A', 'A#']: self.note_mapping[midi_note] = 'L6'  # A2, A#2 -> L6
            elif note == 'B': self.note_mapping[midi_note] = 'L7'  # B2 -> L7
        
        # 中音八度 (C3-B3, 音符编号48-59)
        for i, note in enumerate(low_notes):
            midi_note = 48 + i
            if note in ['C', 'C#']: self.note_mapping[midi_note] = 'M1'  # C3, C#3 -> M1
            elif note in ['D', 'D#']: self.note_mapping[midi_note] = 'M2'  # D3, D#3 -> M2
            elif note == 'E': self.note_mapping[midi_note] = 'M3'  # E3 -> M3
            elif note in ['F', 'F#']: self.note_mapping[midi_note] = 'M4'  # F3, F#3 -> M4
            elif note in ['G', 'G#']: self.note_mapping[midi_note] = 'M5'  # G3, G#3 -> M5
            elif note in ['A', 'A#']: self.note_mapping[midi_note] = 'M6'  # A3, A#3 -> M6
            elif note == 'B': self.note_mapping[midi_note] = 'M7'  # B3 -> M7
        
        # 高音八度 (C4-B4, 音符编号60-71)
        for i, note in enumerate(low_notes):
            midi_note = 60 + i
            if note in ['C', 'C#']: self.note_mapping[midi_note] = 'H1'  # C4, C#4 -> H1
            elif note in ['D', 'D#']: self.note_mapping[midi_note] = 'H2'  # D4, D#4 -> H2
            elif note == 'E': self.note_mapping[midi_note] = 'H3'  # E4 -> H3
            elif note in ['F', 'F#']: self.note_mapping[midi_note] = 'H4'  # F4, F#4 -> H4
            elif note in ['G', 'G#']: self.note_mapping[midi_note] = 'H5'  # G4, G#4 -> H5
            elif note in ['A', 'A#']: self.note_mapping[midi_note] = 'H6'  # A4, A#4 -> H6
            elif note == 'B': self.note_mapping[midi_note] = 'H7'  # B4 -> H7
        
        # 更高八度 (C5-B5, 音符编号72-83) - 映射到高音
        for i, note in enumerate(low_notes):
            midi_note = 72 + i
            if note in ['C', 'C#']: self.note_mapping[midi_note] = 'H1'  # C5, C#5 -> H1
            elif note in ['D', 'D#']: self.note_mapping[midi_note] = 'H2'  # D5, D#5 -> H2
            elif note == 'E': self.note_mapping[midi_note] = 'H3'  # E5 -> H3
            elif note in ['F', 'F#']: self.note_mapping[midi_note] = 'H4'  # F5, F#5 -> H4
            elif note in ['G', 'G#']: self.note_mapping[midi_note] = 'H5'  # G5, G#5 -> H5
            elif note in ['A', 'A#']: self.note_mapping[midi_note] = 'H6'  # A5, A#5 -> H6
            elif note == 'B': self.note_mapping[midi_note] = 'H7'  # B5 -> H7
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        # 新增：右侧工具列
        main_frame.columnconfigure(2, weight=0)
        
        # 标题
        try:
            title_font = tkfont.nametofont("TkHeadingFont")
        except Exception:
            title_font = ("Microsoft YaHei", 18, "bold")
        title_label = ttk.Label(main_frame, text="🎹 MeowField_AutoPiano", font=title_font)
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 预留侧边栏占位（不影响布局）
        try:
            if self.config.get("ui", {}).get("sidebar_stub", True):
                self._init_docked_sidebar_stub()
        except Exception:
            pass
        
        # 新增：外观工具条（主题/模式/密度）
        appearance_bar = ttk.Frame(main_frame)
        appearance_bar.grid(row=0, column=2, sticky=tk.E, pady=(0,10))
        # 主题选择
        self.theme_var = tk.StringVar(value=self.config.get("ui", {}).get("theme_name", "flatly"))
        themes_light = ["flatly", "litera", "cosmo", "sandstone"]
        themes_dark = ["darkly", "superhero", "cyborg", "solar"]
        ttk.Label(appearance_bar, text="主题:").pack(side=tk.LEFT)
        theme_combo = ttk.Combobox(appearance_bar, width=12, state="readonly", textvariable=self.theme_var,
                                   values=themes_light + themes_dark)
        theme_combo.pack(side=tk.LEFT, padx=(4,8))
        def _on_theme_change(_e=None):
            try:
                if hasattr(self, "_appearance") and self._appearance:
                    self._appearance.apply_theme(self.theme_var.get())
                    self._appearance.apply_to_widgets()
                else:
                    self._apply_theme(self.theme_var.get())
            except Exception as e:
                self.log(f"主题切换失败: {e}", "WARNING")
        theme_combo.bind('<<ComboboxSelected>>', _on_theme_change)
        try:
            if ToolTip is not None:
                ToolTip(theme_combo, text="切换主题（与下方模式配合）")
        except Exception:
            pass
        # 模式选择
        self.theme_mode_var = tk.StringVar(value=self.config.get("ui", {}).get("theme_mode", "light"))
        ttk.Label(appearance_bar, text="模式:").pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(appearance_bar, width=7, state="readonly", textvariable=self.theme_mode_var,
                                  values=["light", "dark"])
        mode_combo.pack(side=tk.LEFT, padx=(4,8))
        def _on_mode_change(_e=None):
            try:
                mode = self.theme_mode_var.get()
                cur = self.theme_var.get()
                mapping = {
                "flatly": ("flatly", "darkly"),
                "litera": ("litera", "superhero"),
                "cosmo": ("cosmo", "cyborg"),
                "sandstone": ("sandstone", "solar"),
                "darkly": ("flatly", "darkly"),
                "superhero": ("litera", "superhero"),
                "cyborg": ("cosmo", "cyborg"),
                "solar": ("sandstone", "solar")
                }
                light, dark = mapping.get(cur, ("flatly", "darkly"))
                target = dark if mode == "dark" else light
                self.theme_var.set(target)
                if hasattr(self, "_appearance") and self._appearance:
                    self._appearance.apply_theme(target)
                    self._appearance.apply_to_widgets()
                else:
                    self._apply_theme(target)
                self.config.setdefault("ui", {})["theme_mode"] = mode
            except Exception as e:
                self.log(f"模式切换失败: {e}", "WARNING")
        mode_combo.bind('<<ComboboxSelected>>', _on_mode_change)
        try:
            if ToolTip is not None:
                ToolTip(mode_combo, text="切换浅色/深色模式")
        except Exception:
            pass
        # 密度选择
        self.density_var = tk.StringVar(value=self.config.get("ui", {}).get("density", "comfortable"))
        ttk.Label(appearance_bar, text="密度:").pack(side=tk.LEFT)
        density_combo = ttk.Combobox(appearance_bar, width=10, state="readonly", textvariable=self.density_var,
                                     values=["comfortable", "compact"])
        density_combo.pack(side=tk.LEFT, padx=(4,0))
        def _on_density_change(_e=None):
            try:
                if hasattr(self, "_appearance") and self._appearance:
                    self._appearance.apply_density(self.density_var.get())
                    self._appearance.apply_to_widgets()
                else:
                    self._apply_density(self.density_var.get())
            except Exception as e:
                self.log(f"密度切换失败: {e}", "WARNING")
        density_combo.bind('<<ComboboxSelected>>', _on_density_change)
        try:
            if ToolTip is not None:
                ToolTip(density_combo, text="切换控件密度（紧凑/舒适）")
        except Exception:
            pass
        # 倒计时设置（可选）
        try:
            from meowauto.ui.countdown_settings import CountdownSettings as _CountdownSettings
            _cd = _CountdownSettings(appearance_bar, self)
        except Exception:
            pass
        
        # 页面容器与默认页（Meow）
        self._page_container = ttk.Frame(main_frame)
        self._page_container.grid(row=1, column=0, columnspan=3, sticky=(tk.N, tk.S, tk.E, tk.W))
        main_frame.rowconfigure(1, weight=1)
        self._page_container.columnconfigure(0, weight=1)
        self._page_container.rowconfigure(0, weight=1)
        self._page_meow = ttk.Frame(self._page_container)
        self._page_meow.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # 主内容采用左右分栏（位于 Meow 页）
        content_paned = ttk.Panedwindow(self._page_meow, orient=tk.HORIZONTAL)
        content_paned.grid(row=0, column=0, columnspan=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        self._page_meow.rowconfigure(0, weight=1)
        self._page_meow.columnconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        left_frame = ttk.Frame(content_paned)
        right_frame = ttk.Frame(content_paned, width=420)
        content_paned.add(left_frame, weight=3)
        content_paned.add(right_frame, weight=2)
        
        # 恢复 sash 位置（按比例），并在拖动释放后更新比例
        def _restore_sash():
            try:
                width = content_paned.winfo_width()
                if width <= 1:
                    self.root.after(50, _restore_sash)
                    return
                ui = self.config.get('ui', {})
                ratio = ui.get('sash_ratio', None)
                if isinstance(ratio, (int, float)):
                    r = max(0.2, min(0.8, float(ratio)))
                    pos = int(width * r)
                else:
                    # 默认左侧约 62%
                    pos = int(width * 0.62)
                content_paned.sashpos(0, pos)
            except Exception:
                pass
        self.root.after(0, _restore_sash)
        
        def _update_sash_ratio():
            try:
                w = max(1, content_paned.winfo_width())
                p = content_paned.sashpos(0)
                self.config.setdefault('ui', {})['sash_ratio'] = round(p / w, 4)
            except Exception:
                pass
        content_paned.bind('<ButtonRelease-1>', lambda e: _update_sash_ratio())
        
        self._content_paned = content_paned
        
        # 左侧内容随窗体拉伸
        for i in range(0, 6):
            left_frame.rowconfigure(i, weight=0)
        left_frame.rowconfigure(3, weight=1)  # 列表区域可扩展
        left_frame.columnconfigure(0, weight=1)
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(left_frame, text="文件选择", padding="12")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        
        ttk.Label(file_frame, text="音频文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.mp3_path_var = tk.StringVar()
        mp3_entry = ttk.Entry(file_frame, textvariable=self.mp3_path_var, width=60)
        mp3_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="浏览", command=self.browse_mp3).grid(row=0, column=2)
        
        # 转换按钮
        convert_frame = ttk.Frame(left_frame)
        convert_frame.grid(row=1, column=0, pady=(10, 0))
        
        ttk.Button(convert_frame, text="音频转MIDI", command=self.convert_mp3_to_midi, style=self.accent_button_style).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="选择MIDI文件", command=self.browse_midi, style=self.secondary_button_style).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(convert_frame, text="加载乐谱文件", command=self.load_score_file, style=self.secondary_button_style).pack(side=tk.LEFT, padx=(0, 10))
        
        # MIDI文件信息
        midi_frame = ttk.LabelFrame(left_frame, text="文件信息", padding="12")
        midi_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(midi_frame, text="MIDI文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.midi_path_var = tk.StringVar()
        midi_entry = ttk.Entry(midi_frame, textvariable=self.midi_path_var, width=60)
        midi_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Label(midi_frame, text="乐谱文件:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.score_path_var = tk.StringVar(value="未加载")
        score_entry = ttk.Entry(midi_frame, textvariable=self.score_path_var, width=60, state="readonly")
        score_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 乐谱信息显示
        self.score_info_var = tk.StringVar(value="乐谱信息: 未加载")
        score_info_label = ttk.Label(midi_frame, textvariable=self.score_info_var, foreground="blue")
        score_info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # 播放列表区域
        if _PlaylistView is not None:
            density = self.config.get('ui', {}).get('density', 'comfortable')
            sty = getattr(self, '_style', ttk.Style())
            self._playlist_view = _PlaylistView(left_frame, style=sty, density=density)
            # 工具栏（沿用原有三个按钮），添加到内部 toolbar
            toolbar = self._playlist_view.toolbar
            ttk.Button(toolbar, text="添加乐谱", command=self.add_to_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(toolbar, text="移除选中", command=self.remove_from_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(toolbar, text="清空列表", command=self.clear_playlist).pack(side=tk.LEFT, padx=(0, 5))
            # 指向新 tree
            self.playlist_tree = self._playlist_view.tree
            # 绑定双击事件
            self.playlist_tree.bind('<Double-1>', self.on_playlist_double_click)
        else:
            playlist_frame = ttk.LabelFrame(left_frame, text="自动演奏列表", padding="12")
            playlist_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
            playlist_frame.columnconfigure(0, weight=1)
            playlist_toolbar = ttk.Frame(playlist_frame)
            playlist_toolbar.pack(fill=tk.X, pady=(0, 5))
            ttk.Button(playlist_toolbar, text="添加乐谱", command=self.add_to_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="移除选中", command=self.remove_from_playlist).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(playlist_toolbar, text="清空列表", command=self.clear_playlist).pack(side=tk.LEFT, padx=(0, 5))
            playlist_display_frame = ttk.Frame(playlist_frame)
            playlist_display_frame.pack(fill=tk.BOTH, expand=True)
            columns = ('序号', '文件名', '类型', '时长', '状态')
            self.playlist_tree = ttk.Treeview(playlist_display_frame, columns=columns, show='headings', height=6)
            for col in columns:
                self.playlist_tree.heading(col, text=col)
                self.playlist_tree.column(col, width=100)
            playlist_scrollbar = ttk.Scrollbar(playlist_display_frame, orient=tk.VERTICAL, command=self.playlist_tree.yview)
            self.playlist_tree.configure(yscrollcommand=playlist_scrollbar.set)
            self.playlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            playlist_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        try:
            if _tbl_style:
                density = self.config.get('ui', {}).get('density', 'comfortable')
                sty = getattr(self, '_style', ttk.Style())
                _tbl_style(sty, density)
            if _tbl_hover:
                _tbl_hover(self.playlist_tree)
        except Exception:
            pass
        self.playlist_tree.bind('<Double-1>', self.on_playlist_double_click)
        
        # 播放控制区域
        control_frame = ttk.LabelFrame(left_frame, text="播放控制", padding="12")
        control_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 播放控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.auto_play_button = ttk.Button(button_frame, text="自动弹琴", command=self.toggle_auto_play, style=self.accent_button_style)
        self.auto_play_button.pack(pady=(0, 5))
        try:
            from meowauto.ui.countdown_settings import CountdownSettings as _CountdownSettings
            _cd_ctrl = _CountdownSettings(button_frame, self)
            _cd_ctrl.attach(pady=(4, 0))
        except Exception:
            pass
        
        # 控制参数
        param_frame = ttk.Frame(control_frame)
        param_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))
        
        ttk.Label(param_frame, text="速度:").pack()
        self.tempo_var = tk.DoubleVar(value=1.0)
        tempo_scale = ttk.Scale(param_frame, from_=0.5, to=2.0, variable=self.tempo_var, orient=tk.HORIZONTAL)
        tempo_scale.pack()
        # 速度显示与重置
        self.tempo_value_var = tk.StringVar(value="1.00x")
        def _on_tempo_change(*_):
            try:
                self.tempo_value_var.set(f"{float(self.tempo_var.get() or 1.0):.2f}x")
            except Exception:
                pass
        try:
            self.tempo_var.trace_add('write', _on_tempo_change)
        except Exception:
            pass
        speed_info = ttk.Frame(param_frame)
        speed_info.pack()
        ttk.Label(speed_info, textvariable=self.tempo_value_var, width=6).pack(side=tk.LEFT, padx=(4, 6))
        ttk.Button(speed_info, text="重置", command=lambda: self.tempo_var.set(1.0), style=self.secondary_button_style).pack(side=tk.LEFT)
        
        ttk.Label(param_frame, text="音量:").pack()
        self.volume_var = tk.DoubleVar(value=0.7)
        volume_scale = ttk.Scale(param_frame, from_=0.0, to=1.0, variable=self.volume_var, orient=tk.HORIZONTAL)
        volume_scale.pack()
        
        # 模式与映射选择
        mode_frame = ttk.Frame(control_frame)
        mode_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))
        ttk.Label(mode_frame, text="演奏模式:").pack()
        self.play_mode_var = tk.StringVar(value="midi")
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.play_mode_var, state="readonly",
            values=["lrcp", "midi"])
        mode_combo.pack()
        ttk.Label(mode_frame, text="映射策略:").pack(pady=(8,0))
        self.mapping_strategy_var = tk.StringVar(value="folded")
        strategy_combo = ttk.Combobox(mode_frame, textvariable=self.mapping_strategy_var, state="readonly",
            values=["folded", "qmp"])
        strategy_combo.pack()
        
        # 重复单音检测设置
        detection_frame = ttk.Frame(control_frame)
        detection_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))
        ttk.Label(detection_frame, text="重复单音检测:").pack()
        ttk.Label(detection_frame, text="时间窗口(ms):").pack()
        self.time_window_var = tk.IntVar(value=150)
        time_window_scale = ttk.Scale(detection_frame, from_=50, to=300, variable=self.time_window_var, orient=tk.HORIZONTAL)
        time_window_scale.pack()
        ttk.Label(detection_frame, text="最小和弦时长(秒):").pack()
        self.min_chord_duration_var = tk.DoubleVar(value=0.5)
        min_chord_scale = ttk.Scale(detection_frame, from_=0.3, to=1.5, variable=self.min_chord_duration_var, orient=tk.HORIZONTAL)
        min_chord_scale.pack()
        
        # 进度条
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(20, 0))
        
        self.progress_var = tk.DoubleVar()
        try:
            if tb is not None:
                self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, bootstyle="success-striped")
            else:
                self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        except Exception:
            self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # 时间显示
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        time_label = ttk.Label(progress_frame, textvariable=self.time_var)
        time_label.pack()

        # 帮助说明显示
        mapping_frame = ttk.LabelFrame(left_frame, text="帮助说明", padding="12")
        mapping_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 帮助文本
        ttk.Label(mapping_frame, text="热键ctrl+shift+c暂停/继续演奏，新版本不自带pianotrans（音频转换模型）需要单独下载，下载好后将文件夹移入根目录即可正常使用", justify=tk.LEFT, wraplength=600).pack(fill=tk.X)
        # 日志区域
        log_frame = ttk.LabelFrame(right_frame, text="操作日志", padding="12")
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 日志工具栏
        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(log_toolbar, text="清空日志", command=self.clear_log, style=self.secondary_button_style).pack(side=tk.LEFT)
        ttk.Button(log_toolbar, text="保存日志", command=self.save_log, style=self.secondary_button_style).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(log_toolbar, text="导出配置", command=self.export_config, style=self.secondary_button_style).pack(side=tk.LEFT, padx=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=16, width=100)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        # 创建后首次应用外观同步
        try:
            self._apply_appearance_to_widgets()
        except Exception:
            pass
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 快捷键绑定
        try:
            self.root.bind_all('<Control-o>', lambda e: self.browse_mp3())
            self.root.bind_all('<Control-p>', lambda e: self.toggle_auto_play())
            self.root.bind_all('<Control-l>', lambda e: self.clear_log())
            self.root.bind_all('<Control-s>', lambda e: self.save_log())
            self.root.bind_all('<Control-Shift-c>', self.pause_or_resume_auto)
        except Exception:
            pass
        
        # 追加其它页面：圆神 / 待开发（默认隐藏）
        try:
            self._page_ys = ttk.Frame(self._page_container)
            from meowauto.ui.yuanshen import YuanShenPage
            ys = YuanShenPage(self._page_ys)
            ys.frame.pack(fill=tk.BOTH, expand=True)
            self._page_ys.grid_remove()
        except Exception:
            self._page_ys = ttk.Frame(self._page_container)
            ttk.Label(self._page_ys, text="圆神 · 空白页").pack(pady=8)
            self._page_ys.grid_remove()
        self._page_tbd = ttk.Frame(self._page_container)
        ttk.Label(self._page_tbd, text="待开发 · TODO").pack(pady=8)
        self._page_tbd.grid_remove()
        
        # 默认显示 Meow 页
        self._switch_page('meow')
        
        # 注册全局热键：Ctrl+Shift+C 暂停/继续自动弹琴
        self._global_hotkey_handle = None
        try:
            self._global_hotkey_handle = keyboard.add_hotkey('ctrl+shift+c', lambda: self.root.after(0, self.pause_or_resume_auto))
            self.log("全局热键已注册：Ctrl+Shift+C（暂停/继续自动弹琴）", "INFO")
        except Exception as e:
            self.log(f"注册全局热键失败：{e}", "WARNING")
    
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
        
        # 安全回退：日志控件未创建时打印到控制台
        if not hasattr(self, "log_text") or self.log_text is None:
            try:
                print(log_message.strip())
            except Exception:
                pass
            return
        
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
        """浏览音频文件"""
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg"),
                ("MP3文件", "*.mp3"),
                ("WAV文件", "*.wav"),
                ("FLAC文件", "*.flac"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.mp3_path_var.set(file_path)
            self.log(f"已选择音频文件: {file_path}", "INFO")
    
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
            
            # 自动转换为LRCp，无需确认
            self.convert_midi_to_lrcp(file_path)
    
    def load_score_file(self):
        """加载乐谱文件 (.lrcp)"""
        file_path = filedialog.askopenfilename(
            title="选择乐谱文件 (.lrcp)",
            filetypes=[("乐谱文件", "*.lrcp"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    score_text = f.read()
                self.score_events = parse_score(score_text)
                self.log(f"成功加载乐谱文件: {file_path}", "SUCCESS")
                messagebox.showinfo("提示", f"成功加载乐谱文件: {file_path}")
                self.score_path_var.set(file_path)
                self.analyze_score_file()
            except Exception as e:
                self.log(f"加载乐谱文件失败: {str(e)}", "ERROR")
                messagebox.showerror("错误", f"加载乐谱文件失败: {str(e)}")
    
    def batch_convert(self):
        """批量转换音频文件"""
        folder_path = filedialog.askdirectory(title="选择包含音频文件的文件夹")
        if not folder_path:
            return
        
        # 支持的音频格式
        audio_extensions = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']
        audio_files = [f for f in os.listdir(folder_path) 
                      if any(f.lower().endswith(ext) for ext in audio_extensions)]
        
        if not audio_files:
            messagebox.showinfo("提示", "所选文件夹中没有支持的音频文件")
            return
        
        # 创建输出目录
        output_dir = os.path.join(folder_path, "converted_midi")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self.log(f"开始批量转换 {len(audio_files)} 个音频文件...", "INFO")
        
        # 在新线程中执行批量转换
        batch_thread = threading.Thread(target=self._batch_convert_thread, args=(folder_path, audio_files, output_dir))
        batch_thread.daemon = True
        batch_thread.start()
    
    def _batch_convert_thread(self, folder_path, audio_files, output_dir):
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
            for i, audio_file in enumerate(audio_files):
                if not os.path.exists(piano_trans_path):
                    break
                
                audio_path = os.path.join(folder_path, audio_file)
                output_name = os.path.splitext(audio_file)[0] + ".mid"
                midi_output = os.path.join(output_dir, output_name)
                
                self.root.after(0, lambda msg=f"正在转换 {audio_file} ({i+1}/{len(audio_files)})": self.status_var.set(msg))
                
                try:
                    # 使用正确的PianoTrans路径和参数
                    cmd = [piano_trans_path, audio_path]
                    working_dir = os.path.dirname(piano_trans_path)
                    
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=False,  # 使用二进制模式避免编码问题
                        cwd=working_dir, 
                        timeout=600,  # 增加超时时间到10分钟
                    )
                    
                    # 处理输出
                    stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
                    stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                    
                    # 解析实际输出文件路径
                    actual_output = None
                    for line in stdout.splitlines():
                        if 'Write out to ' in line:
                            actual_output = line.split('Write out to ', 1)[-1].strip()
                            break
                    if not actual_output:
                        # PianoTrans通常输出为 原文件名追加 .mid
                        guess_out = audio_path + ".mid"
                        if os.path.exists(guess_out):
                            actual_output = guess_out
                    # 若实际输出存在而与目标不同，执行重命名/移动
                    if actual_output and os.path.exists(actual_output) and actual_output != midi_output:
                        try:
                            os.replace(actual_output, midi_output)
                            stdout += f"\nRenamed output to: {midi_output}"
                        except Exception:
                            pass
                    
                    if os.path.exists(midi_output):
                        success_count += 1
                        self.root.after(0, lambda msg=f"转换成功: {audio_file}": self.log(msg, "SUCCESS"))
                    else:
                        error_detail = stderr if stderr else stdout
                        self.root.after(0, lambda msg=f"转换失败: {audio_file} - {error_detail}": self.log(msg, "ERROR"))
                
                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda msg=f"转换超时: {audio_file}": self.log(msg, "WARNING"))
                except Exception as e:
                    self.root.after(0, lambda msg=f"转换错误 {audio_file}: {str(e)}": self.log(msg, "ERROR"))
            
            self.root.after(0, lambda: self._batch_convert_complete(success_count, len(audio_files), output_dir))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"批量转换失败: {str(e)}", "ERROR"))
    
    def _batch_convert_complete(self, success_count, total_count, output_dir):
        """批量转换完成"""
        self.status_var.set("批量转换完成")
        messagebox.showinfo("批量转换完成", 
                          f"转换完成！\n成功: {success_count}/{total_count}\n输出目录: {output_dir}")
        self.log(f"批量转换完成: {success_count}/{total_count} 成功", "SUCCESS")
    
    def convert_mp3_to_midi(self):
        """使用新的音频转换器转换音频到MIDI"""
        audio_path = self.mp3_path_var.get()
        if not audio_path:
            messagebox.showerror("错误", "请先选择音频文件")
            return
        
        if not os.path.exists(audio_path):
            messagebox.showerror("错误", "音频文件不存在")
            return
        
        # 分支策略：仅当检测到PianoTrans.py脚本存在时才使用新转换器
        use_new_converter = False
        if self.audio_converter:
            try:
                script_path = self.audio_converter.find_pianotrans_python()
                if script_path and os.path.exists(script_path):
                    use_new_converter = True
                else:
                    self.log("未检测到PianoTrans.py脚本，改用exe方案", "INFO")
            except Exception:
                self.log("检测PianoTrans脚本失败，改用exe方案", "WARNING")
        
        if use_new_converter:
            self.log("使用新的音频转换器...", "INFO")
            self._convert_with_new_converter(audio_path)
        elif self.pianotrans_config:
            self.log("使用PianoTrans配置方法(Exe，无 -o 参数，自动解析输出)...", "INFO")
            self._convert_with_pianotrans_config(audio_path)
        else:
            self.log("使用传统PianoTrans方法(Exe)...", "INFO")
            self._convert_with_traditional_method(audio_path)
    
    def _convert_with_pianotrans_config(self, audio_path):
        """使用PianoTrans配置方法"""
        try:
            # 获取输出路径
            output_dir = os.path.dirname(audio_path)
            output_name = os.path.splitext(os.path.basename(audio_path))[0]
            midi_output = os.path.join(output_dir, f"{output_name}.mid")
            
            self.log("开始转换音频到MIDI...", "INFO")
            self.status_var.set("正在转换...")
            
            # 异步转换
            def progress_callback(message):
                self.root.after(0, lambda: self.log(f"转换进度: {message}", "INFO"))
            
            def complete_callback(success, output_path):
                if success:
                    self.root.after(0, lambda: self._conversion_complete(output_path))
                else:
                    self.root.after(0, lambda: self._conversion_error("转换失败"))
            
            self.pianotrans_config.convert_audio_to_midi_async(
                audio_path, 
                midi_output, 
                progress_callback, 
                complete_callback
            )
            
        except Exception as e:
            self.log(f"转换失败: {str(e)}", "ERROR")
            self._conversion_error(f"转换失败: {str(e)}")
    
    def _convert_with_new_converter(self, audio_path):
        """使用新的音频转换器"""
        try:
            # 获取输出路径
            output_dir = os.path.dirname(audio_path)
            output_name = os.path.splitext(os.path.basename(audio_path))[0]
            midi_output = os.path.join(output_dir, f"{output_name}.mid")
            
            self.log("开始转换音频到MIDI...", "INFO")
            self.status_var.set("正在转换...")
            
            # 异步转换
            def progress_callback(message):
                self.root.after(0, lambda: self.log(f"转换进度: {message}", "INFO"))
            
            def complete_callback(success, output_path):
                if success:
                    self.root.after(0, lambda: self._conversion_complete(output_path))
                else:
                    self.root.after(0, lambda: self._conversion_error("转换失败"))
            
            self.audio_converter.convert_audio_to_midi_async(
                audio_path, 
                midi_output, 
                progress_callback, 
                complete_callback
            )
            
        except Exception as e:
            self.log(f"转换失败: {str(e)}", "ERROR")
            self._conversion_error(f"转换失败: {str(e)}")
    
    def _convert_with_traditional_method(self, audio_path):
        """使用传统PianoTrans方法（备用）"""
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
        
        self.log("开始转换音频到MIDI...", "INFO")
        self.status_var.set("正在转换...")
        
        # 在新线程中执行转换
        convert_thread = threading.Thread(target=self._convert_mp3_thread, args=(audio_path, piano_trans_path))
        convert_thread.daemon = True
        convert_thread.start()
    
    def _convert_mp3_thread(self, audio_path, piano_trans_path):
        """在后台线程中转换音频"""
        try:
            # 获取输出目录
            output_dir = os.path.dirname(audio_path)
            output_name = os.path.splitext(os.path.basename(audio_path))[0]
            
            # 构建输出路径
            midi_output = os.path.join(output_dir, f"{output_name}.mid")
            
            # 检查模型文件是否存在
            model_path = os.path.join(os.path.dirname(piano_trans_path), "piano_transcription_inference_data", "note_F1=0.9677_pedal_F1=0.9186.pth")
            if not os.path.exists(model_path):
                # 尝试其他可能的路径
                alt_model_paths = [
                    # 标准路径
                    os.path.join(os.path.dirname(piano_trans_path), "piano_transcription_inference_data", "note_F1=0.9677_pedal_F1=0.9186.pth"),
                    # 嵌套路径（当前错误路径）
                    os.path.join(os.path.dirname(piano_trans_path), "PianoTrans-v1.0", "piano_transcription_inference_data", "note_F1=0.9677_pedal_F1=0.9186.pth"),
                    # 相对路径
                    "PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth",
                    # 绝对路径
                    "D:/AutoPiano/PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth",
                    # 当前工作目录
                    os.path.join(os.getcwd(), "PianoTrans-v1.0", "piano_transcription_inference_data", "note_F1=0.9677_pedal_F1=0.9186.pth"),
                    os.path.join(os.getcwd(), "piano_transcription_inference_data", "note_F1=0.9677_pedal_F1=0.9186.pth"),
                ]
                
                for alt_path in alt_model_paths:
                    if os.path.exists(alt_path):
                        model_path = alt_path
                        self.log(f"找到模型文件: {model_path}", "INFO")
                        break
                
                if not os.path.exists(model_path):
                    # 尝试搜索整个PianoTrans目录
                    piano_trans_dir = os.path.dirname(piano_trans_path)
                    for root, dirs, files in os.walk(piano_trans_dir):
                        if "note_F1=0.9677_pedal_F1=0.9186.pth" in files:
                            model_path = os.path.join(root, "note_F1=0.9677_pedal_F1=0.9186.pth")
                            self.log(f"搜索到模型文件: {model_path}", "INFO")
                            break
                    
                    if not os.path.exists(model_path):
                        self.root.after(0, lambda: self._conversion_error(f"找不到PianoTrans模型文件，请确保模型文件存在。\n\n已尝试的路径:\n" + "\n".join(alt_model_paths)))
                        return
            
            # 调用PianoTrans - 使用正确的参数格式
            cmd = [piano_trans_path, audio_path]
            
            # 设置工作目录为PianoTrans所在目录
            working_dir = os.path.dirname(piano_trans_path)
            
            # 运行转换命令
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=False,  # 使用二进制模式避免编码问题
                cwd=working_dir, 
                timeout=600,  # 增加超时时间到10分钟
            )
            
            # 处理输出
            stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
            
            # 解析实际输出文件路径
            actual_output = None
            for line in stdout.splitlines():
                if 'Write out to ' in line:
                    actual_output = line.split('Write out to ', 1)[-1].strip()
                    break
            if not actual_output:
                # PianoTrans通常输出为 原文件名追加 .mid
                guess_out = audio_path + ".mid"
                if os.path.exists(guess_out):
                    actual_output = guess_out
            # 若实际输出存在而与目标不同，执行重命名/移动
            if actual_output and os.path.exists(actual_output) and actual_output != midi_output:
                try:
                    os.replace(actual_output, midi_output)
                    stdout += f"\nRenamed output to: {midi_output}"
                except Exception:
                    pass
            
            if os.path.exists(midi_output):
                self.root.after(0, lambda: self._conversion_complete(midi_output))
            else:
                error_msg = f"转换失败: {stderr if stderr else '未知错误'}"
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
        self.log(f"音频转换完成: {midi_path}", "SUCCESS")
        self.status_var.set("转换完成，正在生成LRCp…")
        self.analyze_midi_file(midi_path)
        # 自动继续转换为LRCp
        self.convert_midi_to_lrcp(midi_path)
    
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
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("正在播放...")
        
        # 在新线程中播放
        self.playback_thread = threading.Thread(target=self._play_midi_thread)
        self.playback_thread.daemon = True
        self.playback_thread.start()
    
    def _play_midi_thread(self):
        """在后台线程中播放MIDI"""
        try:
            # 使用pygame播放MIDI文件
            pygame.mixer.music.load(self.midi_file)
            pygame.mixer.music.play()
            
            start_time = time.time()
            
            # 获取MIDI文件信息用于进度显示
            try:
                midi = mido.MidiFile(self.midi_file)
                total_time = midi.length
            except:
                total_time = 60.0  # 默认1分钟
            
            # 播放循环
            while self.is_playing and pygame.mixer.music.get_busy():
                # 更新进度条和时间显示
                current_time = time.time() - start_time
                progress = min(100, (current_time / total_time) * 100)
                
                current_str = time.strftime("%M:%S", time.gmtime(current_time))
                total_str = time.strftime("%M:%S", time.gmtime(total_time))
                
                self.root.after(0, lambda p=progress, c=current_str, t=total_str: self._update_progress(p, c, t))
                
                time.sleep(0.1)  # 更新频率
            
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
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.time_var.set("00:00 / 00:00")
        self.status_var.set("播放完成")
        self.log("MIDI播放完成", "SUCCESS")
    
    def _playback_error(self, error_msg):
        """播放错误处理"""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("播放失败")
        self.log(f"播放错误: {error_msg}", "ERROR")
        messagebox.showerror("播放失败", error_msg)
    
    def pause_midi(self):
        """暂停播放"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.pause_button.config(text="继续")
            self.status_var.set("已暂停")
            self.log("MIDI播放已暂停", "INFO")
        else:
            pygame.mixer.music.unpause()
            self.pause_button.config(text="暂停")
            self.status_var.set("正在播放")
            self.log("MIDI播放已继续", "INFO")
    
    def stop_midi(self):
        """停止播放"""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.time_var.set("00:00 / 00:00")
        self.status_var.set("已停止")
        self.log("MIDI播放已停止", "INFO")
    
    def toggle_auto_play(self):
        """切换自动弹琴模式（外部模块倒计时）。"""
        # 若正在倒计时，则取消
        if hasattr(self, '_countdown') and self._countdown and self._countdown.active:
            self._countdown.cancel()
            return
        # 已在演奏 → 直接停止
        if getattr(self, 'is_auto_playing', False):
            self.stop_auto_play()
            return
        # 选择模式与校验
        mode_var = getattr(self, 'play_mode_var', None)
        mode = mode_var.get() if mode_var else 'midi'
        def _has_lrcp():
            return hasattr(self, 'score_events') and bool(self.score_events)
        def _has_midi():
            return bool(self.midi_file and os.path.exists(self.midi_file))
        if mode == 'lrcp' and not _has_lrcp():
            messagebox.showerror("错误", "请先加载LRCp乐谱文件")
            return
        if mode == 'midi' and not _has_midi():
            messagebox.showerror("错误", "请先选择MIDI文件")
            return
        # 选择目标启动函数
        if mode == 'lrcp':
            target_start = self.start_auto_play
        elif mode == 'midi':
            target_start = self.start_auto_play_midi
        else:
            messagebox.showerror("错误", "请选择演奏模式")
            return
        # 读取倒计时秒数
        countdown_secs = 5
        try:
            countdown_secs = int(self.config.get('settings', {}).get('countdown_secs', 5))
        except Exception:
            countdown_secs = 5
        if _CountdownTimer is None:
            # 回退：直接启动
            target_start()
            return
        # 配置倒计时
        def _on_tick(rem: int):
            self.status_var.set(f"即将开始自动弹琴：{rem} 秒… 请切换到游戏界面")
            self.log(f"倒计时：{rem}")
            self.auto_play_button.config(text="取消倒计时", state=tk.NORMAL)
        def _on_finish():
            self.auto_play_button.config(text="停止弹琴", state=tk.NORMAL)
            try:
                target_start()
            except Exception as e:
                self.log(f"启动自动弹琴失败: {e}", "ERROR")
        def _on_cancel():
            self.status_var.set("倒计时已取消")
            self.log("倒计时已取消", "INFO")
            self.auto_play_button.config(text="自动弹琴", state=tk.NORMAL)
        self._countdown = _CountdownTimer(self.root, countdown_secs, _on_tick, _on_finish, _on_cancel)
        self._countdown.start()
    
    def start_auto_play(self):
        """开始自动弹琴"""
        self.is_auto_playing = True
        self.is_auto_paused = False
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
        self.is_auto_paused = False
        self.auto_play_button.config(text="自动弹琴")
        self.status_var.set("自动弹琴已停止")
        self.log("自动弹琴已停止", "INFO")
    
    def _auto_play_thread(self):
        """自动弹琴线程 - 基于时间轴事件"""
        try:
            if not hasattr(self, 'score_events') or not self.score_events:
                self.root.after(0, lambda: self._auto_play_error("没有加载乐谱文件"))
                return
            
            # 开始自动弹琴
            start_time = time.time()
            
            # 创建按键发送器
            key_sender = KeySender()
            
            # 构造动作表 (time, type, keys)
            actions: List[Tuple[float, str, List[str]]] = []
            for event in self.score_events:
                actions.append((event.start, 'press', event.keys))
                actions.append((event.end, 'release', event.keys))
            
            # 按时间排序
            actions.sort(key=lambda x: x[0])
            
            # 开始执行（合并同一时间戳批处理）
            idx = 0
            jitter = 0.003
            while idx < len(actions) and self.is_auto_playing:
                # 若处于暂停，等待恢复
                while self.is_auto_paused and self.is_auto_playing:
                    time.sleep(0.05)
                # 目标时间（按速度缩放）
                group_time = actions[idx][0] / max(0.01, float(self.tempo_var.get() or 1.0))
                # 等待到该批次时间点
                while True:
                    # 暂停时让等待循环让出CPU
                    if self.is_auto_paused:
                        time.sleep(0.05)
                        continue
                    now = time.time()
                    target = start_time + group_time
                    wait = target - now
                    if wait > 0:
                        time.sleep(min(wait, 0.001))
                    else:
                        break
                # 收集同一时间片的所有动作
                j = idx
                press_keys: List[str] = []
                release_keys: List[str] = []
                while j < len(actions) and abs(actions[j][0] / max(0.01, float(self.tempo_var.get() or 1.0)) - group_time) <= jitter:
                    _, typ, keys = actions[j]
                    if typ == 'release':
                        release_keys.extend(keys)
                    else:
                        press_keys.extend(keys)
                    j += 1
                # 先释放再按下，减少重叠干扰
                if release_keys:
                    key_sender.release(release_keys)
                if press_keys:
                    key_sender.press(press_keys)
                idx = j
            
            key_sender.release_all()
            self.root.after(0, self._auto_play_complete)
            
        except Exception as e:
            error_msg = f"自动弹琴失败: {str(e)}"
            self.root.after(0, lambda: self._auto_play_error(error_msg))
    
    def _send_note_key(self, note):
        """根据MIDI音符映射到21键并返回PC键位"""
        try:
            token = self._token_from_midi_note(note)
            if token and token in self.key_mapping:
                return self.key_mapping[token]
            return None
        except Exception as e:
            self.log(f"发送按键失败: {str(e)}", "ERROR")
            return None
    
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
        self._auto_advance_next()
    
    def _auto_advance_next(self):
        """自动连播：若当前来自播放列表，自动跳到下一首并开始演奏"""
        try:
            if getattr(self, 'current_playlist_index', -1) >= 0 and self.playlist_items:
                next_index = self.current_playlist_index + 1
                if next_index < len(self.playlist_items):
                    self._play_playlist_item(next_index)
                    self.log("自动切换到下一首", "INFO")
                else:
                    self.log("列表已结束", "INFO")
        except Exception:
            pass
    
    def _auto_play_error(self, error_msg):
        """自动弹琴错误处理"""
        self.is_auto_playing = False
        self.auto_play_button.config(text="自动弹琴")
        self.status_var.set("自动弹琴失败")
        self.log(f"自动弹琴错误: {error_msg}", "ERROR")
        messagebox.showerror("自动弹琴失败", error_msg)
    
    def start_auto_play_midi(self):
        """开始自动弹琴 - MIDI模式"""
        self.is_auto_playing = True
        self.auto_play_button.config(text="停止弹琴")
        self.status_var.set("自动弹琴中... (MIDI模式)")
        self.log("开始自动弹琴 (MIDI模式)", "INFO")
        
        # 在新线程中执行自动弹琴
        self.auto_play_thread = threading.Thread(target=self._auto_play_midi_thread)
        self.auto_play_thread.daemon = True
        self.auto_play_thread.start()
    
    def _auto_play_midi_thread(self):
        """自动弹琴线程 - MIDI模式（使用pretty_midi获得精确时间）"""
        try:
            key_sender = KeySender()
            actions: List[Tuple[float, str, List[str]]] = []  # (time, 'press'/'release', [keys])
            use_pretty = False
            try:
                import pretty_midi
                use_pretty = True
            except ImportError:
                use_pretty = False
            
            if use_pretty:
                pm = pretty_midi.PrettyMIDI(self.midi_file)
                # 先按时间片聚合
                groups: Dict[float, List[Tuple[str, str, float, float]]] = {}
                # 收集所有音符事件
                all_notes = []
                for inst in pm.instruments:
                    for n in inst.notes:
                        token = self._token_from_midi_note(n.pitch)
                        if not token:
                            continue
                        s = round(float(n.start), 4)
                        e = round(float(n.end), 4)
                        if e < s:
                            e = s
                        pc_key = self.key_mapping.get(token)
                        if not pc_key:
                            continue
                        all_notes.append((token, pc_key, s, e))
                
                # 按开始时间排序
                all_notes.sort(key=lambda x: x[2])
                
                # 过滤重复单音并合并为和弦
                i = 0
                while i < len(all_notes):
                    current_note = all_notes[i]
                    current_token, current_key, current_s, current_e = current_note
                    
                    # 查找时间窗口内的重复单音
                    time_window = self.time_window_var.get() / 1000.0  # 从GUI获取时间窗口
                    min_chord_duration = self.min_chord_duration_var.get()  # 从GUI获取最小和弦时长
                    
                    j = i + 1
                    similar_notes = [current_note]
                    
                    while j < len(all_notes):
                        next_note = all_notes[j]
                        next_token, next_key, next_s, next_e = next_note
                        
                        # 检查是否在时间窗口内且是重复单音
                        if (next_s - current_s) <= time_window and next_token == current_token:
                            similar_notes.append(next_note)
                            j += 1
                        else:
                            break
                    
                    if len(similar_notes) > 1:
                        # 有重复单音，合并为和弦
                        min_start = min(note[2] for note in similar_notes)
                        max_end = max(note[3] for note in similar_notes)
                        duration = max_end - min_start
                        
                        # 确保和弦持续时间不少于0.5秒
                        if duration < min_chord_duration:
                            max_end = min_start + min_chord_duration
                        
                        # 将重复单音替换为和弦
                        chord_key = self._digit_to_chord_key(self._digit_from_token(current_token))
                        if chord_key:
                            # 轻微延长和弦按下/释放
                            chord_lead = 0.03
                            chord_tail = 0.07
                            s_min_ext = max(0.0, min_start - chord_lead)
                            e_max_ext = max_end + chord_tail
                            actions.append((s_min_ext, 'press', [chord_key]))
                            actions.append((e_max_ext, 'release', [chord_key]))
                        
                        # 跳过已处理的重复单音
                        i = j
                    else:
                        # 无重复，按原逻辑处理
                        g = self._quantize_time(current_s, 0.05)
                        groups.setdefault(g, []).append((current_token, current_key, current_s, current_e))
                        i += 1
                
                # 对剩余的音符按时间片聚合
                groups: Dict[float, List[Tuple[str, str, float, float]]] = {}
                for inst in pm.instruments:
                    for note in inst.notes:
                        token = self._token_from_midi_note(note.pitch)
                        if not token:
                            continue
                        s = round(float(note.start), 4)
                        e = round(float(note.end), 4)
                        if e < s:
                            e = s
                        g = self._quantize_time(s, 0.05)
                        pc_key = self.key_mapping.get(token)
                        if not pc_key:
                            continue
                        groups.setdefault(g, []).append((token, pc_key, s, e))
                # 对每个时间片尝试识别和弦
                for g_time in sorted(groups.keys()):
                    items = groups[g_time]
                    tokens = [t for (t, _, __, ___) in items]
                    chord = self._detect_chord_label(tokens)
                    if chord and chord in self.key_mapping:
                        # 合并为和弦：使用底栏键位，时长覆盖该组最小start到最大end
                        s_min = min(s for (_, __, s, ___) in items)
                        e_max = max(e for (_, __, ___, e) in items)
                        # 轻微延长和弦按下/释放
                        chord_lead = 0.03
                        chord_tail = 0.07
                        s_min_ext = max(0.0, s_min - chord_lead)
                        # 将和弦持续时间翻倍（基于原始时长）
                        orig_dur = max(0.0, e_max - s_min)
                        e_dbl = s_min + 2.0 * orig_dur
                        e_dbl_ext = e_dbl + chord_tail
                        chord_key = self.key_mapping.get(chord)
                        if chord_key:
                            actions.append((s_min_ext, 'press', [chord_key]))
                            actions.append((e_dbl_ext, 'release', [chord_key]))
                    # 无论是否识别为和弦，都保留逐音触发（不阻断单音）
                    short_thr = 0.06
                    for (tok, pc_key, s, e) in items:
                        if (e - s) < short_thr:
                            # 短促高频单音：改触发底栏和弦键（按度数）
                            d = self._digit_from_token(tok)
                            chord_key = self._digit_to_chord_key(d)
                            if chord_key:
                                lead, tail = 0.02, 0.05
                                s_ext = max(0.0, s - lead)
                                # 翻倍短音持续
                                orig_d = max(0.0, e - s)
                                e_dbl = s + 2.0 * orig_d
                                e_ext = e_dbl + tail
                                actions.append((s_ext, 'press', [chord_key]))
                                actions.append((e_ext, 'release', [chord_key]))
                                continue
                        # 常规：逐音触发
                        actions.append((s, 'press', [pc_key]))
                        actions.append((e, 'release', [pc_key]))
            else:
                # 退化实现：沿用原mido解析但仅生成开始/结束事件
                midi = mido.MidiFile(self.midi_file)
                tempo = 500000
                tracks_events = []
                for track in midi.tracks:
                    track_time = 0
                    active = {}
                    for msg in track:
                        if msg.type == 'set_tempo':
                            tempo = msg.tempo
                        track_time += msg.time
                        if msg.type == 'note_on' and msg.velocity > 0:
                            active[msg.note] = track_time
                        elif msg.type in ('note_off',) or (msg.type == 'note_on' and msg.velocity == 0):
                            if msg.note in active:
                                s = mido.tick2second(active[msg.note], midi.ticks_per_beat, tempo)
                                e = mido.tick2second(track_time, midi.ticks_per_beat, tempo)
                                token = self._token_from_midi_note(msg.note)
                                if token:
                                    pc_key = self.key_mapping.get(token)
                                    if pc_key:
                                        # 短促单音改触发底栏和弦键
                                        if (e - s) < 0.06:
                                            d = self._digit_from_token(token)
                                            chord_key = self._digit_to_chord_key(d)
                                            if chord_key:
                                                s_ext = max(0.0, s - 0.02)
                                                # 翻倍短音持续
                                                orig_d = max(0.0, e - s)
                                                e_dbl = s + 2.0 * orig_d
                                                e_ext = e_dbl + 0.05
                                                actions.append((s_ext, 'press', [chord_key]))
                                                actions.append((e_ext, 'release', [chord_key]))
                                            else:
                                                actions.append((s, 'press', [pc_key]))
                                                actions.append((e, 'release', [pc_key]))
                                        else:
                                            actions.append((s, 'press', [pc_key]))
                                            actions.append((e, 'release', [pc_key]))
                                active.pop(msg.note, None)
            
            # 排序并按速度缩放
            actions.sort(key=lambda x: x[0])
            start_time = time.time()
            idx = 0
            jitter = 0.003
            while idx < len(actions) and self.is_auto_playing:
                # 若处于暂停，等待恢复
                while self.is_auto_paused and self.is_auto_playing:
                    time.sleep(0.05)
                # 目标时间（按速度缩放）
                _speed = float(self.tempo_var.get() or 1.0)
                group_time = actions[idx][0] / max(0.01, _speed)
                # 等待到该批次时间点
                while True:
                    if self.is_auto_paused:
                        time.sleep(0.05)
                        continue
                    now = time.time()
                    target = start_time + group_time
                    wait = target - now
                    if wait > 0:
                        time.sleep(min(wait, 0.001))
                    else:
                        break
                # 收集同一时间片的所有动作
                j = idx
                press_keys: List[str] = []
                release_keys: List[str] = []
                while j < len(actions) and abs(actions[j][0] / max(0.01, _speed) - group_time) <= jitter:
                    _, typ, keys = actions[j]
                    if typ == 'release':
                        release_keys.extend(keys)
                    else:
                        press_keys.extend(keys)
                    j += 1
                # 先释放再按下
                if release_keys:
                    key_sender.release(release_keys)
                if press_keys:
                    key_sender.press(press_keys)
                idx = j
            
            key_sender.release_all()
            self.root.after(0, self._auto_play_complete)
        except Exception as e:
            error_msg = f"自动弹琴失败: {str(e)}"
            self.root.after(0, lambda: self._auto_play_error(error_msg))
    
    def analyze_score_file(self):
        """分析乐谱文件信息并更新显示"""
        if not hasattr(self, 'score_events') or not self.score_events:
            self.score_info_var.set("乐谱信息: 未加载")
            return
        
        total_events = len(self.score_events)
        total_notes = sum(len(event.keys) for event in self.score_events)
        total_time = self.score_events[-1].end if self.score_events else 0
        
        self.score_info_var.set(f"乐谱信息: 共 {total_events} 个事件，包含 {total_notes} 个音符，总时长 {total_time:.2f} 秒")
        self.log(f"乐谱文件分析完成: 共 {total_events} 个事件，包含 {total_notes} 个音符，总时长 {total_time:.2f} 秒", "INFO")
    
    def on_closing(self):
        """关闭程序时的处理"""
        if self.is_playing:
            self.stop_midi()
        if self.is_auto_playing:
            self.stop_auto_play()
        
        # 保存配置
        try:
            # 记录 sash 位置与比例
            try:
                if hasattr(self, '_content_paned') and self._content_paned:
                    w = max(1, self._content_paned.winfo_width())
                    p = self._content_paned.sashpos(0)
                    self.config.setdefault('ui', {})['sash_ratio'] = round(p / w, 4)
                    self.config['ui']['sashpos'] = int(p)
            except Exception:
                pass
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except:
            pass
        # 销毁侧边栏窗口
        try:
            if hasattr(self, '_sidebar_win') and self._sidebar_win:
                self._sidebar_win.destroy()
        except Exception:
            pass
        # 卸载全局热键
        try:
            if getattr(self, '_global_hotkey_handle', None) is not None:
                keyboard.remove_hotkey(self._global_hotkey_handle)
        except Exception:
            pass
        
        self.root.destroy()
    
    def run(self):
        """运行程序"""
        self.log("MeowField_AutoPiano启动成功", "SUCCESS")
        self.log("支持功能: MP3转MIDI、MIDI播放、自动弹琴、批量转换", "INFO")
        self.root.mainloop()

    def add_to_playlist(self):
        """添加乐谱到播放列表"""
        file_path = filedialog.askopenfilename(
            title="选择乐谱文件",
            filetypes=[
                ("乐谱文件", "*.lrcp"),
                ("MIDI文件", "*.mid;*.midi"),
                ("音频文件", "*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self._add_file_to_playlist(file_path)
    
    def _add_file_to_playlist(self, file_path):
        """添加文件到播放列表"""
        try:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 确定文件类型和时长
            file_type = "未知"
            duration = "未知"
            
            if file_ext == '.lrcp':
                file_type = "LRCp乐谱"
                # 解析乐谱获取时长
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        score_text = f.read()
                    events = parse_score(score_text)
                    if events:
                        duration = f"{events[-1].end:.1f}秒"
                except:
                    duration = "解析失败"
            elif file_ext in ['.mid', '.midi']:
                file_type = "MIDI文件"
                try:
                    midi = mido.MidiFile(file_path)
                    duration = f"{midi.length:.1f}秒"
                except:
                    duration = "解析失败"
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                file_type = "音频文件"
                duration = "需转换"
            
            # 添加到播放列表
            item = {
                'path': file_path,
                'name': file_name,
                'type': file_type,
                'duration': duration,
                'status': '未播放'
            }
            
            self.playlist_items.append(item)
            self._update_playlist_display()
            self.log(f"已添加到播放列表: {file_name}", "INFO")
            
        except Exception as e:
            self.log(f"添加文件到播放列表失败: {str(e)}", "ERROR")
    
    def remove_from_playlist(self):
        """从播放列表中移除选中的项目"""
        selected = self.playlist_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要移除的项目")
            return
        
        for item_id in selected:
            item = self.playlist_tree.item(item_id)
            index = int(item['values'][0]) - 1
            if 0 <= index < len(self.playlist_items):
                removed_item = self.playlist_items.pop(index)
                self.log(f"已从播放列表移除: {removed_item['name']}", "INFO")
        
        self._update_playlist_display()
    
    def clear_playlist(self):
        """清空播放列表"""
        if messagebox.askyesno("确认", "确定要清空播放列表吗？"):
            self.playlist_items.clear()
            self.current_playlist_index = -1
            self._update_playlist_display()
            self.log("播放列表已清空", "INFO")
    
    def save_playlist(self):
        """保存播放列表到文件"""
        if not self.playlist_items:
            messagebox.showwarning("提示", "播放列表为空，无法保存")
            return
        
        filename = filedialog.asksaveasfilename(
            title="保存播放列表",
            defaultextension=".m3u8",
            filetypes=[("播放列表", "*.m3u8"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for item in self.playlist_items:
                        f.write(f"#EXTINF:-1,{item['name']}\n")
                        f.write(f"{item['path']}\n")
                
                self.log(f"播放列表已保存到: {filename}", "SUCCESS")
                messagebox.showinfo("成功", f"播放列表已保存到:\n{filename}")
            except Exception as e:
                self.log(f"保存播放列表失败: {str(e)}", "ERROR")
    
    def load_playlist(self):
        """从文件加载播放列表"""
        filename = filedialog.askopenfilename(
            title="加载播放列表",
            filetypes=[("播放列表", "*.m3u8"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                self.playlist_items.clear()
                with open(filename, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                current_path = None
                for line in lines:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if current_path is None:
                        current_path = line
                        if os.path.exists(current_path):
                            self._add_file_to_playlist(current_path)
                        current_path = None
                
                self.current_playlist_index = -1
                self._update_playlist_display()
                self.log(f"播放列表已从文件加载: {filename}", "SUCCESS")
                
            except Exception as e:
                self.log(f"加载播放列表失败: {str(e)}", "ERROR")
    
    def _update_playlist_display(self):
        """更新播放列表显示"""
        # 清空现有显示
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        
        # 重新填充
        for i, item in enumerate(self.playlist_items):
            status = "当前播放" if i == self.current_playlist_index else item['status']
            self.playlist_tree.insert("", "end", values=(
                i + 1,
                item['name'],
                item['type'],
                item['duration'],
                status
            ))
        # 斑马纹
        try:
            if _tbl_striped:
                _tbl_striped(self.playlist_tree)
        except Exception:
            pass
    
    def on_playlist_double_click(self, event):
        """播放列表双击事件"""
        selected = self.playlist_tree.selection()
        if selected:
            item_id = selected[0]
            item = self.playlist_tree.item(item_id)
            index = int(item['values'][0]) - 1
            if 0 <= index < len(self.playlist_items):
                self._play_playlist_item(index)
    
    def _play_playlist_item(self, index):
        """播放播放列表中的指定项目"""
        if not (0 <= index < len(self.playlist_items)):
            return
        
        item = self.playlist_items[index]
        file_path = item['path']
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.lrcp':
                # 加载LRCp乐谱
                with open(file_path, "r", encoding="utf-8") as f:
                    score_text = f.read()
                self.score_events = parse_score(score_text)
                self.score_path_var.set(file_path)
                self.analyze_score_file()
                self.log(f"已加载乐谱: {item['name']}", "SUCCESS")
                
            elif file_ext in ['.mid', '.midi']:
                # 加载MIDI文件
                self.midi_file = file_path
                self.midi_path_var.set(file_path)
                self.analyze_midi_file(file_path)
                self.log(f"已加载MIDI: {item['name']}", "SUCCESS")
                
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']:
                # 音频文件，询问是否转换
                if messagebox.askyesno("转换提示", f"音频文件 {item['name']} 需要转换为MIDI才能播放，是否现在转换？"):
                    self.mp3_path_var.set(file_path)
                    self.convert_mp3_to_midi()
                    return
            
            # 更新播放列表状态
            self.current_playlist_index = index
            self._update_playlist_display()
            
            # 直接开始自动弹琴
            self.start_auto_play()
            
        except Exception as e:
            self.log(f"播放列表项目加载失败: {str(e)}", "ERROR")
    
    def play_previous(self):
        """播放上一首"""
        if not self.playlist_items:
            return
        
        if self.current_playlist_index > 0:
            self._play_playlist_item(self.current_playlist_index - 1)
        elif self.loop_play:
            self._play_playlist_item(len(self.playlist_items) - 1)
    
    def play_next(self):
        """播放下一首"""
        if not self.playlist_items:
            return
        
        if self.current_playlist_index < len(self.playlist_items) - 1:
            self._play_playlist_item(self.current_playlist_index + 1)
        elif self.loop_play:
            self._play_playlist_item(0)
    
    def toggle_random_play(self):
        """切换随机播放"""
        self.random_play = not self.random_play
        status = "开启" if self.random_play else "关闭"
        self.log(f"随机播放已{status}", "INFO")
    
    def toggle_loop_play(self):
        """切换循环播放"""
        self.loop_play = not self.loop_play
        status = "开启" if self.loop_play else "关闭"
        self.log(f"循环播放已{status}", "INFO")

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
    
    def _quantize_time(self, t: float, step: float = 0.03) -> float:
        """时间量化，默认30ms栅格（更利于聚合和弦）"""
        return round(t / step) * step

    def _group_blocks_to_lrcp(self, blocks, epsilon: float = 0.03):
        """将(start,end,token)列表按时间量化并分组，返回LRCp文本"""
        groups: Dict[Tuple[float, float], List[str]] = {}
        for start, end, token in blocks:
            qs = self._quantize_time(start)
            qe = self._quantize_time(end)
            key = (qs, qe)
            groups.setdefault(key, []).append(token)
        lines: List[str] = []
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
        epsilon_chord = 0.08
        for (qs, qe), tokens in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
            start_str = self._seconds_to_timestamp(qs)
            end_str = self._seconds_to_timestamp(qe)
            tokens.sort()
            label = _detect_chord_label(tokens)
            # 和弦不阻断单音：输出 和弦名 + 单音tokens
            payload = (label + ' ' if label else '') + ' '.join(tokens)
            thr = epsilon_chord if label else epsilon
            # 和弦时间轻微延长
            chord_lead = 0.03
            chord_tail = 0.07
            if label:
                qs_ext = max(0.0, qs - chord_lead)
                qe_ext = qe + chord_tail
                start_str_ext = self._seconds_to_timestamp(qs_ext)
                end_str_ext = self._seconds_to_timestamp(qe_ext)
                if abs(qe_ext - qs_ext) <= thr:
                    lines.append(f"[{start_str_ext}] {payload}\n")
                else:
                    lines.append(f"[{start_str_ext}][{end_str_ext}] {payload}\n")
            else:
                if abs(qe - qs) <= thr:
                    lines.append(f"[{start_str}] {payload}\n")
                else:
                    lines.append(f"[{start_str}][{end_str}] {payload}\n")
        return ''.join(lines)
    
    def _convert_with_pretty_midi(self, midi_path):
        """使用pretty_midi库转换MIDI"""
        try:
            import pretty_midi
            
            pm = pretty_midi.PrettyMIDI(midi_path)
            blocks = []
            for inst in pm.instruments:
                for note in inst.notes:
                    token = self._token_from_midi_note(note.pitch)
                    if not token:
                        continue
                    start = round(note.start, 4)
                    end = round(note.end, 4)
                    if end < start:
                        end = start
                    blocks.append((start, end, token))
            
            # 生成LRCp内容
            lrcp_content = f"# 从MIDI文件转换: {os.path.basename(midi_path)}\n"
            lrcp_content += f"# 转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            lrcp_content += "# 格式: [开始时间][结束时间] 音符\n\n"
            lrcp_content += self._group_blocks_to_lrcp(blocks)
            
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
        
        # 收集并分组
        blocks = []
        for event in events:
            key = self._token_from_midi_note(event['note'])
            if not key:
                continue
            blocks.append((event['start_time'], event['end_time'], key))
        content += self._group_blocks_to_lrcp(blocks)
        
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
        
        # 自动加载转换后的LRCp文件并加入自动演奏列表
        try:
            with open(lrcp_path, "r", encoding="utf-8") as f:
                score_text = f.read()
            self.score_events = parse_score(score_text)
            self.score_path_var.set(lrcp_path)
            self.analyze_score_file()
            # 加入播放列表（自动演奏列表）
            self._add_file_to_playlist(lrcp_path)
            
        except Exception as e:
            self.log(f"自动加载LRCp文件失败: {str(e)}", "ERROR")

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

    def fix_pianotrans_paths(self):
        """修复PianoTrans路径问题"""
        try:
            self.log("开始修复PianoTrans路径...", "INFO")
            
            # 导入路径修复工具
            try:
                from fix_pianotrans_paths import PianoTransPathFixer
            except ImportError:
                self.log("路径修复工具未找到，请确保fix_pianotrans_paths.py存在", "ERROR")
                return
            
            # 在新线程中执行修复
            def fix_thread():
                try:
                    fixer = PianoTransPathFixer()
                    fixed_count, total_count = fixer.fix_all_paths()
                    
                    self.root.after(0, lambda: self._path_fix_complete(fixed_count, total_count))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"路径修复失败: {str(e)}", "ERROR"))
            
            thread = threading.Thread(target=fix_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.log(f"启动路径修复失败: {str(e)}", "ERROR")
    
    def _path_fix_complete(self, fixed_count, total_count):
        """路径修复完成处理"""
        if fixed_count > 0:
            messagebox.showinfo("修复完成", 
                              f"路径修复完成！\n修复了 {fixed_count}/{total_count} 个文件\n\n"
                              f"备份文件保存在 pianotrans_backups 目录中\n"
                              f"如需恢复，请运行: python fix_pianotrans_paths.py --restore")
            self.log(f"路径修复完成: {fixed_count}/{total_count} 个文件", "SUCCESS")
        else:
            messagebox.showinfo("修复完成", "未发现需要修复的路径问题")
            self.log("未发现需要修复的路径问题", "INFO")

    # ===== 追加：映射与时间分组辅助方法（空格缩进版本） =====
    def _token_from_midi_note(self, midi_note: int) -> Optional[str]:
        """将任意MIDI音符映射为L/M/H的1-7标记（21键），含半音折叠到邻近度数）。
        - 折叠到C3~B5（48~83）
        - 48-59→L，60-71→M，72-83→H
        - 半音分组：C/C#→1, D/D#→2, E→3, F/F#→4, G/G#→5, A/A#→6, B→7
        """
        if midi_note is None:
            return None
        n = int(midi_note)
        # 折叠到C3~B5
        while n < 48:
            n += 12
        while n > 83:
            n -= 12
        # 前缀
        if 48 <= n <= 59:
            prefix = 'L'
        elif 60 <= n <= 71:
            prefix = 'M'
        elif 72 <= n <= 83:
            prefix = 'H'
        else:
            return None
        pc = n % 12
        if pc in (0, 1):
            digit = '1'
        elif pc in (2, 3):
            digit = '2'
        elif pc == 4:
            digit = '3'
        elif pc in (5, 6):
            digit = '4'
        elif pc in (7, 8):
            digit = '5'
        elif pc in (9, 10):
            digit = '6'
        else:
            digit = '7'
        return prefix + digit

    def _detect_chord_label(self, tokens: List[str]) -> Optional[str]:
        """根据度数组合识别 C/Dm/Em/F/G/Am/G7 和弦名。"""
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

    def _digit_from_token(self, token: Optional[str]) -> Optional[str]:
        if not token or len(token) != 2:
            return None
        d = token[1]
        return d if d in '1234567' else None

    def _digit_to_chord_key(self, digit: Optional[str]) -> Optional[str]:
        if not digit:
            return None
        chord_order = ['C', 'Dm', 'Em', 'F', 'G', 'Am', 'G7']
        # 1..7 -> C..G7
        try:
            chord_name = chord_order[int(digit) - 1]
        except Exception:
            return None
        key = self.key_mapping.get(chord_name)
        return key

    def _quantize_time(self, t: float, step: float = 0.03) -> float:
        """时间量化，默认30ms栅格（更利于聚合和弦）"""
        return round(t / step) * step

    def _group_blocks_to_lrcp(self, blocks, epsilon: float = 0.03):
        """将(start,end,token)列表按时间量化并分组，返回LRCp文本"""
        groups: Dict[Tuple[float, float], List[str]] = {}
        for start, end, token in blocks:
            qs = self._quantize_time(start)
            qe = self._quantize_time(end)
            key = (qs, qe)
            groups.setdefault(key, []).append(token)
        lines: List[str] = []
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
        epsilon_chord = 0.08
        for (qs, qe), tokens in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
            start_str = self._seconds_to_timestamp(qs)
            end_str = self._seconds_to_timestamp(qe)
            tokens.sort()
            label = _detect_chord_label(tokens)
            # 和弦不阻断单音：输出 和弦名 + 单音tokens
            payload = (label + ' ' if label else '') + ' '.join(tokens)
            thr = epsilon_chord if label else epsilon
            # 和弦时间轻微延长
            chord_lead = 0.03
            chord_tail = 0.07
            if label:
                qs_ext = max(0.0, qs - chord_lead)
                qe_ext = qe + chord_tail
                start_str_ext = self._seconds_to_timestamp(qs_ext)
                end_str_ext = self._seconds_to_timestamp(qe_ext)
                if abs(qe_ext - qs_ext) <= thr:
                    lines.append(f"[{start_str_ext}] {payload}\n")
                else:
                    lines.append(f"[{start_str_ext}][{end_str_ext}] {payload}\n")
            else:
                if abs(qe - qs) <= thr:
                    lines.append(f"[{start_str}] {payload}\n")
                else:
                    lines.append(f"[{start_str}][{end_str}] {payload}\n")
        return ''.join(lines)

    def _init_appearance(self):
        """初始化外观：DPI缩放、主题、密度与字体。失败时静默回退。"""
        ui_cfg = self.config.get("ui", {})
        # 1) 缩放
        try:
            self._apply_scaling(ui_cfg.get("scaling", "auto"))
        except Exception:
            pass
        # 2) 主题
        try:
            if tb is not None:
                # 初始化样式
                theme = ui_cfg.get("theme_name", "flatly")
                self._style = tb.Style(theme=theme)
            else:
                self._style = ttk.Style()
            # 预设按钮风格名
            self.accent_button_style = "Accent.TButton" if tb else "TButton"
            self.secondary_button_style = "Secondary.TButton" if tb else "TButton"
            # 记录当前主题来源
            try:
                src = "ttkbootstrap" if tb else "system ttk"
                self.log(f"外观初始化完成（{src}）", "INFO")
            except Exception:
                pass
        except Exception:
            self._style = ttk.Style()
            self.accent_button_style = "TButton"
            self.secondary_button_style = "TButton"
        # 3) 密度
        try:
            self._apply_density(ui_cfg.get("density", "comfortable"))
        except Exception:
            pass
        # 4) 字体（不改变字体族，仅按缩放微调大小）
        try:
            base = tkfont.nametofont("TkDefaultFont")
            textf = tkfont.nametofont("TkTextFont")
            headf = tkfont.nametofont("TkHeadingFont")
            # 根据 tk scaling 估计字号（保持最小 9）
            scale = float(self.root.tk.call('tk', 'scaling'))
            def _adj(f, mul=1.0):
                try:
                    size = max(9, int(f.cget('size') * scale * mul))
                    f.configure(size=size)
                except Exception:
                    pass
            _adj(base, 1.0)
            _adj(textf, 1.0)
            _adj(headf, 1.1)
        except Exception:
            pass

    def _apply_scaling(self, mode_or_factor):
        """应用缩放：'auto' 或 数字比例。优先使用 Windows DPI API。"""
        try:
            if isinstance(mode_or_factor, (int, float)):
                factor = float(mode_or_factor)
            else:
                # auto: 通过 DPI 推算
                factor = 1.0
                try:
                    # Windows 10+: 使用 shcore 获取缩放
                    shcore = ctypes.windll.shcore
                    shcore.SetProcessDpiAwareness(2)  # Per-Monitor v2
                    # 获取主屏缩放（96 为 100%）
                    user32 = ctypes.windll.user32
                    dc = user32.GetDC(0)
                    LOGPIXELSX = 88
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
                    factor = max(0.75, dpi / 96.0)
                except Exception:
                    # 回退：基于 Tk 测量
                    px_per_inch = self.root.winfo_fpixels('1i')
                    factor = max(0.75, float(px_per_inch) / 96.0)
            # 应用到 Tk
            self.root.tk.call('tk', 'scaling', factor)
            self.scaling_factor = factor
        except Exception:
            # 即使失败也不抛出
            self.scaling_factor = 1.0

    def _apply_theme(self, theme_name: str):
        """切换主题；无 ttkbootstrap 时仅记录配置。"""
        try:
            if tb is not None and hasattr(self, "_style"):
                self._style.theme_use(theme_name)
            # 更新配置
            self.config.setdefault("ui", {})["theme_name"] = theme_name
            # 同步 theme_mode（根据名称粗略判断）
            dark_set = {"darkly", "superhero", "cyborg", "solar"}
            self.config["ui"]["theme_mode"] = "dark" if theme_name in dark_set else "light"
            self.log(f"主题已切换为: {theme_name}", "INFO")
            # 主题改变后同步更新控件外观
            self._apply_appearance_to_widgets()
        except Exception as e:
            self.log(f"切换主题失败: {e}", "WARNING")

    def _apply_density(self, density: str):
        """应用密度：调整控件行高与 padding。"""
        sty = getattr(self, "_style", ttk.Style())
        if density == "compact":
            row_h = 24
            pad = 4
        else:
            row_h = 28
            pad = 6
        try:
            sty.configure("Treeview", rowheight=row_h)
            sty.configure("TButton", padding=(8, pad))
            if tb:
                sty.configure("Accent.TButton", padding=(10, pad))
                sty.configure("Secondary.TButton", padding=(8, pad))
        except Exception:
            pass
        self.config.setdefault("ui", {})["density"] = density
        # 密度改变后可按需更新
        self._apply_appearance_to_widgets()

    def _apply_appearance_to_widgets(self):
        """根据主题模式微调个别区域（如日志区）。"""
        try:
            if hasattr(self, "_log_view") and self._log_view:
                self._log_view.apply_theme()
            mode = self.config.get("ui", {}).get("theme_mode", "light")
            if hasattr(self, "log_text") and self.log_text:
                if mode == "dark":
                    self.log_text.configure(bg="#22262A", fg="#D6DEE7", insertbackground="#D6DEE7")
                else:
                    self.log_text.configure(bg="#FFFFFF", fg="#1F2D3D", insertbackground="#1F2D3D")
        except Exception:
            pass

    def toast(self, message: str, title: str = "提示", duration: int = 3000):
        """显示轻通知（若可用）。"""
        try:
            if ToastNotification is None or tb is None:
                return
            ToastNotification(title=title, message=message, duration=duration, alert=False).show_toast()
        except Exception:
            pass

    def _init_docked_sidebar_stub(self):
        """创建停靠在窗口外侧的侧边栏占位（独立窗口，不影响主界面布局）。"""
        try:
            # 创建无边框子窗口
            self._sidebar_win = tk.Toplevel(self.root)
            self._sidebar_win.overrideredirect(True)
            try:
                self._sidebar_win.wm_attributes('-toolwindow', True)
            except Exception:
                pass
            # 初始为折叠
            self._sidebar_collapsed = True
            self._sidebar_collapsed_w = 12
            self._sidebar_expanded_w = 260
            self._sidebar_container = ttk.Frame(self._sidebar_win, padding=2)
            self._sidebar_container.pack(fill=tk.BOTH, expand=True)
            # 顶部折叠把手
            topbar = ttk.Frame(self._sidebar_container)
            topbar.pack(fill=tk.X)
            self._sidebar_toggle = ttk.Button(
                topbar, text='≡ 展开/收起', width=10, style=self.accent_button_style, command=lambda: self._toggle_sidebar_stub())
            self._sidebar_toggle.pack(side=tk.LEFT, pady=4)
            try:
                if ToolTip is not None:
                    ToolTip(self._sidebar_toggle, text="展开/收起侧边栏")
            except Exception:
                pass
            ttk.Separator(self._sidebar_container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2,6))
            # Notebook 页签
            nb = ttk.Notebook(self._sidebar_container)
            nb.pack(fill=tk.BOTH, expand=True)
            # Page 1: Meow（按钮直达页面）
            pg_meow = ttk.Frame(nb, padding=6)
            nb.add(pg_meow, text="Meow")
            ttk.Button(pg_meow, text="Meow 页面", command=lambda: self._switch_page('meow')).pack(fill=tk.X, pady=2)
            ttk.Separator(pg_meow, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
            ttk.Label(pg_meow, text="当前页面入口", foreground="#888").pack(anchor=tk.W)
            # Page 2: 圆神
            pg_ys = ttk.Frame(nb, padding=6)
            nb.add(pg_ys, text="圆神")
            ttk.Button(pg_ys, text="打开圆神", command=lambda: self._switch_page('yuanshen')).pack(fill=tk.X, pady=2)
            # Page 3: 待开发
            pg_tbd = ttk.Frame(nb, padding=6)
            nb.add(pg_tbd, text="待开发")
            ttk.Button(pg_tbd, text="打开待开发", command=lambda: self._switch_page('tbd')).pack(fill=tk.X, pady=2)
            # 跟随主窗体定位
            def _follow(_e=None):
                try:
                    rx = self.root.winfo_rootx()
                    ry = self.root.winfo_rooty()
                    rh = self.root.winfo_height()
                    w = self._sidebar_collapsed_w if self._sidebar_collapsed else self._sidebar_expanded_w
                    x = max(0, rx - w)
                    self._sidebar_win.geometry(f"{w}x{rh}+{x}+{ry}")
                    self._sidebar_win.lift()
                except Exception:
                    pass
            self.root.bind('<Configure>', _follow)
            self.root.after(0, _follow)
        except Exception:
            pass

    def _toggle_sidebar_stub(self):
        self._sidebar_collapsed = not getattr(self, '_sidebar_collapsed', True)
        try:
            # 重新定位以应用宽度变化
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rh = self.root.winfo_height()
            w = self._sidebar_collapsed_w if self._sidebar_collapsed else self._sidebar_expanded_w
            x = max(0, rx - w)
            self._sidebar_win.geometry(f"{w}x{rh}+{x}+{ry}")
            self._sidebar_win.lift()
        except Exception:
            pass

    def _switch_page(self, key: str):
        """切换页面：'meow' | 'yuanshen' | 'tbd'"""
        try:
            for f in (getattr(self, '_page_meow', None), getattr(self, '_page_ys', None), getattr(self, '_page_tbd', None)):
                if f:
                    f.grid_remove()
            if key == 'yuanshen' and getattr(self, '_page_ys', None):
                self._page_ys.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
            elif key == 'tbd' and getattr(self, '_page_tbd', None):
                self._page_tbd.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
            else:
                self._page_meow.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        except Exception:
            pass

    def pause_or_resume_auto(self, event=None):
        """切换自动弹琴暂停/继续（热键：Ctrl+Shift+C）。"""
        if not getattr(self, 'is_auto_playing', False):
            return
        self.is_auto_paused = not self.is_auto_paused
        if self.is_auto_paused:
            self.status_var.set("自动弹琴已暂停")
            self.log("自动弹琴已暂停", "INFO")
        else:
            self.status_var.set("自动弹琴继续…")
            self.log("自动弹琴继续", "INFO")

def main():
    """主函数"""
    try:
        app = Py312AutoPiano()
        app.run()
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        input("按回车键退出...")

if __name__ == "__main__":
    main() 