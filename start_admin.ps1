# 管理员权限启动自动弹琴软件 (PowerShell版本)
# 右键选择"以管理员身份运行PowerShell"，然后运行此脚本

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "🎹 正在以管理员权限启动自动弹琴软件..." -ForegroundColor Green
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ 需要管理员权限！" -ForegroundColor Red
    Write-Host "请右键选择'以管理员身份运行PowerShell'，然后重新运行此脚本" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "✅ 已获得管理员权限" -ForegroundColor Green
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot
Write-Host "📁 当前工作目录: $PWD" -ForegroundColor Cyan
Write-Host ""

# 检查Python是否安装
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 错误: 未找到Python，请先安装Python 3.7或更高版本" -ForegroundColor Red
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 检查依赖是否安装
Write-Host "📦 检查依赖包..." -ForegroundColor Cyan
try {
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 2>$null
    Write-Host "✅ 依赖包检查完成" -ForegroundColor Green
} catch {
    Write-Host "⚠️ 警告: 部分依赖包安装失败，尝试继续运行..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 以管理员权限启动软件..." -ForegroundColor Green

# 启动软件
try {
    python auto_piano_py312.py
} catch {
    Write-Host ""
    Write-Host "❌ 程序运行出错，请检查错误信息" -ForegroundColor Red
    Read-Host "按回车键退出"
} 