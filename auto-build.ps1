# Recorded World - Auto Build Script
# Runs automatically to build all components

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Recorded World - Auto Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Install Python dependencies
Write-Host "`n[1/3] Installing backend dependencies..." -ForegroundColor Yellow
Push-Location "$root\backend"
pip install -r requirements.txt --quiet 2>$null
if ($?) { Write-Host "  Backend dependencies installed" -ForegroundColor Green }
else { Write-Host "  Warning: Some dependencies may need manual install" -ForegroundColor Yellow }
Pop-Location

# Install PC Client dependencies
Write-Host "`n[2/3] Installing PC client dependencies..." -ForegroundColor Yellow
Push-Location "$root\pc-client"
npm install --silent 2>$null
if ($?) { Write-Host "  PC client dependencies installed" -ForegroundColor Green }
else { Write-Host "  Warning: npm install failed" -ForegroundColor Yellow }
Pop-Location

# Install Mobile App dependencies
Write-Host "`n[3/3] Installing mobile app dependencies..." -ForegroundColor Yellow
Push-Location "$root\mobile-app"
npm install --silent 2>$null
if ($?) { Write-Host "  Mobile app dependencies installed" -ForegroundColor Green }
else { Write-Host "  Warning: npm install failed" -ForegroundColor Yellow }
Pop-Location

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nTo start the project:" -ForegroundColor White
Write-Host "  1. Backend:  cd backend; python -m uvicorn app.main:app --reload" -ForegroundColor Gray
Write-Host "  2. PC Client: cd pc-client; npm run dev" -ForegroundColor Gray
Write-Host "  3. Mobile:   cd mobile-app; npm start" -ForegroundColor Gray
