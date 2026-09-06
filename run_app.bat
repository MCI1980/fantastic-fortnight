@echo off
REM Golf Coach launcher for the simulator PC.
REM First run creates a virtual environment and installs dependencies.
setlocal
cd /d "%~dp0"

REM --- Find a real Python 3 (the Windows "python" Store shortcut does not count) ---
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY (
    echo.
    echo Python 3 is not installed. The "python" command on this PC is only the
    echo Microsoft Store shortcut.
    echo.
    echo Install it, then run this file again:
    echo   winget install -e --id Python.Python.3.12
    echo or download it from https://www.python.org/downloads/ and tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with %PY% ...
    %PY% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
    echo Installing dependencies ^(first run only, one to two minutes^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency install failed. Check your internet connection and run this file again.
        pause
        exit /b 1
    )
)

echo.
echo Starting Golf Coach. Open the "Network URL" shown below on your phone (same Wi-Fi).
echo Press Ctrl+C in this window to stop.
echo.
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false
pause
endlocal
