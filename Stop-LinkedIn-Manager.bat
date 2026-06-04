@echo off
title LinkedIn Manager - Stop
color 0C

echo Stopping LinkedIn Manager servers...
echo.

REM Kill anything listening on the backend (8000) and frontend (5173/5174) ports
for %%P in (8000 5173 5174) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%P ^| findstr LISTENING') do (
    echo Stopping process on port %%P (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
  )
)

REM Also close the named server windows if still open
taskkill /FI "WINDOWTITLE eq LinkedIn Manager - Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LinkedIn Manager - Frontend*" /F >nul 2>&1

echo.
echo Done. The app has been stopped.
timeout /t 3 /nobreak >nul
