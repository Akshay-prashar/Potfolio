@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] venv not found at "%~dp0venv"
  echo Create it first: python -m venv venv
  pause
  exit /b 1
)

echo Starting IPL app on http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000/"
"%~dp0venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

