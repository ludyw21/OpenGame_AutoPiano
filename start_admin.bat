@echo off
chcp 65001 >nul
title 管理员权限启动自动弹琴软件
echo 正在以管理员权限启动自动弹琴软件...
echo.

REM 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✓ 已获得管理员权限
) else (
    echo 需要管理员权限，正在请求...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo 检查依赖包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
if errorlevel 1 (
    echo 警告: 部分依赖包安装失败，尝试继续运行...
)

echo 以管理员权限启动软件...
python auto_piano_py312.py

if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查错误信息
    pause
) 