#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio conversion module for MeowField AutoPiano.

This module handles audio to MIDI conversion using various methods including
PianoTrans and custom converters.
"""

import os
import subprocess
import threading
from typing import List, Callable, Optional, Dict, Any
from ..core import Logger


class AudioConverter:
    """音频转换器，支持多种转换方法"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.supported_formats = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']
        
        # 初始化转换器
        self.new_converter = None
        self.pianotrans_config = None
        self._init_converters()
    
    def _init_converters(self):
        """初始化各种转换器"""
        # 尝试导入新的音频转换器
        try:
            from audio_to_midi_converter import AudioToMidiConverter
            self.new_converter = AudioToMidiConverter(self.logger.log)
            self.logger.log("新音频转换器已加载", "SUCCESS")
        except ImportError:
            self.logger.log("新音频转换器未加载", "WARNING")
        
        # 尝试导入PianoTrans配置器
        try:
            from pianotrans_config import PianoTransConfig
            self.pianotrans_config = PianoTransConfig(self.logger.log)
            self.logger.log("PianoTrans配置器已加载", "SUCCESS")
        except ImportError:
            self.logger.log("PianoTrans配置器未加载", "WARNING")
    
    def convert_audio_to_midi(self, audio_path: str, output_path: str = None) -> bool:
        """转换音频文件到MIDI"""
        if not os.path.exists(audio_path):
            self.logger.error(f"音频文件不存在: {audio_path}")
            return False
        
        if output_path is None:
            output_dir = os.path.dirname(audio_path)
            output_name = os.path.splitext(os.path.basename(audio_path))[0]
            output_path = os.path.join(output_dir, f"{output_name}.mid")
        
        # 选择转换策略
        if self._should_use_new_converter():
            return self._convert_with_new_converter(audio_path, output_path)
        elif self.pianotrans_config:
            return self._convert_with_pianotrans_config(audio_path, output_path)
        else:
            return self._convert_with_traditional_method(audio_path, output_path)
    
    def convert_audio_to_midi_async(self, audio_path: str, output_path: str, 
                                  progress_callback: Callable = None, 
                                  complete_callback: Callable = None):
        """异步转换音频文件到MIDI"""
        def convert_thread():
            try:
                success = self.convert_audio_to_midi(audio_path, output_path)
                if complete_callback:
                    complete_callback(success, output_path if success else None)
            except Exception as e:
                self.logger.error(f"异步转换失败: {str(e)}")
                if complete_callback:
                    complete_callback(False, None)
        
        thread = threading.Thread(target=convert_thread, daemon=True)
        thread.start()
    
    def batch_convert(self, folder_path: str, output_dir: str = None) -> Dict[str, Any]:
        """批量转换音频文件"""
        if not os.path.exists(folder_path):
            self.logger.error(f"文件夹不存在: {folder_path}")
            return {"success": False, "error": "文件夹不存在"}
        
        # 查找音频文件
        audio_files = []
        for file in os.listdir(folder_path):
            if any(file.lower().endswith(ext) for ext in self.supported_formats):
                audio_files.append(file)
        
        if not audio_files:
            self.logger.warning("所选文件夹中没有支持的音频文件")
            return {"success": False, "error": "没有支持的音频文件"}
        
        # 创建输出目录
        if output_dir is None:
            output_dir = os.path.join(folder_path, "converted_midi")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self.logger.log(f"开始批量转换 {len(audio_files)} 个音频文件...", "INFO")
        
        # 执行批量转换
        success_count = 0
        failed_files = []
        
        for i, audio_file in enumerate(audio_files):
            audio_path = os.path.join(folder_path, audio_file)
            output_name = os.path.splitext(audio_file)[0] + ".mid"
            midi_output = os.path.join(output_dir, output_name)
            
            self.logger.log(f"正在转换 {audio_file} ({i+1}/{len(audio_files)})", "INFO")
            
            try:
                success = self.convert_audio_to_midi(audio_path, midi_output)
                if success:
                    success_count += 1
                    self.logger.log(f"转换成功: {audio_file}", "SUCCESS")
                else:
                    failed_files.append(audio_file)
                    self.logger.log(f"转换失败: {audio_file}", "ERROR")
            except Exception as e:
                failed_files.append(audio_file)
                self.logger.log(f"转换错误 {audio_file}: {str(e)}", "ERROR")
        
        result = {
            "success": True,
            "total": len(audio_files),
            "success_count": success_count,
            "failed_count": len(failed_files),
            "failed_files": failed_files,
            "output_dir": output_dir
        }
        
        self.logger.log(f"批量转换完成: {success_count}/{len(audio_files)} 成功", "SUCCESS")
        return result
    
    def _should_use_new_converter(self) -> bool:
        """判断是否应该使用新转换器"""
        if not self.new_converter:
            return False
        
        try:
            script_path = self.new_converter.find_pianotrans_python()
            return script_path and os.path.exists(script_path)
        except Exception:
            return False
    
    def _convert_with_new_converter(self, audio_path: str, output_path: str) -> bool:
        """使用新的音频转换器"""
        try:
            self.logger.log("使用新的音频转换器...", "INFO")
            
            def progress_callback(message):
                self.logger.log(f"转换进度: {message}", "INFO")
            
            def complete_callback(success, output_path):
                if success:
                    self.logger.log(f"新转换器转换成功: {output_path}", "SUCCESS")
                else:
                    self.logger.log("新转换器转换失败", "ERROR")
            
            self.new_converter.convert_audio_to_midi_async(
                audio_path, 
                output_path, 
                progress_callback, 
                complete_callback
            )
            return True
        except Exception as e:
            self.logger.error(f"新转换器转换失败: {str(e)}")
            return False
    
    def _convert_with_pianotrans_config(self, audio_path: str, output_path: str) -> bool:
        """使用PianoTrans配置方法"""
        try:
            self.logger.log("使用PianoTrans配置方法...", "INFO")
            
            def progress_callback(message):
                self.logger.log(f"转换进度: {message}", "INFO")
            
            def complete_callback(success, output_path):
                if success:
                    self.logger.log(f"PianoTrans配置转换成功: {output_path}", "SUCCESS")
                else:
                    self.logger.log("PianoTrans配置转换失败", "ERROR")
            
            self.pianotrans_config.convert_audio_to_midi_async(
                audio_path, 
                output_path, 
                progress_callback, 
                complete_callback
            )
            return True
        except Exception as e:
            self.logger.error(f"PianoTrans配置转换失败: {str(e)}")
            return False
    
    def _convert_with_traditional_method(self, audio_path: str, output_path: str) -> bool:
        """使用传统PianoTrans方法"""
        try:
            self.logger.log("使用传统PianoTrans方法...", "INFO")
            
            # 查找PianoTrans.exe
            piano_trans_path = self._find_pianotrans_exe()
            if not piano_trans_path:
                self.logger.error("找不到PianoTrans.exe")
                return False
            
            # 执行转换
            cmd = [piano_trans_path, audio_path]
            working_dir = os.path.dirname(piano_trans_path)
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=False,
                cwd=working_dir, 
                timeout=600,
            )
            
            # 处理输出
            stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
            
            # 解析输出文件路径
            actual_output = self._parse_pianotrans_output(stdout, audio_path)
            
            # 重命名输出文件
            if actual_output and os.path.exists(actual_output) and actual_output != output_path:
                try:
                    os.replace(actual_output, output_path)
                except Exception as e:
                    self.logger.error(f"重命名输出文件失败: {str(e)}")
                    return False
            
            if os.path.exists(output_path):
                self.logger.log(f"传统方法转换成功: {output_path}", "SUCCESS")
                return True
            else:
                error_detail = stderr if stderr else stdout
                self.logger.error(f"传统方法转换失败: {error_detail}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("转换超时")
            return False
        except Exception as e:
            self.logger.error(f"传统方法转换失败: {str(e)}")
            return False
    
    def _find_pianotrans_exe(self) -> Optional[str]:
        """查找PianoTrans.exe文件"""
        possible_paths = [
            os.path.join("PianoTrans-v1.0", "PianoTrans.exe"),
            "PianoTrans-v1.0/PianoTrans.exe",
            "PianoTrans.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _parse_pianotrans_output(self, stdout: str, audio_path: str) -> Optional[str]:
        """解析PianoTrans输出，获取实际输出文件路径"""
        # 查找输出路径
        for line in stdout.splitlines():
            if 'Write out to ' in line:
                return line.split('Write out to ', 1)[-1].strip()
        
        # 默认输出路径
        guess_out = audio_path + ".mid"
        if os.path.exists(guess_out):
            return guess_out
        
        return None
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return self.supported_formats.copy()
    
    def is_format_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.supported_formats 