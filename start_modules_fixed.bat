@echo off
chcp 65001 >nul
title MeowField AutoPiano v1.0.6 - 模块修复版

echo.
echo ========================================
echo    MeowField AutoPiano v1.0.6
echo    模块修复版启动脚本
echo ========================================
echo.
echo 本软件免费使用，如果你是从其他地方购入说明你已经受骗。请联系b站up主薮薮猫猫举报。

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 选择Python命令（优先 py -3，回退 python）
set "PY_CMD="
where py >nul 2>&1 && (set "PY_CMD=py -3")
if not defined PY_CMD (
    where python >nul 2>&1 && (set "PY_CMD=python")
)

:: 检查Python环境
echo 正在检查Python环境...
%PY_CMD% --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python未安装或未添加到PATH
    echo 请先安装Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python环境检查通过: %PYTHON_VERSION%

:: 检查Python版本
%PY_CMD% -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python版本过低，需要3.8+
    pause
    exit /b 1
)

:: 检查meowauto目录结构
echo.
echo 正在检查meowauto目录结构...
if not exist "meowauto" (
    echo ❌ meowauto目录不存在
    pause
    exit /b 1
)

if not exist "meowauto\__init__.py" (
    echo ❌ meowauto\__init__.py不存在
    pause
    exit /b 1
)

if not exist "meowauto\playback" (
    echo ❌ meowauto\playback目录不存在
    pause
    exit /b 1
)

if not exist "meowauto\core" (
    echo ❌ meowauto\core目录不存在
    pause
    exit /b 1
)

echo ✓ meowauto目录结构检查通过

:: 依赖安装：优先 requirements.txt；否则逐项检查
echo.
echo 正在检查/安装依赖包...
if exist requirements.txt (
    echo 检测到 requirements.txt，执行一键安装...
    %PY_CMD% -m pip install -r requirements.txt
    if %errorLevel% neq 0 (
        echo ❌ 依赖安装失败，请检查网络或权限
        pause
        exit /b 1
    )
) else (
    rem tkinter 为内置
    %PY_CMD% -c "import tkinter; print('tkinter OK')" >nul 2>&1 || (
        echo ❌ tkinter 不可用，请安装带有 tkinter 的 Python 版本
        pause & exit /b 1
    )
    rem ttkbootstrap（可选）
    %PY_CMD% -c "import ttkbootstrap" >nul 2>&1 || %PY_CMD% -m pip install ttkbootstrap>=1.10.1
    rem mido（必须）
    %PY_CMD% -c "import mido" >nul 2>&1 || %PY_CMD% -m pip install mido>=1.3.0
    if %errorLevel% neq 0 ( echo ❌ mido 安装失败 & pause & exit /b 1 )
    rem pygame（必须）
    %PY_CMD% -c "import pygame" >nul 2>&1 || %PY_CMD% -m pip install pygame>=2.5.2
    if %errorLevel% neq 0 ( echo ❌ pygame 安装失败 & pause & exit /b 1 )
    rem keyboard（必须）
    %PY_CMD% -c "import keyboard" >nul 2>&1 || %PY_CMD% -m pip install keyboard>=0.13.5
    if %errorLevel% neq 0 ( echo ❌ keyboard 安装失败 & pause & exit /b 1 )
)
echo ✓ 依赖检查完成

:: 创建必要目录
echo.
echo 正在创建必要目录...
if not exist "output" mkdir output
if not exist "temp" mkdir temp
if not exist "logs" mkdir logs
echo ✓ 目录结构检查完成

:: 测试模块加载
echo.
echo 正在测试模块加载...
%PY_CMD% test_module_loading.py
if %errorLevel% neq 0 (
    echo.
    echo ⚠ 模块加载测试失败，但继续尝试启动程序
    echo.
)

:: 启动程序
echo.
echo 🚀 正在启动 MeowField AutoPiano...
echo.

:: 使用修复后的启动方式
%PY_CMD% -c "
import sys
import os
import traceback

try:
    # 设置工作目录
    os.chdir(r'%CD%')
    print(f'工作目录: {os.getcwd()}')
    
    # 添加meowauto路径
    meowauto_path = os.path.join(os.getcwd(), 'meowauto')
    if os.path.exists(meowauto_path):
        sys.path.insert(0, os.path.dirname(meowauto_path))
        print(f'已添加meowauto路径: {os.path.dirname(meowauto_path)}')
    
    # 尝试导入主程序
    from app import MeowFieldAutoPiano
    print('✓ 主程序导入成功')
    
    # 创建应用实例
    app = MeowFieldAutoPiano()
    print('✓ 应用实例创建成功')
    
    # 启动程序
    print('正在启动主循环...')
    app.run()
    
except ImportError as e:
    print(f'❌ 模块导入失败: {e}')
    print('\\n详细错误信息:')
    traceback.print_exc()
    print('\\n🔧 可能的解决方案:')
    print('1. 检查meowauto目录结构是否完整')
    print('2. 确保所有依赖包已正确安装')
    print('3. 运行 test_module_loading.py 进行诊断')
    input('\\n按回车键退出...')
    
except Exception as e:
    print(f'❌ 程序启动失败: {e}')
    print('\n详细错误信息:')
    traceback.print_exc()
    input('\n按回车键退出...')
    
finally:
    print('\n程序已退出')
"

:: 检查程序退出状态
if %errorLevel% neq 0 (
    echo.
    echo ❌ 程序异常退出，错误代码: %errorLevel%
    echo.
    echo 🔧 建议的解决方案:
    echo 1. 运行 test_module_loading.py 检查模块状态
    echo 2. 检查meowauto目录结构是否完整
    echo 3. 确保所有依赖包已正确安装
    echo 4. 检查Python环境是否正确
    echo.
    pause
)

echo.
echo 👋 程序已退出
pause

