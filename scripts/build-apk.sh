#!/bin/bash
# AURA APK Build Script
# Automates the APK build process

echo "🚀 AURA APK Build Script"
echo ""

# Check if logged in
echo "Checking Expo login status..."
if ! eas whoami &>/dev/null; then
    echo "❌ Not logged in to Expo"
    echo ""
    echo "Please login first:"
    echo "  eas login"
    echo ""
    echo "Or create account at: https://expo.dev/signup"
    exit 1
fi

echo "✅ Logged in to Expo"
echo ""

# Ask for build profile
echo "Select build profile:"
echo "  1. Preview (Recommended for testing)"
echo "  2. Development"
echo "  3. Production"
echo ""
read -p "Enter choice (1-3): " profileChoice

case $profileChoice in
    1) profile="preview" ;;
    2) profile="development" ;;
    3) profile="production" ;;
    *) 
        echo "Invalid choice, using preview"
        profile="preview"
        ;;
esac

echo ""
echo "📦 Building APK with profile: $profile"
echo "This may take 10-15 minutes..."
echo ""

# Build
eas build --platform android --profile $profile

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build completed successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Check build status: npm run build:status"
    echo "  2. Download APK: npm run build:download"
    echo "  3. Or visit: https://expo.dev"
else
    echo ""
    echo "❌ Build failed. Check the logs above."
    exit 1
endif

