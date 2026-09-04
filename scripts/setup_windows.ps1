$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location "$projectRoot\backend"
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location
Push-Location "$projectRoot\frontend"
npm ci
Pop-Location
Write-Host 'Setup complete. Run scripts/start_backend.ps1 and scripts/start_frontend.ps1 in separate terminals.'
