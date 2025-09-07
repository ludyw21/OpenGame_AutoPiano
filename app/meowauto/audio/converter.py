#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio conversion module for MeowField AutoPiano.

This module provides a thin wrapper over the unified entry in
`meowauto.audio.audio2midi.convert_audio_to_midi`.
"""
"""
署名与声明：
by薮薮猫猫
本软件开源且免费，如果你是付费购买请申请退款，并从官方渠道获取。
"""

import os
import threading
from typing import List, Callable, Optional, Dict, Any
from ..core import Logger


class AudioConverter:
    """音频转换器（统一入口封装）"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.supported_formats = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']
    
    def convert_audio_to_midi(self, audio_path: str, output_path: str = None) -> bool:
        """转换音频文件到MIDI"""
        if not os.path.exists(audio_path):
            self.logger.error(f"音频文件不存在: {audio_path}")
            return False
        
        if output_path is None:
            output_dir = os.path.dirname(audio_path)
            output_name = os.path.splitext(os.path.basename(audio_path))[0]
            output_path = os.path.join(output_dir, f"{output_name}.mid")
        
        # 统一通过 meowauto.audio.audio2midi 执行
        try:
            from .audio2midi import convert_audio_to_midi
        except Exception as e:
            self.logger.error(f"加载统一转换入口失败: {e}")
            return False

        ok, outp, err, logs = convert_audio_to_midi(audio_path, output_path)
        if logs.get('stdout'):
            self.logger.log(f"PianoTrans输出: {logs['stdout']}", "INFO")
        if logs.get('stderr'):
            # 可能包含校验警告，不一定是失败
            self.logger.log(f"PianoTrans错误/警告: {logs['stderr']}", "WARNING")
        if logs.get('elapsed'):
            self.logger.log(f"转换耗时: {logs['elapsed']:.1f}s", "INFO")
        if ok and outp and os.path.exists(outp):
            self.logger.log(f"转换成功: {outp}", "SUCCESS")
            return True
        else:
            self.logger.error(f"转换失败: {err or '未知错误'}")
            return False
    
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
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return self.supported_formats.copy()

    def is_format_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.supported_formats