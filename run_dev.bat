@echo off
echo Starting QuantTrader API + Web (development)...
echo.
echo [1/2] Starting FastAPI backend on port 8000...
start "QuantTrader API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
echo [2/2] Starting Next.js frontend on port 3000...
start "QuantTrader Web" cmd /k "cd web && pnpm dev"
echo.
echo Both servers started. Press any key to exit this launcher.
pause >nul
