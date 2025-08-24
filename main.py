#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField AutoPiano v1.0.2
主程序入口点

这是一个高度模块化的自动钢琴应用程序，支持：
- MP3转MIDI转换
- MIDI文件播放
- LRCp乐谱自动演奏
- 播放列表管理
- 现代化UI界面
- 自适应布局
"""

import sys
import os
import traceback
from pathlib import Path


def setup_environment():
    """设置运行环境"""
    try:
        # 添加meowauto模块路径
        meowauto_path = Path(__file__).parent / "meowauto"
        if meowauto_path.exists():
            sys.path.insert(0, str(meowauto_path.parent))
        
        # 创建必要的目录
        directories = ['output', 'temp', 'logs']
        for dir_name in directories:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
        
        return True
        
    except Exception as e:
        print(f"环境设置失败: {e}")
        return False


def check_dependencies():
    """检查依赖包"""
    required_packages = [
        ('tkinter', 'tkinter'),
        ('PIL', 'pillow'),
        ('mido', 'mido'),
        ('pygame', 'pygame'),
        ('numpy', 'numpy')
    ]
    
    missing_packages = []
    
    for package_name, pip_name in required_packages:
        try:
            if package_name == 'tkinter':
                import tkinter
            else:
                __import__(package_name)
        except ImportError:
            missing_packages.append(pip_name)
    
    if missing_packages:
        print("缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请使用以下命令安装:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True


def main():
    """主函数"""
    print("🎹 MeowField AutoPiano v1.0.2")
    print("正在启动...")
    
    # 设置环境
    if not setup_environment():
        print("环境设置失败，程序退出")
        input("按回车键退出...")
        return
    
    # 检查依赖
    if not check_dependencies():
        print("依赖检查失败，程序退出")
        input("按回车键退出...")
        return
    
    try:
        # 导入主应用程序
        from app import MeowFieldAutoPiano
        
        # 创建并运行应用程序
        app = MeowFieldAutoPiano()
        print("应用程序启动成功")
        
        # 运行主循环
        app.run()
        
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保meowauto模块可用")
        input("按回车键退出...")
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        input("按回车键退出...")
    
    finally:
        print("程序已退出")


if __name__ == "__main__":
    main() 