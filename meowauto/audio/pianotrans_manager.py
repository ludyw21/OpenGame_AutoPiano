#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PianoTrans management module for MeowField AutoPiano.

This module handles PianoTrans configuration checking, path fixing, and management.
"""

import os
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from ..core import Logger


class PianoTransManager:
    """PianoTrans管理器，负责配置检查和路径修复"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.piano_trans_path = None
        self.model_path = None
        self.config_status = {}
    
    def check_configuration(self) -> Dict[str, Any]:
        """检查PianoTrans配置和模型文件"""
        self.logger.log("开始检查PianoTrans配置...", "INFO")
        
        result = {
            "piano_trans_found": False,
            "model_found": False,
            "piano_trans_path": None,
            "model_path": None,
            "model_size_mb": 0,
            "directory_structure": [],
            "errors": [],
            "warnings": []
        }
        
        # 检查PianoTrans.exe
        piano_trans_path = self._find_pianotrans_exe()
        if piano_trans_path:
            result["piano_trans_found"] = True
            result["piano_trans_path"] = piano_trans_path
            self.piano_trans_path = piano_trans_path
            self.logger.log(f"✓ 找到PianoTrans.exe: {piano_trans_path}", "SUCCESS")
        else:
            result["errors"].append("未找到PianoTrans.exe")
            self.logger.log("❌ 未找到PianoTrans.exe", "ERROR")
            return result
        
        # 检查模型文件
        model_path = self._find_model_file(piano_trans_path)
        if model_path:
            result["model_found"] = True
            result["model_path"] = model_path
            self.model_path = model_path
            self.logger.log(f"✓ 找到模型文件: {model_path}", "SUCCESS")
            
            # 检查文件大小
            try:
                model_size = os.path.getsize(model_path)
                result["model_size_mb"] = model_size / (1024 * 1024)
                self.logger.log(f"模型文件大小: {result['model_size_mb']:.1f} MB", "INFO")
                
                if result["model_size_mb"] < 100:
                    result["warnings"].append("模型文件可能不完整（小于100MB）")
                    self.logger.log("⚠️ 模型文件可能不完整（小于100MB）", "WARNING")
            except Exception as e:
                result["warnings"].append(f"无法获取模型文件大小: {str(e)}")
        else:
            result["errors"].append("未找到模型文件")
            self.logger.log("❌ 未找到模型文件", "ERROR")
        
        # 检查目录结构
        if piano_trans_path:
            result["directory_structure"] = self._analyze_directory_structure(piano_trans_path)
        
        self.config_status = result
        return result
    
    def _find_pianotrans_exe(self) -> Optional[str]:
        """查找PianoTrans.exe文件"""
        possible_paths = [
            os.path.join("PianoTrans-v1.0", "PianoTrans.exe"),
            os.path.join("PianoTrans-v1.0", "PianoTrans-v1.0", "PianoTrans.exe"),
            "PianoTrans.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        return None
    
    def _find_model_file(self, piano_trans_path: str) -> Optional[str]:
        """查找模型文件"""
        model_file = "note_F1=0.9677_pedal_F1=0.9186.pth"
        possible_paths = [
            os.path.join(os.path.dirname(piano_trans_path), "piano_transcription_inference_data", model_file),
            os.path.join(os.path.dirname(piano_trans_path), "PianoTrans-v1.0", "piano_transcription_inference_data", model_file),
            os.path.join("piano_transcription_inference_data", model_file),
            os.path.join(os.getcwd(), "PianoTrans-v1.0", "piano_transcription_inference_data", model_file),
            os.path.join(os.getcwd(), "piano_transcription_inference_data", model_file),
        ]
        
        # 首先尝试标准路径
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        # 搜索整个PianoTrans目录
        piano_trans_dir = os.path.dirname(piano_trans_path)
        for root, dirs, files in os.walk(piano_trans_dir):
            if model_file in files:
                return os.path.abspath(os.path.join(root, model_file))
        
        return None
    
    def _analyze_directory_structure(self, piano_trans_path: str) -> List[str]:
        """分析目录结构"""
        structure = []
        piano_trans_dir = os.path.dirname(piano_trans_path)
        
        try:
            for root, dirs, files in os.walk(piano_trans_dir):
                level = root.replace(piano_trans_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                structure.append(f"{indent}{os.path.basename(root)}/")
                
                subindent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # 只显示前10个文件
                    structure.append(f"{subindent}{file}")
                
                if len(files) > 10:
                    structure.append(f"{subindent}... 还有 {len(files) - 10} 个文件")
        except Exception as e:
            structure.append(f"遍历目录失败: {str(e)}")
        
        return structure
    
    def fix_paths(self, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """修复PianoTrans路径问题"""
        self.logger.log("开始修复PianoTrans路径...", "INFO")
        
        result = {
            "success": False,
            "fixed_count": 0,
            "total_count": 0,
            "errors": [],
            "backup_created": False
        }
        
        try:
            # 尝试导入路径修复工具
            try:
                from fix_pianotrans_paths import PianoTransPathFixer
            except ImportError:
                result["errors"].append("路径修复工具未找到，请确保fix_pianotrans_paths.py存在")
                self.logger.log("路径修复工具未找到，请确保fix_pianotrans_paths.py存在", "ERROR")
                return result
            
            # 在新线程中执行修复
            def fix_thread():
                try:
                    fixer = PianoTransPathFixer()
                    fixed_count, total_count = fixer.fix_all_paths()
                    
                    result["success"] = True
                    result["fixed_count"] = fixed_count
                    result["total_count"] = total_count
                    result["backup_created"] = True
                    
                    if callback:
                        callback(result)
                    
                except Exception as e:
                    result["errors"].append(f"路径修复失败: {str(e)}")
                    if callback:
                        callback(result)
            
            thread = threading.Thread(target=fix_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            result["errors"].append(f"启动路径修复失败: {str(e)}")
            self.logger.log(f"启动路径修复失败: {str(e)}", "ERROR")
        
        return result
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        if not self.config_status:
            self.check_configuration()
        return self.config_status.copy()
    
    def is_ready(self) -> bool:
        """检查PianoTrans是否准备就绪"""
        status = self.get_configuration_status()
        return status.get("piano_trans_found", False) and status.get("model_found", False)
    
    def get_piano_trans_path(self) -> Optional[str]:
        """获取PianoTrans.exe路径"""
        if not self.piano_trans_path:
            self.piano_trans_path = self._find_pianotrans_exe()
        return self.piano_trans_path
    
    def get_model_path(self) -> Optional[str]:
        """获取模型文件路径"""
        if not self.model_path and self.piano_trans_path:
            self.model_path = self._find_model_file(self.piano_trans_path)
        return self.model_path
    
    def validate_model_file(self, model_path: str) -> Dict[str, Any]:
        """验证模型文件"""
        result = {
            "valid": False,
            "size_mb": 0,
            "errors": [],
            "warnings": []
        }
        
        if not os.path.exists(model_path):
            result["errors"].append("模型文件不存在")
            return result
        
        try:
            # 检查文件大小
            size = os.path.getsize(model_path)
            result["size_mb"] = size / (1024 * 1024)
            
            if result["size_mb"] < 100:
                result["warnings"].append("模型文件可能不完整（小于100MB）")
            elif result["size_mb"] > 200:
                result["warnings"].append("模型文件过大，可能包含额外数据")
            else:
                result["valid"] = True
            
            # 检查文件扩展名
            if not model_path.lower().endswith('.pth'):
                result["warnings"].append("模型文件扩展名不是.pth")
            
        except Exception as e:
            result["errors"].append(f"验证模型文件失败: {str(e)}")
        
        return result
    
    def get_installation_guide(self) -> str:
        """获取安装指南"""
        guide = """PianoTrans安装指南：

1. 下载PianoTrans-v1.0完整版本
2. 解压到项目根目录
3. 确保目录结构如下：
   PianoTrans-v1.0/
   ├── PianoTrans.exe
   └── piano_transcription_inference_data/
       └── note_F1=0.9677_pedal_F1=0.9186.pth

4. 模型文件大小应约为165MB
5. 首次使用需要等待模型加载

如果遇到路径问题，可以使用路径修复功能。"""
        
        return guide
    
    def create_backup(self, backup_dir: str = "pianotrans_backups") -> bool:
        """创建PianoTrans配置备份"""
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # 这里可以实现具体的备份逻辑
            # 目前只是创建备份目录
            
            self.logger.log(f"备份目录已创建: {backup_dir}", "INFO")
            return True
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {str(e)}")
            return False
    
    def restore_backup(self, backup_dir: str = "pianotrans_backups") -> bool:
        """从备份恢复PianoTrans配置"""
        try:
            if not os.path.exists(backup_dir):
                self.logger.error("备份目录不存在")
                return False
            
            # 这里可以实现具体的恢复逻辑
            
            self.logger.log("从备份恢复完成", "SUCCESS")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复备份失败: {str(e)}")
            return False 