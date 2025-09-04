#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging system for MeowField AutoPiano.

This module provides a centralized logging system with support for
both console and GUI logging.
"""

import os
from datetime import datetime
from typing import Optional, Callable


class Logger:
    """日志系统"""
    
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.log_text = None
        self.root = None
    
    def set_gui_components(self, log_text, root):
        """设置GUI组件"""
        self.log_text = log_text
        self.root = root
    
    def log(self, message: str, level: str = "INFO"):
        """添加日志信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "SUCCESS": "✅"}
        emoji = level_emoji.get(level, "ℹ️")
        
        log_message = f"[{timestamp}] {emoji} {message}\n"
        
        # 优先使用回调函数
        if self.log_callback:
            try:
                self.log_callback(message, level)
                return
            except Exception:
                pass
        
        # GUI日志
        if self.log_text is not None:
            try:
                self.log_text.insert("end", log_message)
                self.log_text.see("end")
                
                # 限制日志行数
                lines = self.log_text.get("1.0", "end").split('\n')
                if len(lines) > 1000:
                    self.log_text.delete("1.0", f"{len(lines)-1000}.0")
                
                if self.root:
                    self.root.update_idletasks()
                return
            except Exception:
                pass
        
        # 控制台回退
        try:
            print(log_message.strip())
        except Exception:
            pass
    
    def clear_log(self):
        """清空日志"""
        if self.log_text is not None:
            try:
                self.log_text.delete("1.0", "end")
                self.log("日志已清空", "INFO")
            except Exception:
                pass
    
    def save_log(self, filename: str = None) -> bool:
        """保存日志到文件"""
        if self.log_text is None:
            return False
        
        try:
            if filename is None:
                filename = f"logs/log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            # 确保日志目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", "end"))
            
            self.log(f"日志已保存到: {filename}", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"保存日志失败: {str(e)}", "ERROR")
            return False
    
    def info(self, message: str):
        """信息日志"""
        self.log(message, "INFO")
    
    def warning(self, message: str):
        """警告日志"""
        self.log(message, "WARNING")
    
    def error(self, message: str):
        """错误日志"""
        self.log(message, "ERROR")
    
    def success(self, message: str):
        """成功日志"""
        self.log(message, "SUCCESS") 