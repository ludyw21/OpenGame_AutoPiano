@echo off
chcp 65001 >nul
title MeowField AutoPiano v1.0.5 - 管理员模式 (修复版)

echo.
echo ========================================
echo    MeowField AutoPiano v1.0.5
echo    管理员模式启动脚本 (修复版)
echo ========================================
echo.
echo 本软件免费使用，如果你是从其他地方购入说明你已经受骗。请联系b站up主薮薮猫猫举报。

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✓ 已获得管理员权限
) else (
    echo ❌ 需要管理员权限运行
    echo 请右键选择"以管理员身份运行"
    pause
    exit /b 1
)

:: 检查Python是否安装
echo 正在检查Python环境...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python未安装或未添加到PATH
    echo 请先安装Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python环境检查通过: %PYTHON_VERSION%

:: 检查Python版本
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python版本过低，需要3.8+
    pause
    exit /b 1
)

:: 检查依赖包
echo.
echo 正在检查依赖包...
echo 检查 tkinter...
python -c "import tkinter; print('tkinter OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ tkinter 不可用
    pause
    exit /b 1
)

echo 检查 PIL...
python -c "import PIL; print('PIL OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠ PIL 缺失，正在安装...
    pip install pillow
    if %errorLevel% neq 0 (
        echo ❌ PIL 安装失败
        pause
        exit /b 1
    )
)

echo 检查 mido...
python -c "import mido; print('mido OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠ mido 缺失，正在安装...
    pip install mido
    if %errorLevel% neq 0 (
        echo ❌ mido 安装失败
        pause
        exit /b 1
    )
)

echo 检查 pygame...
python -c "import pygame; print('pygame OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠ pygame 缺失，正在安装...
    pip install pygame
    if %errorLevel% neq 0 (
        echo ❌ pygame 安装失败
        pause
        exit /b 1
    )
)

echo 检查 numpy...
python -c "import numpy; print('numpy OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠ numpy 缺失，正在安装...
    pip install numpy
    if %errorLevel% neq 0 (
        echo ❌ numpy 安装失败
        pause
        exit /b 1
    )
)

echo ✓ 所有依赖包检查完成

:: 创建必要目录
echo.
echo 正在创建必要目录...
if not exist "output" (
    mkdir output
    echo ✓ 已创建 output 目录
) else (
    echo ✓ output 目录已存在
)

if not exist "temp" (
    mkdir temp
    echo ✓ 已创建 temp 目录
) else (
    echo ✓ temp 目录已存在
)

if not exist "logs" (
    mkdir logs
    echo ✓ 已创建 logs 目录
) else (
    echo ✓ logs 目录已存在
)

echo ✓ 目录结构检查完成

:: 尝试直接运行Python脚本
echo.
echo 🚀 正在启动 MeowField AutoPiano...
echo.

:: 首先尝试运行 start.py
echo 尝试运行 start.py...
python start.py
if %errorLevel% == 0 (
    echo ✓ start.py 运行成功
    goto :end
)

:: 如果 start.py 失败，尝试运行 main.py
echo start.py 运行失败，尝试运行 main.py...
python main.py
if %errorLevel% == 0 (
    echo ✓ main.py 运行成功
    goto :end
)

:: 如果都失败了，尝试直接运行 app.py
echo main.py 运行失败，尝试直接运行 app.py...
python -c "
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath('app.py')))
try:
    from app import MeowFieldAutoPiano
    app = MeowFieldAutoPiano()
    app.run()
except Exception as e:
    print(f'启动失败: {e}')
    import traceback
    traceback.print_exc()
    input('按回车键退出...')
"

:end
:: 如果程序异常退出，暂停显示错误信息
if %errorLevel% neq 0 (
    echo.
    echo ❌ 程序异常退出，错误代码: %errorLevel%
    echo.
    echo 可能的解决方案:
    echo 1. 检查Python版本是否为3.8+
    echo 2. 确保所有依赖包已正确安装
    echo 3. 检查meowauto模块是否完整
    echo 4. 尝试使用普通模式启动 (start_normal.bat)
    echo.
    echo 请检查错误信息并联系开发者
    pause
)

echo.
echo 👋 程序已退出
pause

