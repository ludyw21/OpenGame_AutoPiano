<#
PowerShell launcher for MeowField AutoPiano (UTF-8 safe output)
This script is the PowerShell equivalent of start_admin_fixed.bat
#>

# Set script to exit on error
$ErrorActionPreference = "Stop"

# Get base directory
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppDir = Join-Path $BaseDir "app"
$DidPushd = $false

# Set console to UTF-8
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()

# App directory handling
if (Test-Path -Path $AppDir -PathType Container) {
    Write-Host "Using app directory: $AppDir"
    Push-Location $AppDir
    $DidPushd = $true
} else {
    Write-Host "App directory not found. Running in base directory."
    $AppDir = $BaseDir
}

# Environment variables for UTF-8 and cleaner output
$env:PYTHONUTF8 = 1
$env:PYTHONIOENCODING = "utf-8"
$env:PIP_DISABLE_PIP_VERSION_CHECK = 1
$env:PYTHONDONTWRITEBYTECODE = 1

# Admin check (warn only, do not stop)
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if ($IsAdmin) {
    Write-Host "Admin privilege OK"
} else {
    Write-Warning "Not running as Administrator. Some features may require admin."
}

# Pick Python command (prefer py -3)
$PyCmd = $null
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PyCmd = "py -3"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PyCmd = "python"
}

if (-not $PyCmd) {
    Write-Error "Python not found in PATH. Please install Python 3.8+."
    pause
    if ($DidPushd) { Pop-Location }
    exit 1
}

Write-Host "Checking Python..."
# Check if Python works
try {
    & $PyCmd --version | Out-Null
} catch {
    Write-Error "Python not working. Please fix your Python installation."
    pause
    if ($DidPushd) { Pop-Location }
    exit 1
}

# Get Python version
$PythonVersion = & $PyCmd --version 2>&1
Write-Host $PythonVersion

# Check Python version >= 3.8
try {
    & $PyCmd -c "import sys; exit(0 if sys.version_info>=(3,8) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python 3.8+ is required."
        pause
        if ($DidPushd) { Pop-Location }
        exit 1
    }
} catch {
    Write-Error "Failed to check Python version."
    pause
    if ($DidPushd) { Pop-Location }
    exit 1
}

Write-Host ""
Write-Host "Checking/installing dependencies..."

# Check if requirements.txt exists in current directory or base directory
$CurrentDirRequirements = Join-Path (Get-Location) "requirements.txt"
$BaseDirRequirements = Join-Path $BaseDir "requirements.txt"

if (Test-Path -Path $CurrentDirRequirements -PathType Leaf) {
    $RequirementsPath = $CurrentDirRequirements
} elseif (Test-Path -Path $BaseDirRequirements -PathType Leaf) {
    $RequirementsPath = $BaseDirRequirements
}

if ($RequirementsPath) {
    Write-Host "Found requirements.txt, installing..."
    try {
        & $PyCmd -m pip install -r $RequirementsPath
        if ($LASTEXITCODE -ne 0) {
            throw "Installation failed"
        }
    } catch {
        Write-Error "Failed to install dependencies from requirements.txt"
        pause
        if ($DidPushd) { Pop-Location }
        exit 1
    }
} else {
    Write-Host "requirements.txt not found. Checking minimal requirements..."
    
    # Function to check and install a package if needed
    function Check-And-Install ($PackageName, $Version = $null) {
        try {
            & $PyCmd -c "import $PackageName" | Out-Null
            Write-Host "  ✓ $PackageName already installed"
            return $true
        } catch {
            Write-Host "  ✗ $PackageName not found, installing..."
            $InstallCmd = "$PyCmd -m pip install $PackageName"
            if ($Version) {
                $InstallCmd += ">=$Version"
            }
            try {
                Invoke-Expression $InstallCmd
                if ($LASTEXITCODE -ne 0) {
                    throw "Installation failed"
                }
                Write-Host "  ✓ $PackageName installed successfully"
                return $true
            } catch {
                Write-Error "$PackageName install failed"
                pause
                if ($DidPushd) { Pop-Location }
                exit 1
            }
        }
    }
    
    # Check and install required packages
    Write-Host "Checking required packages..."
    $null = Check-And-Install "tkinter"
    $null = Check-And-Install "ttkbootstrap" "1.10.1"
    $null = Check-And-Install "mido" "1.3.0"
    $null = Check-And-Install "pygame" "2.5.2"
    $null = Check-And-Install "keyboard" "0.13.5"
}

Write-Host "Dependencies OK"

Write-Host ""
Write-Host "Preparing directories..."

# Create directories if they don't exist
foreach ($dir in @("output", "temp", "logs")) {
    if (-not (Test-Path -Path $dir -PathType Container)) {
        New-Item -Path $dir -ItemType Directory | Out-Null
        Write-Host "Created $dir"
    } else {
        Write-Host "$dir exists"
    }
}

Write-Host "Directories ready"

Write-Host ""
Write-Host "Launching MeowField AutoPiano..."

$LaunchOk = $false

# Prefer explicit app/start.py if present
if (Test-Path -Path "start.py" -PathType Leaf) {
    Write-Host "Trying start.py ..."
    try {
        & $PyCmd start.py
        if ($LASTEXITCODE -eq 0) {
            $LaunchOk = $true
        }
    } catch {
        Write-Host "Error running start.py: $_"
    }
    if ($LaunchOk) {
        # Application started successfully, skip further attempts
        Write-Host "Application exited normally."
        if ($DidPushd) { Pop-Location }
        exit 0
    }
} else {
    # If we are not inside app dir (no start.py found), try using absolute path
    $StartPyPath = Join-Path $AppDir "start.py"
    if (Test-Path -Path $StartPyPath -PathType Leaf) {
        Write-Host "Trying $StartPyPath ..."
        try {
            & $PyCmd "$StartPyPath"
            if ($LASTEXITCODE -eq 0) {
                $LaunchOk = $true
            }
        } catch {
            Write-Host "Error running ${StartPyPath}: $_"
        }
        if ($LaunchOk) {
            # Application started successfully, skip further attempts
            Write-Host "Application exited normally."
            if ($DidPushd) { Pop-Location }
            exit 0
        }
    }
}

# Try main.py
if (Test-Path -Path "main.py" -PathType Leaf) {
    Write-Host "start.py not available or failed. Trying main.py ..."
    try {
        & $PyCmd main.py
        if ($LASTEXITCODE -eq 0) {
            $LaunchOk = $true
        }
    } catch {
        Write-Host "Error running main.py: $_"
    }
    if ($LaunchOk) {
        # Application started successfully, skip further attempts
        Write-Host "Application exited normally."
        if ($DidPushd) { Pop-Location }
        exit 0
    }
}

# Try app.py class entry
Write-Host "main.py failed. Trying app.py class entry ..."
try {
    $Cmd = "import sys,os,traceback; sys.path.insert(0, os.getcwd()); from app import MeowFieldAutoPiano; app=MeowFieldAutoPiano(); app.run()"
    & $PyCmd -c $Cmd
    if ($LASTEXITCODE -eq 0) {
        $LaunchOk = $true
    }
} catch {
    Write-Host "Error running app.py class entry: $_"
}

if (-not $LaunchOk) {
    Write-Host ""
    Write-Error "Application exited with error. See messages above."
    pause
    if ($DidPushd) { Pop-Location }
    exit 1
}

# Final status check
if ($LaunchOk) {
    Write-Host "Application exited normally."
} else {
    Write-Host "Application exited abnormally."
}

if ($DidPushd) { Pop-Location }
exit 0