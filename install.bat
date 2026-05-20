@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%~dp0"
set "NODE_VERSION=v22.11.0"
set "PNPM_VERSION=11.1.1"
set "NODE_DIST=node-v22.11.0-win-x64"
set "TOOLS_DIR=%ROOT%tools"
set "NODE_DIR=%TOOLS_DIR%\node"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "NODE_ZIP=%TOOLS_DIR%\%NODE_DIST%.zip"
set "SHASUMS_FILE=%TOOLS_DIR%\SHASUMS256.txt"
set "NODE_TMP_DIR=%TOOLS_DIR%\node_extract_tmp"
set "NODE_ZIP_URL=https://nodejs.org/dist/v22.11.0/node-v22.11.0-win-x64.zip"
set "NODE_SUMS_URL=https://nodejs.org/dist/v22.11.0/SHASUMS256.txt"

echo.
echo  ====================================
echo   FactorHammer Setup
echo  ====================================
echo.

echo [1/5] Checking uv package manager...
set "UV_EXE=uv"
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
        goto :uv_found
    )
    if exist "%APPDATA%\uv\bin\uv.exe" (
        set "UV_EXE=%APPDATA%\uv\bin\uv.exe"
        set "PATH=%APPDATA%\uv\bin;%PATH%"
        goto :uv_found
    )

    echo      uv not found. Installing...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo  [ERROR] Failed to install uv.
        echo  Please visit https://docs.astral.sh/uv/ and install manually, then re-run.
        echo.
        pause
        exit /b 1
    )

    set "PATH=%USERPROFILE%\.local\bin;%APPDATA%\uv\bin;%PATH%"

    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
        goto :uv_found
    )
    if exist "%APPDATA%\uv\bin\uv.exe" (
        set "UV_EXE=%APPDATA%\uv\bin\uv.exe"
        goto :uv_found
    )

    echo.
    echo  [ERROR] uv installed but not found. Close and re-run install.bat.
    echo.
    pause
    exit /b 1
) else (
    echo      uv already installed.
)

:uv_found
echo      OK

echo.
echo [2/5] Installing Python packages (may take a few minutes)...
echo.
set "UV_LINK_MODE=copy"
"%UV_EXE%" sync
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo      Sync failed. Removing old .venv and retrying...
    echo.
    if exist ".venv" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Recurse -Force '.venv'"
    )
    "%UV_EXE%" sync
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo  [ERROR] Package installation failed.
        echo.
        pause
        exit /b 1
    )
)
echo      OK

echo.
echo [3/5] Checking portable Node.js (%NODE_VERSION%)...
if exist "%NODE_EXE%" (
    echo      Found %NODE_EXE%, skipping download.
) else (
    call :install_node_portable
    if !ERRORLEVEL! NEQ 0 (
        pause
        exit /b 1
    )
)
echo      OK

echo.
echo [4/5] Enabling corepack and installing frontend dependencies...
set "PATH=%NODE_DIR%;%PATH%"

set "NODE_ACTUAL_VERSION="
for /f "usebackq delims=" %%V in (`node --version 2^>nul`) do set "NODE_ACTUAL_VERSION=%%V"
if not defined NODE_ACTUAL_VERSION (
    echo  [ERROR] node command is unavailable after PATH injection.
    pause
    exit /b 1
)
if /I not "%NODE_ACTUAL_VERSION%"=="%NODE_VERSION%" (
    echo  [ERROR] Node version mismatch. Expected %NODE_VERSION%, got %NODE_ACTUAL_VERSION%.
    pause
    exit /b 1
)
echo      Node version: %NODE_ACTUAL_VERSION%

corepack --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] corepack is unavailable under portable Node.
    pause
    exit /b 1
)
echo      corepack available.

pushd web
corepack enable
if %ERRORLEVEL% NEQ 0 (
    popd
    echo  [ERROR] corepack enable failed in web directory.
    pause
    exit /b 1
)

set "PNPM_ACTUAL_VERSION="
for /f "usebackq delims=" %%V in (`pnpm --version 2^>nul`) do set "PNPM_ACTUAL_VERSION=%%V"
if not defined PNPM_ACTUAL_VERSION (
    popd
    echo  [ERROR] pnpm command is unavailable after corepack enable.
    pause
    exit /b 1
)
if /I not "%PNPM_ACTUAL_VERSION%"=="%PNPM_VERSION%" (
    popd
    echo  [ERROR] pnpm version mismatch. Expected %PNPM_VERSION%, got %PNPM_ACTUAL_VERSION%.
    pause
    exit /b 1
)
echo      pnpm version: %PNPM_ACTUAL_VERSION%

