@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo uv is required. Run setup.bat first, or install uv.
    pause
    exit /b 1
)

echo Building CaptureGPT. The GPU-enabled build includes CUDA binaries and will be large.
uv run --frozen python build.py
if errorlevel 1 (
    echo Build failed. Review the error above.
    pause
    exit /b 1
)

echo.
echo Build output: dist\CaptureGPT\CaptureGPT.exe
pause
