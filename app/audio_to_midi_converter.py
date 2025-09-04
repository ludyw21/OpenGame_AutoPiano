#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的音频转MIDI转换模块
支持MP3、WAV等音频格式转换为MIDI
"""

import os
import sys
import subprocess
import threading
import time
from typing import Optional, Callable
import logging

class AudioToMidiConverter:
    """音频转MIDI转换器"""
    
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.is_converting = False
        
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
    def find_pianotrans_python(self) -> Optional[str]:
        """查找PianoTrans的Python脚本"""
        possible_paths = [
            "PianoTrans-v1.0/PianoTrans.py",
            "PianoTrans-v1.0/PianoTrans.py",
            "PianoTrans.py"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.log(f"找到PianoTrans脚本: {path}", "SUCCESS")
                return os.path.abspath(path)
        
        self.log("未找到PianoTrans.py脚本", "ERROR")
        return None
    
    def find_model_file(self) -> Optional[str]:
        """查找模型文件"""
        model_name = "note_F1=0.9677_pedal_F1=0.9186.pth"
        
        # 搜索整个项目目录
        search_dirs = [
            "PianoTrans-v1.0",
            ".",
            ".."
        ]
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for root, dirs, files in os.walk(search_dir):
                if model_name in files:
                    model_path = os.path.abspath(os.path.join(root, model_name))
                    self.log(f"找到模型文件: {model_path}", "SUCCESS")
                    return model_path
        
        self.log(f"未找到模型文件: {model_name}", "ERROR")
        return None
    
    def fix_pianotrans_paths(self, pianotrans_script: str) -> bool:
        """修复PianoTrans脚本中的路径问题"""
        try:
            self.log("开始修复PianoTrans路径...", "INFO")
            
            # 读取原始脚本
            with open(pianotrans_script, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 查找模型文件路径
            model_path = self.find_model_file()
            if not model_path:
                return False
            
            # 修复路径问题
            original_path = "D:\\AutoPiano\\PianoTrans-v1.0\\PianoTrans-v1.0\\piano_transcription_inference_data\\note_F1=0.9677_pedal_F1=0.9186.pth"
            fixed_path = model_path.replace('\\', '/')  # 使用正斜杠
            
            if original_path in content:
                content = content.replace(original_path, fixed_path)
                self.log(f"修复路径: {original_path} -> {fixed_path}", "SUCCESS")
            
            # 修复其他可能的路径问题
            problematic_patterns = [
                "PianoTrans-v1.0\\PianoTrans-v1.0\\",
                "PianoTrans-v1.0/",
            ]
            
            for pattern in problematic_patterns:
                if pattern in content:
                    fixed_pattern = pattern.replace("PianoTrans-v1.0\\PianoTrans-v1.0\\", "PianoTrans-v1.0\\")
                    fixed_pattern = fixed_pattern.replace("PianoTrans-v1.0/", "PianoTrans-v1.0/")
                    content = content.replace(pattern, fixed_pattern)
                    self.log(f"修复重复路径: {pattern} -> {fixed_pattern}", "SUCCESS")
            
            # 保存修复后的脚本
            backup_script = pianotrans_script + ".backup"
            if not os.path.exists(backup_script):
                with open(backup_script, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"创建备份: {backup_script}", "INFO")
            
            with open(pianotrans_script, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log("PianoTrans路径修复完成", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"修复PianoTrans路径失败: {str(e)}", "ERROR")
            return False
    
    def convert_audio_to_midi(self, audio_path: str, output_path: str, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """转换音频到MIDI"""
        try:
            self.is_converting = True
            self.log(f"开始转换: {audio_path}", "INFO")
            
            # 查找PianoTrans脚本
            pianotrans_script = self.find_pianotrans_python()
            if not pianotrans_script:
                return False
            
            # 修复路径问题
            if not self.fix_pianotrans_paths(pianotrans_script):
                return False
            
            # 检查输入文件
            if not os.path.exists(audio_path):
                self.log(f"输入文件不存在: {audio_path}", "ERROR")
                return False
            
            # 创建输出目录
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 构建转换命令
            cmd = [
                sys.executable,  # 使用当前Python解释器
                pianotrans_script,
                audio_path,
                "-o",
                output_path
            ]
            
            self.log(f"执行命令: {' '.join(cmd)}", "INFO")
            
            # 设置工作目录
            working_dir = os.path.dirname(pianotrans_script)
            
            # 执行转换
            start_time = time.time()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(f"PianoTrans: {output.strip()}", "INFO")
                    if progress_callback:
                        progress_callback(output.strip())
            
            # 获取返回码
            return_code = process.poll()
            
            if return_code == 0 and os.path.exists(output_path):
                elapsed_time = time.time() - start_time
                self.log(f"转换成功完成！耗时: {elapsed_time:.1f}秒", "SUCCESS")
                return True
            else:
                # 读取错误信息
                stderr_output = process.stderr.read()
                if stderr_output:
                    self.log(f"转换错误: {stderr_output}", "ERROR")
                else:
                    self.log(f"转换失败，返回码: {return_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"转换过程中发生错误: {str(e)}", "ERROR")
            return False
        finally:
            self.is_converting = False
    
    def convert_audio_to_midi_async(self, audio_path: str, output_path: str,
                                  progress_callback: Optional[Callable] = None,
                                  complete_callback: Optional[Callable] = None):
        """异步转换音频到MIDI"""
        def convert_thread():
            success = self.convert_audio_to_midi(audio_path, output_path, progress_callback)
            if complete_callback:
                complete_callback(success, output_path if success else None)
        
        thread = threading.Thread(target=convert_thread, daemon=True)
        thread.start()
        return thread
    
    def stop_conversion(self):
        """停止转换"""
        self.is_converting = False
        self.log("转换已停止", "INFO")

# 测试函数
def test_converter():
    """测试转换器"""
    def log_callback(message, level):
        print(f"[{level}] {message}")
    
    converter = AudioToMidiConverter(log_callback)
    
    # 测试查找功能
    print("=== 测试查找功能 ===")
    script_path = converter.find_pianotrans_python()
    model_path = converter.find_model_file()
    
    print(f"脚本路径: {script_path}")
    print(f"模型路径: {model_path}")
    
    if script_path and model_path:
        print("=== 测试路径修复 ===")
        converter.fix_pianotrans_paths(script_path)

if __name__ == "__main__":
    test_converter() 