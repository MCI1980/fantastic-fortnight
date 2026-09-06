@echo off
REM Removes the login autostart and stops the app.
set "VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GolfCoach.vbs"
if exist "%VBS%" del "%VBS%"
call "%~dp0stop_app.bat" quiet
echo Autostart removed and Golf Coach stopped. Use run_app.bat to start it by hand.
pause
