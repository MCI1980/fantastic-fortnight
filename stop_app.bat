@echo off
REM Stops any running Golf Coach server.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*streamlit run streamlit_app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if /i "%~1"=="quiet" exit /b 0
echo Golf Coach stopped.
pause
