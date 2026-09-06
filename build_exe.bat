@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

echo =============================================
echo   Build Fast Convert.exe
echo =============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

python -c "import PySide6, psutil, PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing build dependencies...
    python -m pip install -r requirements.txt pyinstaller
)

echo Checking obsolete pathlib backport...
python -m pip show pathlib >nul 2>&1
if not errorlevel 1 (
    echo Removing obsolete pathlib backport ^(conflicts with PyInstaller^)...
    python -m pip uninstall -y pathlib
)

echo Stopping running Fast Convert instances...
taskkill /F /IM "Fast Convert.exe" >nul 2>&1

echo Checking source files...
python -m py_compile fast_convert.py i18n.py
if errorlevel 1 (
    echo [ERROR] Source compile check failed.
    pause
    exit /b 1
)

echo Building single exe...
echo (PyInstaller may take 1-2 minutes, please wait...)
python -m PyInstaller --noconfirm --clean FastConvert.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
if errorlevel 1 (
    echo [WARN] Failed to create desktop shortcut.
)

echo.
echo =============================================
echo Build complete!
echo Output: %CD%\dist\Fast Convert.exe
echo =============================================
pause
exit /b 0
