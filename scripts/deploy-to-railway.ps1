# Railway Deployment Script
# This script helps you deploy the backend to Railway

Write-Host "=== Railway Deployment Helper ===" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
$railwayInstalled = Get-Command railway -ErrorAction SilentlyContinue

if (-not $railwayInstalled) {
    Write-Host "⚠️  Railway CLI not found!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Install Railway CLI:" -ForegroundColor Cyan
    Write-Host "  npm install -g @railway/cli" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use the web interface:" -ForegroundColor Cyan
    Write-Host "  1. Go to https://railway.app" -ForegroundColor White
    Write-Host "  2. Sign up with GitHub" -ForegroundColor White
    Write-Host "  3. New Project → Deploy from GitHub repo" -ForegroundColor White
    Write-Host "  4. Select your repository" -ForegroundColor White
    Write-Host "  5. Set Root Directory: backend" -ForegroundColor White
    Write-Host "  6. Set Start Command: uvicorn main:app --host 0.0.0.0 --port `$PORT" -ForegroundColor White
    Write-Host ""
    exit 0
}

Write-Host "✓ Railway CLI found" -ForegroundColor Green
Write-Host ""

# Check if logged in
Write-Host "Checking Railway login status..." -ForegroundColor Cyan
$loginStatus = railway whoami 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Not logged in to Railway" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please login:" -ForegroundColor Cyan
    Write-Host "  railway login" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✓ Logged in to Railway" -ForegroundColor Green
Write-Host ""

# Check if in a Railway project
Write-Host "Checking Railway project..." -ForegroundColor Cyan
$projectInfo = railway status 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Not in a Railway project" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  1. Link existing project: railway link" -ForegroundColor White
    Write-Host "  2. Create new project: railway init" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✓ Railway project found" -ForegroundColor Green
Write-Host ""

# Show deployment info
Write-Host "=== Deployment Information ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend directory: backend/" -ForegroundColor White
Write-Host "Start command: uvicorn main:app --host 0.0.0.0 --port `$PORT" -ForegroundColor White
Write-Host ""

# Get service URL
Write-Host "Getting service URL..." -ForegroundColor Cyan
$serviceUrl = railway domain 2>&1

if ($LASTEXITCODE -eq 0 -and $serviceUrl) {
    Write-Host "✓ Service URL: $serviceUrl" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Next Steps ===" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Update eas.json with this URL:" -ForegroundColor White
    Write-Host "   EXPO_PUBLIC_API_URL: $serviceUrl" -ForegroundColor Cyan
    Write-Host "   EXPO_PUBLIC_WS_URL: wss://$serviceUrl/ws" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "2. Rebuild mobile app:" -ForegroundColor White
    Write-Host "   eas build --profile production --platform android" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "⚠️  Could not get service URL" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Get URL from Railway dashboard:" -ForegroundColor Cyan
    Write-Host "  https://railway.app/dashboard" -ForegroundColor White
    Write-Host ""
}

Write-Host "=== Deployment Commands ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Deploy to Railway:" -ForegroundColor White
Write-Host "  railway up" -ForegroundColor Cyan
Write-Host ""
Write-Host "View logs:" -ForegroundColor White
Write-Host "  railway logs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Open dashboard:" -ForegroundColor White
Write-Host "  railway open" -ForegroundColor Cyan
Write-Host ""

