@echo off
setlocal

cd /d "%~dp0"
if exist "%~dp0tools\node\node.exe" set "PATH=%~dp0tools\node;%PATH%"
set "PNPM_PACKAGE=pnpm@11.1.1"
set "PNPM_HOME=%~dp0tools\pnpm"
set "PNPM_CLI=%PNPM_HOME%\node_modules\pnpm\bin\pnpm.cjs"
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
if not exist "%PNPM_CLI%" (
    if exist "%~dp0tools\node\npm.cmd" (
        call "%~dp0tools\node\npm.cmd" install --prefix "%PNPM_HOME%" "%PNPM_PACKAGE%"
        if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
    )
)
pushd web
if exist "%PNPM_CLI%" (
    call "%~dp0tools\node\node.exe" "%PNPM_CLI%" install
) else (
    call pnpm install
)
popd
echo.
goto :start_services

:frontend
cd /d "%~dp0web"
if exist "%PNPM_CLI%" (
    call "%~dp0tools\node\node.exe" "%PNPM_CLI%" dev
) else (
    call pnpm dev
)
exit /b %ERRORLEVEL%
