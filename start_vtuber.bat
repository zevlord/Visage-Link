@echo off
title Visage Link Launcher
echo ===================================================
echo            VISAGE LINK STARTUP UTILITY              
echo ===================================================
echo.

:: Get the directory of the batch file
set "PROJECT_DIR=%~dp0"
:: Strip the trailing backslash if it exists to prevent escaping double quotes
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: GPT-SoVITS directory path
set "VOICE_DIR=%PROJECT_DIR%\GPT-SoVITS"

echo [1/3] Launching GPT-SoVITS voice clone server (Conda GPTSovits)...
:: Start GPT-SoVITS using the Conda environment GPTSovits
start "GPT-SoVITS API" cmd /k "cd /d "%VOICE_DIR%" && call conda activate GPTSovits && python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml"

:: Wait 3 seconds for the TTS server to bind to port 9880
timeout /t 3 /nobreak >nul

echo [2/3] Launching FastAPI backend server...
:: Start FastAPI backend in a new command window, activating the .venv first
start "FastAPI Backend" cmd /k "cd /d "%PROJECT_DIR%" && .venv\Scripts\activate.bat && python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"

:: Wait 1 second for backend server to bind to port 8000
timeout /t 1 /nobreak >nul

echo [3/3] Launching Desktop Subtitle Overlay...
:: Start the Desktop Subtitle Overlay window
start "Subtitle Overlay" cmd /k "cd /d "%PROJECT_DIR%" && .venv\Scripts\activate.bat && python server/desktop_overlay.py"

echo.
echo ===================================================
echo Startup initiated!
echo  - Voice server: http://127.0.0.1:9880/
echo  - Control panel: http://127.0.0.1:8000/
echo.
echo Leave this window open while using the Vtuber.
echo.
echo --- PRESS ANY KEY IN THIS WINDOW TO SHUT DOWN ALL SERVERS ---
echo ===================================================
pause >nul

echo.
echo Stopping servers...
:: Close the command windows and kill their child processes cleanly using PowerShell command line filtering
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*api_v2.py*' -or $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*desktop_overlay.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Done! All processes terminated.
timeout /t 2 >nul
