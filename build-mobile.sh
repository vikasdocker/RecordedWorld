#!/bin/bash
# Build script for Recorded World Mobile App

echo "========================================"
echo " Recorded World - Mobile Build"
echo "========================================"

cd mobile-app

echo ""
echo "Installing dependencies..."
npm install

echo ""
echo "Starting Expo development server..."
echo "Scan the QR code with Expo Go app on your phone"
echo ""
echo "For production builds:"
echo "  npm run build:android  # APK"
echo "  npm run build:ios      # IPA"
echo ""
npx expo start
