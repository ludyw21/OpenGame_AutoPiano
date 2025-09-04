#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PianoTrans配置文件
用于覆盖PianoTrans的路径设置
"""

import os
import sys
import subprocess
import threading
import time
from typing import Optional, Callable

class PianoTransConfig:
    """PianoTrans配置管理器"""
    
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.is_converting = False
        
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
    def setup_environment(self):
        """设置环境变量"""
        try:
            # 设置正确的模型路径
            model_path = os.path.abspath("PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth")
            if os.path.exists(model_path):
                os.environ['PIANOTRANS_MODEL_PATH'] = model_path
                self.log(f"设置模型路径环境变量: {model_path}", "SUCCESS")
            else:
                self.log(f"模型文件不存在: {model_path}", "ERROR")
                return False
 
            # 将内置 ffmpeg 添加到 PATH，修复 audioread NoBackendError
            ffmpeg_dir = os.path.abspath(os.path.join("PianoTrans-v1.0", "ffmpeg"))
            if os.path.isdir(ffmpeg_dir):
                current_path = os.environ.get('PATH', '')
                if ffmpeg_dir not in current_path:
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                    self.log(f"已添加ffmpeg到PATH: {ffmpeg_dir}", "INFO")

            return True
        except Exception as e:
            self.log(f"设置环境变量失败: {str(e)}", "ERROR")
            return False
    
    def create_config_file(self):
        """创建配置文件"""
        try:
            config_content = """# PianoTrans配置文件
# 自动生成，用于修复路径问题

# 模型文件路径
MODEL_PATH = "PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth"

# 工作目录
WORKING_DIR = "."

# 输出目录
OUTPUT_DIR = "output"

# 日志级别
LOG_LEVEL = "INFO"
"""
            
            config_path = "PianoTrans-v1.0/pianotrans_config.py"
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            self.log(f"创建配置文件: {config_path}", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"创建配置文件失败: {str(e)}", "ERROR")
            return False
    
    def convert_audio_to_midi(self, audio_path: str, output_path: str, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """转换音频到MIDI"""
        try:
            self.is_converting = True
            self.log(f"开始转换: {audio_path}", "INFO")
            
            # 设置环境变量
            if not self.setup_environment():
                return False
            
            # 检查PianoTrans.exe
            pianotrans_exe = "PianoTrans-v1.0/PianoTrans.exe"
            if not os.path.exists(pianotrans_exe):
                self.log(f"PianoTrans.exe不存在: {pianotrans_exe}", "ERROR")
                return False
            
            # 检查输入文件
            if not os.path.exists(audio_path):
                self.log(f"输入文件不存在: {audio_path}", "ERROR")
                return False
            
            # 创建输出目录
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 构建转换命令（不使用 -o，由程序自行输出 input.ext.mid）
            cmd = [pianotrans_exe, audio_path]
 
            self.log(f"执行命令: {' '.join(cmd)}", "INFO")
 
            # 设置工作目录
            working_dir = "PianoTrans-v1.0"
 
            # 执行转换
            start_time = time.time()
 
            env = os.environ.copy()
            # 确保 ffmpeg 目录在 PATH 中
            ffmpeg_dir = os.path.abspath(os.path.join("PianoTrans-v1.0", "ffmpeg"))
            if os.path.isdir(ffmpeg_dir) and ffmpeg_dir not in env.get('PATH', ''):
                env['PATH'] = ffmpeg_dir + os.pathsep + env.get('PATH', '')

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                text=True,
                encoding='utf-8',
                errors='ignore',
                env=env  # 使用增强后的环境变量
            )
 
            # 实时读取输出
            captured_stdout = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    captured_stdout.append(line)
                    self.log(f"PianoTrans: {line}", "INFO")
                    if progress_callback:
                        progress_callback(line)
 
            # 获取返回码
            return_code = process.poll()
 
            # 解析实际输出文件并重命名
            actual_output = None
            for line in captured_stdout:
                if 'Write out to ' in line:
                    actual_output = line.split('Write out to ', 1)[-1].strip()
                    break
            if not actual_output:
                # 常见默认命名：原音频追加 .mid
                guess_out = audio_path + ".mid"
                if os.path.exists(guess_out):
                    actual_output = guess_out

            if actual_output and os.path.exists(actual_output):
                try:
                    if os.path.abspath(actual_output) != os.path.abspath(output_path):
                        os.replace(actual_output, output_path)
                        self.log(f"已重命名输出到: {output_path}", "INFO")
                except Exception as re:
                    self.log(f"重命名输出失败: {re}", "WARNING")

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
                    # 附带标准输出，便于排查
                    self.log(f"转换失败，返回码: {return_code}\n{os.linesep.join(captured_stdout)}", "ERROR")
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
def test_config():
    """测试配置"""
    def log_callback(message, level):
        print(f"[{level}] {message}")
    
    config = PianoTransConfig(log_callback)
    
    # 测试环境变量设置
    print("=== 测试环境变量设置 ===")
    config.setup_environment()
    
    # 测试配置文件创建
    print("=== 测试配置文件创建 ===")
    config.create_config_file()

if __name__ == "__main__":
    test_config() 