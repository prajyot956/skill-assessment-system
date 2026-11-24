# Windows PowerShell setup. Run from the project root:  .\setup.ps1
# If scripts are blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"

Write-Host "Checking prerequisites..." -ForegroundColor Cyan
foreach ($tool in @("python", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool was not found. Install Python 3.11+ and Node.js 20+ first."
    }
}

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from .env.example" }

Write-Host "Setting up backend..." -ForegroundColor Cyan
Push-Location backend
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FLASK_APP = "run.py"
& .\.venv\Scripts\flask.exe db upgrade
& .\.venv\Scripts\flask.exe seed
Pop-Location

Write-Host "Setting up frontend..." -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location

Write-Host "`nDone. Start the app in two PowerShell windows:" -ForegroundColor Green
Write-Host "  1) cd backend; .\.venv\Scripts\python.exe run.py"
Write-Host "  2) cd frontend; npm run dev      then open http://localhost:5173"
