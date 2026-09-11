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

echo [1/3] Launching GPT-SoVITS voice clone server...
:: Start GPT-SoVITS using UTF-8 encoding so Chinese/Japanese text doesn't crash charmap codec
start "GPT-SoVITS API" cmd /k "chcp 65001 >nul && cd /d "%VOICE_DIR%" && set "NLTK_DISABLE_IMPORT_SECURITY=1" && set "PYTHONIOENCODING=utf-8" && call "%PROJECT_DIR%\.venv\Scripts\activate.bat" && python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml"

echo Waiting for GPT-SoVITS voice server to bind to port 9880...
powershell -Command "$timeout = 30; $timer = [Diagnostics.Stopwatch]::StartNew(); while ($timer.Elapsed.TotalSeconds -lt $timeout) { try { $tcp = New-Object Net.Sockets.TcpClient('127.0.0.1', 9880); $tcp.Close(); break } catch { Start-Sleep -Milliseconds 500 } }; if ($timer.Elapsed.TotalSeconds -ge $timeout) { Write-Host 'Warning: TTS server took longer than 30s. Continuing...' }"

echo [2/3] Launching FastAPI backend server...
:: Start FastAPI backend in a new command window, activating the .venv first
start "FastAPI Backend" cmd /k "chcp 65001 >nul && cd /d "%PROJECT_DIR%" && set "PYTHONIOENCODING=utf-8" && .venv\Scripts\activate.bat && python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"

:: Wait 1 second for backend server to bind to port 8000
timeout /t 1 /nobreak >nul

echo [3/3] Launching Desktop Subtitle Overlay...
:: Start the Desktop Subtitle Overlay window
start "Subtitle Overlay" cmd /k "chcp 65001 >nul && cd /d "%PROJECT_DIR%" && set "PYTHONIOENCODING=utf-8" && .venv\Scripts\activate.bat && python server/desktop_overlay.py"

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

:: 1. Terminate all processes holding port 8000 and port 9880 (clean tree kill)
powershell -Command "$ports = @(8000, 9880); foreach ($p in $ports) { $lines = netstat -ano | Select-String 'LISTENING' | Select-String (':{0}\b' -f $p); foreach ($l in $lines) { $pidVal = ($l.Line.Trim() -split '\s+')[-1]; if ($pidVal -match '^\d+$' -and $pidVal -ne '0') { taskkill /F /T /PID $pidVal 2>$null } } }"

:: 2. Close spawned command prompt windows by window title
taskkill /F /T /FI "WINDOWTITLE eq GPT-SoVITS API*" 2>nul
taskkill /F /T /FI "WINDOWTITLE eq FastAPI Backend*" 2>nul
taskkill /F /T /FI "WINDOWTITLE eq Subtitle Overlay*" 2>nul
taskkill /F /T /FI "WINDOWTITLE eq AI Vtuber Overlay Subtitles*" 2>nul

echo Done! All processes terminated.
timeout /t 2 >nul
