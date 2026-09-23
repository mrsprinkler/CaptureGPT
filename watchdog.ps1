$python = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$script = Join-Path $PSScriptRoot "main.pyw"

while ($true) {
    $process = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Path -eq $python
        }

    if (-not $process) {
        Start-Process -FilePath $python -ArgumentList "`"$script`""
    }

    Start-Sleep -Milliseconds 500
}