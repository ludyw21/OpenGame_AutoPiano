#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试恢复后的电子琴页面
"""
import tkinter as tk
from tkinter import ttk
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

try:
    from pages.components.playback_controls import create_playback_controls
    print("✅ playback_controls 导入成功")
except Exception as e:
    print(f"❌ playback_controls 导入失败: {e}")
    sys.exit(1)

class MockController:
    def __init__(self):
        self.root = None
        self.midi_path_var = tk.StringVar()
        self.file_info_var = tk.StringVar(value="未选择文件")
        self.enable_auto_countdown_var = tk.BooleanVar(value=True)
        self.auto_countdown_seconds_var = tk.IntVar(value=3)
        self.playlist_mode_var = tk.StringVar(value="顺序")
        self.ensemble_mode_var = tk.StringVar(value="solo")
        self.tempo_var = tk.DoubleVar(value=1.0)
        
    def _log_message(self, message, level="INFO"):
        print(f"[{level}] {message}")
        
    def _start_auto_play(self):
        print("开始演奏")
        
    def _stop_auto_play(self):
        print("停止演奏")
        
    def _pause_or_resume(self):
        print("暂停/恢复")
        
    def _add_to_playlist(self):
        print("添加文件到演奏列表")
        
    def _import_folder_to_playlist(self):
        print("导入文件夹到演奏列表")
        
    def _remove_from_playlist(self):
        print("从演奏列表移除")
        
    def _clear_playlist(self):
        print("清空演奏列表")
        
    def _play_midi(self):
        print("播放MIDI音频")
        
    def _stop_playback(self):
        print("停止音频播放")
        
    def _create_file_selection_component(self, parent_left=None):
        """创建文件选择组件"""
        print("创建文件选择组件")
        # 创建简单的文件选择界面
        frame = ttk.Frame(parent_left)
        frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame, text="MIDI文件:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(frame, textvariable=self.midi_path_var, width=40).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(frame, text="浏览", command=lambda: print("浏览文件")).pack(side=tk.LEFT)
        
        return frame

def test_epiano_restored():
    """测试恢复后的电子琴页面"""
    root = tk.Tk()
    root.title("测试恢复后的电子琴页面")
    root.geometry("800x600")
    
    # 创建主框架
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 创建控制器
    controller = MockController()
    controller.root = root
    
    try:
        print("开始创建播放控制组件...")
        create_playback_controls(controller, main_frame, include_ensemble=True, instrument='电子琴')
        print("✅ 播放控制组件创建成功")
        
        # 显示窗口
        root.mainloop()
        
    except Exception as e:
        print(f"❌ 播放控制组件创建失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_epiano_restored()
