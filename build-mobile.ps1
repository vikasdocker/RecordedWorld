# Build script for Recorded World Mobile App (Windows)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Recorded World - Mobile Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Set-Location "$PSScriptRoot\mobile-app"

Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
npm install

Write-Host "`nStarting Expo development server..." -ForegroundColor Green
Write-Host "Scan the QR code with Expo Go app on your phone" -ForegroundColor White
Write-Host ""
Write-Host "For production builds, run:" -ForegroundColor Yellow
Write-Host "  npx eas build --platform android  # APK" -ForegroundColor Gray
Write-Host "  npx eas build --platform ios      # IPA" -ForegroundColor Gray
Write-Host ""

npx expo start
