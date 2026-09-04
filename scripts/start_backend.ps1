$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location "$projectRoot\backend"
if (!(Test-Path .\.venv\Scripts\python.exe)) { throw 'Run scripts/setup_windows.ps1 first.' }
& .\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8001
