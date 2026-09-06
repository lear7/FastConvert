@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

echo Installing Fast Convert dependencies...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if not defined PIP_INDEX_URL (
    set "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn"
)

echo Using index: %PIP_INDEX_URL%
python -m pip install --disable-pip-version-check --no-input -i "%PIP_INDEX_URL%" --trusted-host "%PIP_TRUSTED_HOST%" -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependencies install failed.
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully.
pause
exit /b 0
