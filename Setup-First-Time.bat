@echo off
title LinkedIn Manager - First Time Setup
color 0E

echo ==================================================
echo      LinkedIn Manager - First Time Setup
echo ==================================================
echo.
echo This installs everything the app needs. Run it once.
echo It may take a few minutes.
echo.
pause

set "ROOT=%~dp0"

REM --- 1. Create .env if missing ------------------------------------
if not exist "%ROOT%.env" (
  echo.
  echo Creating .env configuration file...
  copy "%ROOT%.env.example" "%ROOT%.env" >nul

  echo Generating security keys...
  for /f "delims=" %%k in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "SECRETKEY=%%k"
  for /f "delims=" %%k in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2^>nul') do set "COOKIEKEY=%%k"

  REM Write a fresh .env with generated keys (API key left as placeholder)
  (
    echo ANTHROPIC_API_KEY=sk-ant-PUT-YOUR-KEY-HERE
    echo SECRET_KEY=%SECRETKEY%
    echo LINKEDIN_COOKIE_SECRET=%COOKIEKEY%
    echo DATABASE_URL=sqlite:///./data/linkedin_manager.db
    echo FRONTEND_URL=http://localhost:5173
    echo CORS_ORIGINS=http://localhost:5173
    echo ENVIRONMENT=development
  ) > "%ROOT%.env"

  echo.
  echo [IMPORTANT] Opening .env so you can paste your Anthropic API key.
  echo Replace sk-ant-PUT-YOUR-KEY-HERE with your real key, then SAVE and close Notepad.
  echo Get a key at: https://console.anthropic.com
  echo.
  pause
  notepad "%ROOT%.env"
) else (
  echo .env already exists - keeping your existing settings.
)

REM --- 2. Install backend dependencies ------------------------------
echo.
echo ==================================================
echo  Installing backend (Python) dependencies...
echo ==================================================
cd /d "%ROOT%backend"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Backend install failed. Scroll up to see the error.
  pause
  exit /b 1
)

REM --- 3. Install frontend dependencies -----------------------------
echo.
echo ==================================================
echo  Installing frontend (Node) dependencies...
echo ==================================================
cd /d "%ROOT%frontend"
call npm install
if errorlevel 1 (
  echo.
  echo [ERROR] Frontend install failed. Is Node.js installed?
  echo Download it from https://nodejs.org if needed.
  pause
  exit /b 1
)

echo.
echo ==================================================
echo  Setup complete!
echo.
echo  Now double-click  Start-LinkedIn-Manager.bat
echo  to launch the app.
echo ==================================================
echo.
pause
