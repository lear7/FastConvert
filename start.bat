@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

python fast_convert.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error. Please run install_deps.bat first.
    pause
)
