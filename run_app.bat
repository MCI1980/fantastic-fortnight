@echo off
REM Golf Coach launcher for the simulator PC.
REM First run creates a virtual environment and installs dependencies.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo Starting Golf Coach. Open the "Network URL" shown below on your phone (same Wi-Fi).
echo Press Ctrl+C in this window to stop.
echo.
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false
endlocal
