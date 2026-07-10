@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 6003 > server.log 2>&1
