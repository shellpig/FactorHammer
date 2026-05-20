@echo off
setlocal

cd /d "%~dp0"
if exist "%~dp0tools\node\node.exe" set "PATH=%~dp0tools\node;%PATH%"
set "PNPM_PACKAGE=pnpm@11.1.1"
set "COREPACK_CMD=%~dp0tools\node\corepack.cmd"
if exist "%~dp0tools\node\corepack.cmd" set "PATH=%~dp0tools\node;%~dp0tools\node\node_modules\corepack\dist;%PATH%"
set "PYTHONPATH=%CD%"

if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%APPDATA%\uv\bin\uv.exe"         set "PATH=%APPDATA%\uv\bin;%PATH%"

if /I "%~1"=="frontend" goto :frontend

echo ================================================================
echo   FactorHammer - Dev Stack Launcher
echo ================================================================
echo   Backend  : http://localhost:8000   (FastAPI)
echo   Frontend : http://localhost:3000   (Next.js)
echo   Page     : http://localhost:3000/dashboard
echo ================================================================
echo.

if not exist ".venv\Scripts\python.exe" goto :no_venv
if not exist "web\node_modules" goto :install_web

:start_services
echo Starting backend on port 8000 ...
start "FactorHammer-Backend-8000" cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000"

echo Starting frontend on port 3000 ...
start "FactorHammer-Frontend-3000" cmd /k call "%~f0" frontend

echo.
echo Waiting for frontend to be ready (max 60s) ...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 60;$i++){ try { $r=Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if($r.StatusCode -eq 200){$ok=$true; break} } catch { Start-Sleep -Milliseconds 800 } }; if($ok){ Write-Host '  -> Frontend ready' -ForegroundColor Green } else { Write-Host '  -> Timeout, opening anyway' -ForegroundColor Yellow }"

echo Opening browser ...
start "" http://localhost:3000/dashboard

echo.
echo ----------------------------------------------------------------
echo Services running in separate windows.
echo To stop: press Ctrl+C in each window, or close the window.
echo You can close THIS window now.
echo ----------------------------------------------------------------
echo.
pause
goto :eof

:no_venv
echo [ERROR] .venv not found. Please run install.bat or 'uv sync' first.
pause
exit /b 1

:install_web
echo [WARN] web\node_modules not found. Installing frontend deps...
call :ensure_pnpm
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
pushd web
call "%COREPACK_CMD%" pnpm install
popd
echo.
goto :start_services

:frontend
cd /d "%~dp0web"
call :ensure_pnpm
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
call "%COREPACK_CMD%" pnpm dev
exit /b %ERRORLEVEL%

:ensure_pnpm
if not exist "%COREPACK_CMD%" (
    echo [ERROR] pnpm not found and portable corepack is unavailable.
    exit /b 1
)
call "%COREPACK_CMD%" pnpm --version >nul 2>&1
if %ERRORLEVEL% EQU 0 exit /b 0
call "%COREPACK_CMD%" enable
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
call "%COREPACK_CMD%" prepare "%PNPM_PACKAGE%" --activate
exit /b %ERRORLEVEL%
