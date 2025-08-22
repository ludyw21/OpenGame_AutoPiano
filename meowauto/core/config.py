#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for MeowField AutoPiano.

This module handles loading, saving, and managing application configuration.
"""

import os
import json
from typing import Dict, Any
import time


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.key_mapping = {}
        self.note_mapping = {}
        self.load_key_mappings()
        self.create_directories()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
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
                default_config = self._get_default_config()
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
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
    
    def save_config(self, config: Dict[str, Any] = None):
        """保存配置文件"""
        if config is None:
            config = self.config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
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
        self._build_note_mapping()
    
    def _build_note_mapping(self):
        """构建音符映射"""
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
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def export_config(self, filename: str = None) -> bool:
        """导出配置"""
        try:
            if filename is None:
                filename = f"config_export_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"导出配置失败: {e}")
            return False 