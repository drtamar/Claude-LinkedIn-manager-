@echo off
title LinkedIn Manager
color 0B

echo ==================================================
echo            LinkedIn Manager - Launcher
echo ==================================================
echo.

REM Folder this script lives in (with trailing backslash)
set "ROOT=%~dp0"

REM --- Safety checks -------------------------------------------------
if not exist "%ROOT%backend\app\main.py" (
  echo [ERROR] backend folder not found.
  echo Make sure this file is inside the Claude-LinkedIn-manager- folder
  echo and that you are on the correct branch.
  echo.
  pause
  exit /b 1
)

if not exist "%ROOT%.env" (
  echo [WARNING] No .env file found.
  echo The backend needs your ANTHROPIC_API_KEY to work.
  echo Run Setup-First-Time.bat first.
  echo.
  pause
)

REM --- Start the backend in its own window --------------------------
echo Starting backend on http://localhost:8000 ...
start "LinkedIn Manager - Backend" cmd /k "cd /d "%ROOT%backend" && python -m uvicorn app.main:app --reload --port 8000"

REM --- Start the frontend in its own window -------------------------
echo Starting frontend on http://localhost:5173 ...
start "LinkedIn Manager - Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

REM --- Wait for servers to boot, then open the browser -------------
echo.
echo Waiting for the app to start up...
timeout /t 8 /nobreak >nul
start "" http://localhost:5173

echo.
echo ==================================================
echo  The app is opening in your browser.
echo.
echo  Two server windows are now running:
echo    - "LinkedIn Manager - Backend"
echo    - "LinkedIn Manager - Frontend"
echo.
echo  Keep both open while using the app.
echo  Close them (or run Stop-LinkedIn-Manager.bat) to stop.
echo ==================================================
echo.
echo You can close THIS window now.
timeout /t 5 /nobreak >nul
