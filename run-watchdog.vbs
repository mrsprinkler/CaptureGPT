Set shell = CreateObject("WScript.Shell")

script = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\watchdog.ps1"

shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & script & """ -Watchdog", 0, False