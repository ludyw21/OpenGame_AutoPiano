#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField AutoPiano 启动脚本
用于测试和启动主程序
"""

import sys
import os
import traceback
from pathlib import Path


def main():
    """主函数"""
    print("🎹 MeowField AutoPiano v1.0.6 启动脚本")
    print("=" * 50)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        print(f"当前版本: {sys.version}")
        input("按回车键退出...")
        return
    
    print(f"✓ Python版本: {sys.version.split()[0]}")
    
    # 设置环境
    print("\n🔧 设置运行环境...")
    try:
        # 添加meowauto模块路径
        meowauto_path = Path(__file__).parent / "meowauto"
        if meowauto_path.exists():
            sys.path.insert(0, str(meowauto_path.parent))
            print(f"✓ 已添加模块路径: {meowauto_path}")
        else:
            print("⚠ 警告: meowauto目录不存在")
        
        # 创建必要的目录
        directories = ['output', 'temp', 'logs']
        for dir_name in directories:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✓ 已创建目录: {dir_name}")
            else:
                print(f"✓ 目录已存在: {dir_name}")
        
    except Exception as e:
        print(f"❌ 环境设置失败: {e}")
        input("按回车键退出...")
        return
    
    # 检查依赖
    print("\n📦 检查依赖包...")
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
                print(f"✓ {package_name}")
            else:
                __import__(package_name)
                print(f"✓ {package_name}")
        except ImportError:
            missing_packages.append(pip_name)
            print(f"❌ {package_name}")
    
    if missing_packages:
        print(f"\n❌ 缺少以下依赖包: {', '.join(missing_packages)}")
        print("请使用以下命令安装:")
        print(f"pip install {' '.join(missing_packages)}")
        input("按回车键退出...")
        return
    
    print("✓ 所有依赖包检查通过")
    
    # 检查meowauto模块
    print("\n🔍 检查meowauto模块...")
    try:
        import meowauto
        print("✓ meowauto模块导入成功")
        
        # 检查子模块
        submodules = ['core', 'playback', 'music', 'audio', 'ui', 'utils']
        for submodule in submodules:
            try:
                __import__(f'meowauto.{submodule}')
                print(f"✓ {submodule} 子模块可用")
            except ImportError as e:
                print(f"⚠ {submodule} 子模块不可用: {e}")
        
    except ImportError as e:
        print(f"❌ meowauto模块导入失败: {e}")
        print("请确保meowauto目录结构正确")
        input("按回车键退出...")
        return
    
    # 启动主程序
    print("\n🚀 启动主程序...")
    try:
        # 导入主应用程序
        from app import MeowFieldAutoPiano
        
        print("✓ 主应用程序类导入成功")
        
        # 创建并运行应用程序
        print("正在创建应用程序实例...")
        app = MeowFieldAutoPiano()
        
        print("✓ 应用程序实例创建成功")
        print("正在启动主循环...")
        
        # 运行主循环
        app.run()
        
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保所有必要的文件都存在")
        traceback.print_exc()
        input("按回车键退出...")
        
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        input("按回车键退出...")
    
    finally:
        print("\n👋 程序已退出")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 启动脚本发生未知错误: {e}")
        traceback.print_exc()
        input("按回车键退出...") 