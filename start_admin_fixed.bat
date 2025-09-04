@echo off
chcp 65001 >nul
title MeowField AutoPiano v1.0.6 - 管理员模式 (修复版)

echo.
echo ========================================
echo    MeowField AutoPiano v1.0.6
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

:: 选择Python命令（优先 py -3，回退 python）
set "PY_CMD="
where py >nul 2>&1 && (set "PY_CMD=py -3")
if not defined PY_CMD (
    where python >nul 2>&1 && (set "PY_CMD=python")
)

:: 检查Python是否安装
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

:: 依赖安装：优先使用 requirements.txt；否则逐项检查必要依赖
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
    echo 未找到 requirements.txt，逐项检查必要依赖...
    rem tkinter 为内置，直接检测
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
%PY_CMD% start.py
if %errorLevel% == 0 (
    echo ✓ start.py 运行成功
    goto :end
)

:: 如果 start.py 失败，尝试运行 main.py
echo start.py 运行失败，尝试运行 main.py...
%PY_CMD% main.py
if %errorLevel% == 0 (
    echo ✓ main.py 运行成功
    goto :end
)

:: 如果都失败了，尝试直接运行 app.py
echo main.py 运行失败，尝试直接运行 app.py...
%PY_CMD% -c "
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

