@echo off

where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo Installing dependencies...
uv sync

echo.
for /f "delims=" %%K in ('powershell -NoProfile -Command "$s=Read-Host ''Enter your OpenAI API key'' -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"') do set "OPENAI_API_KEY=%%K"

> .env echo OPENAI_API_KEY=%OPENAI_API_KEY%

echo.
echo API key saved to .env
pause