@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8765"
"%~dp0..\..\.venv\Scripts\python.exe" watch_server.py %*
pause
