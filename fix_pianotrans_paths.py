#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PianoTrans路径修复工具
专门用于修复PianoTrans中的路径问题
"""

import os
import re
import shutil
from typing import List, Tuple

class PianoTransPathFixer:
    """PianoTrans路径修复器"""
    
    def __init__(self):
        self.fixed_files = []
        self.backup_dir = "pianotrans_backups"
    
    def find_pianotrans_files(self) -> List[str]:
        """查找所有PianoTrans相关文件"""
        files = []
        search_dirs = ["PianoTrans-v1.0", "."]
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            
            for root, dirs, filenames in os.walk(search_dir):
                for filename in filenames:
                    if filename.endswith(('.py', '.pyw', '.txt', '.cfg', '.ini', '.bat')):
                        file_path = os.path.join(root, filename)
                        files.append(file_path)
        
        return files
    
    def find_model_file(self) -> str:
        """查找模型文件的实际路径"""
        model_name = "note_F1=0.9677_pedal_F1=0.9186.pth"
        
        # 检查正确的位置
        correct_path = os.path.join("PianoTrans-v1.0", "piano_transcription_inference_data", model_name)
        if os.path.exists(correct_path):
            return os.path.abspath(correct_path)
        
        # 搜索整个项目目录
        for root, dirs, files in os.walk("."):
            if model_name in files:
                return os.path.abspath(os.path.join(root, model_name))
        
        return ""
    
    def create_backup(self, file_path: str) -> str:
        """创建文件备份"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        backup_path = os.path.join(self.backup_dir, os.path.basename(file_path) + ".backup")
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def fix_paths_in_file(self, file_path: str, model_path: str) -> bool:
        """修复文件中的路径问题"""
        try:
            print(f"正在修复: {file_path}")
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            original_content = content
            fixed = False
            
            # 修复硬编码的路径
            problematic_paths = [
                # 原始错误路径
                "D:\\AutoPiano\\PianoTrans-v1.0\\PianoTrans-v1.0\\piano_transcription_inference_data\\note_F1=0.9677_pedal_F1=0.9186.pth",
                "PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth",
                
                # 其他可能的错误路径
                "PianoTrans-v1.0\\PianoTrans-v1.0\\piano_transcription_inference_data\\note_F1=0.9677_pedal_F1=0.9186.pth",
                "PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth",
                
                # 相对路径问题
                "piano_transcription_inference_data\\note_F1=0.9677_pedal_F1=0.9186.pth",
                "PianoTrans-v1.0/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth",
            ]
            
            # 使用模型文件的实际路径
            if model_path:
                for problematic_path in problematic_paths:
                    if problematic_path in content:
                        # 转换为相对路径
                        relative_model_path = os.path.relpath(model_path, os.path.dirname(file_path))
                        # 统一使用正斜杠
                        relative_model_path = relative_model_path.replace('\\', '/')
                        
                        content = content.replace(problematic_path, relative_model_path)
                        print(f"  修复路径: {problematic_path} -> {relative_model_path}")
                        fixed = True
            
            # 修复重复的目录名
            patterns_to_fix = [
                (r'PianoTrans-v1\.0[\\/]PianoTrans-v1\.0[\\/]', 'PianoTrans-v1.0/'),
                (r'PianoTrans-v1\.0[\\/]PianoTrans-v1\.0', 'PianoTrans-v1.0'),
            ]
            
            for pattern, replacement in patterns_to_fix:
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    print(f"  修复重复目录: {pattern} -> {replacement}")
                    fixed = True
            
            # 修复工作目录设置
            if 'os.chdir' in content or 'cwd=' in content:
                # 查找并修复工作目录设置
                content = re.sub(
                    r'os\.chdir\([\'"][^\'"]*PianoTrans-v1\.0[\\/]PianoTrans-v1\.0[^\'"]*[\'"]\)',
                    'os.chdir(os.path.dirname(__file__))',
                    content
                )
                content = re.sub(
                    r'cwd=[\'"][^\'"]*PianoTrans-v1\.0[\\/]PianoTrans-v1\.0[^\'"]*[\'"]',
                    'cwd=os.path.dirname(__file__)',
                    content
                )
            
            # 如果内容有变化，保存文件
            if content != original_content:
                # 创建备份
                backup_path = self.create_backup(file_path)
                print(f"  创建备份: {backup_path}")
                
                # 保存修复后的文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.fixed_files.append(file_path)
                return True
            
            return False
            
        except Exception as e:
            print(f"  修复失败: {str(e)}")
            return False
    
    def fix_all_paths(self) -> Tuple[int, int]:
        """修复所有文件中的路径问题"""
        print("开始修复PianoTrans路径问题...")
        
        # 查找模型文件
        model_path = self.find_model_file()
        if model_path:
            print(f"找到模型文件: {model_path}")
        else:
            print("警告: 未找到模型文件")
        
        # 查找所有相关文件
        files = self.find_pianotrans_files()
        print(f"找到 {len(files)} 个相关文件")
        
        fixed_count = 0
        total_count = len(files)
        
        for file_path in files:
            if self.fix_paths_in_file(file_path, model_path):
                fixed_count += 1
        
        return fixed_count, total_count
    
    def restore_backups(self):
        """恢复备份文件"""
        if not os.path.exists(self.backup_dir):
            print("没有找到备份目录")
            return
        
        print("恢复备份文件...")
        for backup_file in os.listdir(self.backup_dir):
            if backup_file.endswith('.backup'):
                backup_path = os.path.join(self.backup_dir, backup_file)
                original_name = backup_file[:-7]  # 移除.backup后缀
                
                # 查找原始文件位置
                for root, dirs, files in os.walk("."):
                    if original_name in files:
                        original_path = os.path.join(root, original_name)
                        shutil.copy2(backup_path, original_path)
                        print(f"恢复: {original_path}")
                        break
    
    def show_summary(self):
        """显示修复摘要"""
        print("\n=== 修复摘要 ===")
        print(f"修复的文件数量: {len(self.fixed_files)}")
        for file_path in self.fixed_files:
            print(f"  - {file_path}")
        
        if self.fixed_files:
            print(f"\n备份文件保存在: {self.backup_dir}")
            print("如需恢复，请运行: python fix_pianotrans_paths.py --restore")

def main():
    """主函数"""
    import sys
    
    fixer = PianoTransPathFixer()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--restore":
        fixer.restore_backups()
        return
    
    fixed_count, total_count = fixer.fix_all_paths()
    
    print(f"\n修复完成: {fixed_count}/{total_count} 个文件")
    fixer.show_summary()

if __name__ == "__main__":
    main() 