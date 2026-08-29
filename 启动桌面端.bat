@echo off
chcp 65001 >nul
title AI Desktop System

echo =========================================
echo         AI Desktop System Starting...
echo =========================================
echo.

cd /d "%~dp0"

echo [1/3] Clean up old processes...
taskkill /f /fi "WINDOWTITLE eq AI-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq AI-Frontend" >nul 2>&1

echo [2/3] Starting backend (port 18327)...
set "API_PORT=18327"
set BKDIR=%~dp0backend
start "AI-Backend" /min cmd /c "cd /d %BKDIR% && python run.py"

echo [3/3] Waiting for backend...
set RETRIES=0
:wait_loop
timeout /t 2 /nobreak >nul 2>nul
curl -s http://127.0.0.1:18327/api/system/status >nul 2>&1
if not errorlevel 1 goto ready
set /a RETRIES+=1
if %RETRIES% lss 15 goto wait_loop

echo.
echo ===== FAILED: Backend did not start =====
echo Possible causes:
echo   1. Python not in PATH
echo   2. Port 18327 in use
echo   3. Try manually: cd backend ^&^& python run.py
echo =========================================
echo.
pause
exit /b

:ready
echo [Backend OK]

echo [4/4] Starting frontend...
set FRDIR=%~dp0frontend
start "AI-Frontend" /min cmd /c "cd /d %FRDIR% && npm run dev"

timeout /t 6 /nobreak >nul 2>nul
start http://localhost:3000

echo.
echo =========================================
echo   AI Desktop System Started!
echo   Backend: http://localhost:18327
echo   Frontend: http://localhost:3000
echo =========================================
echo.
echo Close this window to stop services.
echo.
pause >nul

taskkill /f /fi "WINDOWTITLE eq AI-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq AI-Frontend" >nul 2>&1
echo Done.
