#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowField AutoPiano 启动脚本
用于测试和启动主程序
"""

import sys
import os
import traceback
import ctypes
from pathlib import Path


def is_admin():
    """检查当前是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新启动当前脚本"""
    if is_admin():
        return True
    else:
        # 获取当前脚本的完整路径
        script_path = os.path.abspath(__file__)
        
        # 使用ShellExecute以管理员权限运行
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                f'"{script_path}"', 
                None, 
                1
            )
            return True
        except Exception as e:
            print(f"申请管理员权限失败: {e}")
            return False

def main():
    """主函数"""
    print("🎹 MeowField AutoPiano v1.0.6 启动脚本")
    print("=" * 50)
    
    # 检查管理员权限
    if not is_admin():
        print("⚠️  需要管理员权限来访问MIDI设备和系统资源")
        print("正在申请管理员权限...")
        
        if run_as_admin():
            print("✅ 管理员权限申请成功，程序将重新启动")
            return
        else:
            print("❌ 管理员权限申请失败")
            print("请右键点击程序图标，选择'以管理员身份运行'")
            input("按回车键退出...")
            return
    else:
        print("✅ 检测到管理员权限")
    
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
        
        # 初始化电子琴处理试听功能
        try:
            from pages.components.playback_controls import initialize_epiano_preview
            result = initialize_epiano_preview(app)
            if result and result.get('success'):
                print("✓ 电子琴处理试听功能已初始化")
            else:
                print(f"⚠ 电子琴处理试听功能初始化失败: {result.get('message', '未知错误')}")
        except Exception as e:
            print(f"⚠ 电子琴处理试听功能初始化失败: {e}")
            
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