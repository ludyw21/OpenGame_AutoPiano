@echo off
setlocal
rem Pure batch launcher for MeowField AutoPiano (UTF-8 safe output)
cd /d "%~dp0"

rem Force console to UTF-8 for Python I/O (messages below stay ASCII)
chcp 65001 >nul

rem App directory handling
set "BASE_DIR=%~dp0"
set "APP_DIR=%BASE_DIR%app"
set "DID_PUSHD=0"
if exist "%APP_DIR%" (
  echo Using app directory: %APP_DIR%
  pushd "%APP_DIR%"
  set "DID_PUSHD=1"
) else (
  echo App directory not found. Running in base directory.
  set "APP_DIR=%BASE_DIR%"
)

rem Environment for UTF-8 and cleaner output
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONDONTWRITEBYTECODE=1"

rem Admin check (warn only, do not stop)
net session >nul 2>&1
if %errorlevel%==0 (
  echo Admin privilege OK
) else (
  echo WARNING: Not running as Administrator. Some features may require admin.
)

rem Pick Python command (prefer py -3)
set "PY_CMD="
where py >nul 2>&1 && (set "PY_CMD=py -3")
if not defined PY_CMD (
  where python >nul 2>&1 && (set "PY_CMD=python")
)
if not defined PY_CMD (
  echo ERROR: Python not found in PATH. Please install Python 3.8+.
  pause
  if "%DID_PUSHD%"=="1" popd
  endlocal & exit /b 1
)

echo Checking Python...
%PY_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Python not working. Please fix your Python installation.
  pause
  if "%DID_PUSHD%"=="1" popd
  endlocal & exit /b 1
)
for /f "tokens=*" %%i in ('%PY_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo %PYTHON_VERSION%

%PY_CMD% -c "import sys; exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Python 3.8+ is required.
  pause
  if "%DID_PUSHD%"=="1" popd
  endlocal & exit /b 1
)

echo.
echo Checking/installing dependencies...
if exist requirements.txt (
  echo Found requirements.txt, installing...
  %PY_CMD% -m pip install -r requirements.txt
  if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies from requirements.txt
    pause
    if "%DID_PUSHD%"=="1" popd
    endlocal & exit /b 1
  )
) else (
  echo requirements.txt not found. Checking minimal requirements...
  %PY_CMD% -c "import tkinter" >nul 2>&1 || (
    echo ERROR: tkinter not available. Please install Python with tkinter.
    pause & if "%DID_PUSHD%"=="1" popd & endlocal & exit /b 1
  )
  %PY_CMD% -c "import ttkbootstrap" >nul 2>&1 || %PY_CMD% -m pip install ttkbootstrap>=1.10.1
  %PY_CMD% -c "import mido" >nul 2>&1 || %PY_CMD% -m pip install mido>=1.3.0
  if %errorlevel% neq 0 ( echo ERROR: mido install failed & pause & if "%DID_PUSHD%"=="1" popd & endlocal & exit /b 1 )
  %PY_CMD% -c "import pygame" >nul 2>&1 || %PY_CMD% -m pip install pygame>=2.5.2
  if %errorlevel% neq 0 ( echo ERROR: pygame install failed & pause & if "%DID_PUSHD%"=="1" popd & endlocal & exit /b 1 )
  %PY_CMD% -c "import keyboard" >nul 2>&1 || %PY_CMD% -m pip install keyboard>=0.13.5
  if %errorlevel% neq 0 ( echo ERROR: keyboard install failed & pause & if "%DID_PUSHD%"=="1" popd & endlocal & exit /b 1 )
)
echo Dependencies OK

echo.
echo Preparing directories...
if not exist "output" ( mkdir output & echo Created output ) else ( echo output exists )
if not exist "temp"   ( mkdir temp   & echo Created temp   ) else ( echo temp exists )
if not exist "logs"   ( mkdir logs   & echo Created logs   ) else ( echo logs exists )
echo Directories ready

echo.
echo Launching MeowField AutoPiano...

set "LAUNCH_OK=0"

rem Prefer explicit app/start.py if present
if exist "start.py" (
  echo Trying start.py ...
  %PY_CMD% start.py
  if %errorlevel%==0 (
    set "LAUNCH_OK=1"
    goto :end
  )
) else (
  rem If we are not inside app dir (no start.py found), try using absolute path
  if exist "%APP_DIR%\start.py" (
    echo Trying %APP_DIR%\start.py ...
    %PY_CMD% "%APP_DIR%\start.py"
    if %errorlevel%==0 (
      set "LAUNCH_OK=1"
      goto :end
    )
  )
)

echo start.py not available or failed. Trying main.py ...
if exist "main.py" (
  %PY_CMD% main.py
  if %errorlevel%==0 (
    set "LAUNCH_OK=1"
    goto :end
  )
)

echo main.py failed. Trying app.py class entry ...
%PY_CMD% -c "import sys,os,traceback; sys.path.insert(0, os.getcwd()); from app import MeowFieldAutoPiano; app=MeowFieldAutoPiano(); app.run()"
if %errorlevel%==0 (
  set "LAUNCH_OK=1"
  goto :end
)

echo.
echo ERROR: Application exited with error. See messages above.
pause
if "%DID_PUSHD%"=="1" popd
endlocal & exit /b 1

:end
if "%LAUNCH_OK%"=="1" (
  echo Application exited normally.
) else (
  echo Application exited abnormally.
)
if "%DID_PUSHD%"=="1" popd
endlocal & exit /b 0
