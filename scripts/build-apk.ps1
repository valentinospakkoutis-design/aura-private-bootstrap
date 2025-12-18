# AURA APK Build Script
# Automates the APK build process

Write-Host "🚀 AURA APK Build Script" -ForegroundColor Cyan
Write-Host ""

# Check if logged in
Write-Host "Checking Expo login status..." -ForegroundColor Yellow
$loginStatus = eas whoami 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not logged in to Expo" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please login first:" -ForegroundColor Yellow
    Write-Host "  eas login" -ForegroundColor White
    Write-Host ""
    Write-Host "Or create account at: https://expo.dev/signup" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Logged in to Expo" -ForegroundColor Green
Write-Host ""

# Ask for build profile
Write-Host "Select build profile:" -ForegroundColor Yellow
Write-Host "  1. Preview (Recommended for testing)" -ForegroundColor White
Write-Host "  2. Development" -ForegroundColor White
Write-Host "  3. Production" -ForegroundColor White
Write-Host ""
$profileChoice = Read-Host "Enter choice (1-3)"

switch ($profileChoice) {
    "1" { $profile = "preview" }
    "2" { $profile = "development" }
    "3" { $profile = "production" }
    default { 
        Write-Host "Invalid choice, using preview" -ForegroundColor Yellow
        $profile = "preview"
    }
}

Write-Host ""
Write-Host "📦 Building APK with profile: $profile" -ForegroundColor Cyan
Write-Host "This may take 10-15 minutes..." -ForegroundColor Yellow
Write-Host ""

# Build
eas build --platform android --profile $profile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Check build status: npm run build:status" -ForegroundColor White
    Write-Host "  2. Download APK: npm run build:download" -ForegroundColor White
    Write-Host "  3. Or visit: https://expo.dev" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Build failed. Check the logs above." -ForegroundColor Red
    exit 1
}