call pnpm install --frozen-lockfile
if %ERRORLEVEL% NEQ 0 (
    popd
    echo  [ERROR] pnpm install --frozen-lockfile failed.
    pause
    exit /b 1
)
popd
echo      OK

echo.
echo [5/5] Setting up .env config...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo      .env created.
) else (
    echo      .env already exists, skipping.
)
echo      OK

echo.
echo  ====================================
echo   Setup complete!
echo   Double-click run_factorhammer.bat to start.
echo  ====================================
echo.
pause
exit /b 0

:install_node_portable
if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
set /a NODE_ATTEMPT=1

:node_retry
echo      Download attempt !NODE_ATTEMPT!/3...
call :download_extract_verify_node
if !ERRORLEVEL! EQU 0 exit /b 0

if !NODE_ATTEMPT! GEQ 3 (
    echo.
    echo  [ERROR] Failed to install portable Node.js after 3 attempts.
    echo  Manual download:
    echo    %NODE_ZIP_URL%
    echo  Extract into:
    echo    %NODE_DIR%
    echo  Make sure node.exe is directly at:
    echo    %NODE_EXE%
    echo  (not under %NODE_DIR%\%NODE_DIST%\node.exe)
    echo.
    exit /b 1
)

set /a NODE_ATTEMPT+=1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 1"
goto :node_retry

:download_extract_verify_node
if exist "%NODE_ZIP%" del /f /q "%NODE_ZIP%" >nul 2>&1
if exist "%SHASUMS_FILE%" del /f /q "%SHASUMS_FILE%" >nul 2>&1
if exist "%NODE_TMP_DIR%" rmdir /s /q "%NODE_TMP_DIR%" >nul 2>&1
if exist "%NODE_DIR%" rmdir /s /q "%NODE_DIR%" >nul 2>&1

echo        Downloading %NODE_DIST%.zip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%NODE_ZIP_URL%' -OutFile '%NODE_ZIP%' -UseBasicParsing"
if %ERRORLEVEL% NEQ 0 (
    echo        [WARN] Node zip download failed.
    exit /b 1
)

echo        Downloading SHASUMS256.txt ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%NODE_SUMS_URL%' -OutFile '%SHASUMS_FILE%' -UseBasicParsing"
if %ERRORLEVEL% NEQ 0 (
    echo        [WARN] SHASUMS256.txt download failed.
    exit /b 1
)

set "EXPECTED_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$line = Get-Content -LiteralPath '%SHASUMS_FILE%' | Where-Object { $_ -match ' node-v22.11.0-win-x64\.zip$' } | Select-Object -First 1; if (-not $line) { exit 1 }; ($line -split '\s+')[0].ToLowerInvariant()"`) do set "EXPECTED_HASH=%%H"
if not defined EXPECTED_HASH (
    echo        [WARN] Unable to resolve expected SHA-256 from SHASUMS256.txt.
    exit /b 1
)

set "ACTUAL_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -LiteralPath '%NODE_ZIP%' -Algorithm SHA256).Hash.ToLowerInvariant()"`) do set "ACTUAL_HASH=%%H"
if not defined ACTUAL_HASH (
    echo        [WARN] Unable to calculate zip SHA-256.
    exit /b 1
)

if /I not "!ACTUAL_HASH!"=="!EXPECTED_HASH!" (
    echo        [WARN] SHA-256 mismatch detected.
    echo        Expected: !EXPECTED_HASH!
    echo        Actual  : !ACTUAL_HASH!
    exit /b 1
)
echo        SHA-256 verified.

echo        Extracting Node runtime ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%NODE_ZIP%' -DestinationPath '%NODE_TMP_DIR%' -Force"
if %ERRORLEVEL% NEQ 0 (
    echo        [WARN] Expand-Archive failed.
    exit /b 1
)

if not exist "%NODE_TMP_DIR%\%NODE_DIST%\node.exe" (
    echo        [WARN] Extracted structure missing %NODE_DIST%\node.exe.
    exit /b 1
)

mkdir "%NODE_DIR%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%NODE_TMP_DIR%\%NODE_DIST%' -Force | Move-Item -Destination '%NODE_DIR%' -Force"
if %ERRORLEVEL% NEQ 0 (
    echo        [WARN] Failed to flatten extracted Node folder.
    exit /b 1
)

if not exist "%NODE_EXE%" (
    echo        [WARN] Portable Node install incomplete: node.exe not found.
    exit /b 1
)

if exist "%NODE_TMP_DIR%" rmdir /s /q "%NODE_TMP_DIR%" >nul 2>&1
if exist "%NODE_ZIP%" del /f /q "%NODE_ZIP%" >nul 2>&1
if exist "%SHASUMS_FILE%" del /f /q "%SHASUMS_FILE%" >nul 2>&1
exit /b 0
