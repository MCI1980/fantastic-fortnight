@echo off
REM Starts Golf Coach with no console window (used by the autostart shortcut).
REM Output goes to data\store\app.log. Run run_app.bat once first to install.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
if not exist "data\store" mkdir "data\store"
echo [%date% %time%] starting >> "data\store\app.log"
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false >> "data\store\app.log" 2>&1
