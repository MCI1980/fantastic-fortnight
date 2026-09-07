@echo off
REM Makes Golf Coach start hidden every time you log in to Windows,
REM starts it now, and stops the PC from sleeping while plugged in.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run run_app.bat once first so the environment gets installed.
    pause
    exit /b 1
)

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\GolfCoach.vbs"
> "%VBS%" echo Set sh = CreateObject("WScript.Shell")
>> "%VBS%" echo sh.CurrentDirectory = "%~dp0"
>> "%VBS%" echo sh.Run "cmd /c ""%~dp0run_app_quiet.bat""", 0, False

call "%~dp0stop_app.bat" quiet
wscript "%VBS%"

powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change hibernate-timeout-ac 0 >nul 2>&1

echo.
echo Golf Coach is now running in the background and will start automatically
echo every time you log in to Windows. Sleep while plugged in has been turned off.
echo.
echo   On this PC:    http://localhost:8501
echo   On your phone: the Network URL shown by run_app.bat (http://192.168.x.x:8501)
echo.
echo To stop it:            double-click stop_app.bat
echo To remove autostart:   double-click remove_autostart.bat
echo Log file:              data\store\app.log
echo.
pause
endlocal
