@echo off
setlocal EnableDelayedExpansion

where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo Installing dependencies...
uv sync

if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Dependencies installed. Start CaptureGPT with run.bat; it will ask for an API key if needed.
pause
exit /b 0
