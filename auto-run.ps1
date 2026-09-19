# Recorded World - Auto Run Script (Phase 2)
# Starts all services including WebSocket server

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Recorded World - Starting Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Start WebSocket server
Write-Host "`n[1/3] Starting WebSocket server..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.websocket_server:app --host 0.0.0.0 --port 8765" -WindowStyle Normal

Start-Sleep -Seconds 2

# Start REST API server
Write-Host "[2/3] Starting REST API server..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.main:app --reload --port 8000" -WindowStyle Normal

Start-Sleep -Seconds 3

# Start PC client
Write-Host "[3/3] Starting PC client..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$root\pc-client'; npm run dev" -WindowStyle Normal

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nREST API:  http://localhost:8000" -ForegroundColor White
Write-Host "WebSocket: ws://localhost:8765" -ForegroundColor White
Write-Host "PC Client: http://localhost:3000" -ForegroundColor White
Write-Host "`nMobile app: cd mobile-app && npm start" -ForegroundColor Gray
