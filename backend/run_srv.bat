@echo off
chcp 65001 >nul
set PYTHONPATH=%~dp0
cd /d "%~dp0"
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 6003
