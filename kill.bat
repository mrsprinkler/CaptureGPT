@echo off

:: Kill watchdog
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*watchdog.ps1*' } | Invoke-CimMethod -MethodName Terminate"

:: Kill only the project's Python
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq '%CD%\.venv\Scripts\pythonw.exe' } | Invoke-CimMethod -MethodName Terminate"

exit