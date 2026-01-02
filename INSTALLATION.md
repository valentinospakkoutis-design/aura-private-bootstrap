# AURA App - Complete Installation Guide 🚀

## Prerequisites

- **Node.js** 18+ installed ([Download](https://nodejs.org/))
- **npm** or **yarn** package manager
- **Expo CLI** installed globally: `npm install -g expo-cli`
- **Git** for version control
- **iOS Simulator** (Mac) or **Android Studio** (for Android development)
- **Physical device** for testing biometrics and push notifications (recommended)

---

## 1. Install Dependencies

### Core Dependencies
```bash
npm install
```

This will install all dependencies including:
- **zustand** - State management
- **axios** - HTTP client
- **@react-native-async-storage/async-storage** - Local storage
- **expo** - Expo SDK
- **react-native** - React Native framework
- **react-native-reanimated** - Animations
- **react-native-gesture-handler** - Gesture handling
- And all other required packages

### Verify Installation
```bash
npx expo doctor
```

This will check for common issues and missing dependencies.

---

## 2. Environment Setup

### Create Environment File

Create a `.env` file in the root directory:

```bash
# Development
EXPO_PUBLIC_API_URL=http://localhost:8000

# Production (update with your Railway URL)
# EXPO_PUBLIC_API_URL=https://aura-private-bootstrap-production.up.railway.app
```

### Environment Configuration

The app uses `mobile/src/config/environment.ts` to manage environment variables:

- **Development**: Uses `http://localhost:8000` by default
- **Production**: Uses Railway URL or custom API URL

---

## 3. Start Development Server

### Start Expo Dev Server
```bash
npm start
```

Or with specific options:

```bash
# Start with cache cleared
npm start -- --clear

# Start for Android
npm run android

# Start for iOS (Mac only)
npm run ios

# Start for Web
npm run web
```

### Scan QR Code

1. Install **Expo Go** app on your device:
   - [iOS App Store](https://apps.apple.com/app/expo-go/id982107779)
   - [Google Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent)

2. Scan the QR code from the terminal or browser

3. The app will load on your device

---

## 4. Project Structure

```
aura-private-bootstrap/
├── app/                    # Expo Router screens
│   ├── _layout.js         # Root layout
│   ├── index.tsx          # Home screen
│   ├── ai-predictions.tsx # AI Predictions screen
│   └── ...
├── mobile/
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── services/     # API services, cache, etc.
│   │   ├── stores/       # Zustand stores
│   │   ├── utils/        # Utility functions
│   │   └── constants/    # Constants and theme
│   └── config/           # Configuration files
├── backend/              # FastAPI backend
├── package.json          # Dependencies
└── app.config.js        # Expo configuration
```

---

## 5. Key Features Setup

### Biometric Authentication

The app supports Face ID, Touch ID, and Fingerprint authentication:

- **iOS**: Face ID / Touch ID
- **Android**: Fingerprint / Face Recognition

Enable in Settings → Security → Biometrics

### Push Notifications

Push notifications are automatically registered on app start:

- Permissions are requested on first launch
- Token is stored securely
- Backend integration required for sending notifications

### Offline Mode & Caching

The app includes offline support with intelligent caching:

- **Cache Service**: Automatic caching of API responses
- **TTL Management**: Different cache durations per data type
- **Offline Detection**: Automatic offline mode when network unavailable

Cache can be managed in Settings → Storage & Cache

### WebSocket Support

Real-time price updates via WebSocket:

- Auto-reconnect on connection loss
- Price updates for AI predictions
- Connection status indicator

---

## 6. Building for Production

### Android Production Build

```bash
# Build APK for production
npm run build:android:production

# Check build status
npm run build:status

# Download build
npm run build:download
```

### EAS Build Configuration

The app uses EAS Build for production builds. Configuration is in `eas.json`:

- **Production**: Production API URL
- **Preview**: Preview builds for testing
- **Development**: Development builds

### Environment Variables for Build

Update `eas.json` with your production API URL:

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_URL": "https://your-railway-url.railway.app"
      }
    }
  }
}
```

---

## 7. Testing

### Test API Endpoints

```bash
# Test development endpoints
npm run test:endpoints

# Test production endpoints
npm run test:endpoints:prod
```

### Test on Physical Device

1. Connect device via USB (Android) or WiFi (iOS)
2. Enable Developer Mode
3. Run `npm run android` or `npm run ios`
4. App will install and launch automatically

---

## 8. Troubleshooting

### Common Issues

#### Metro Bundler Issues
```bash
# Clear Metro cache
npm start -- --clear

# Reset Metro bundler
npx expo start -c
```

#### Node Modules Issues
```bash
# Clean install
rm -rf node_modules
npm install

# Clear npm cache
npm cache clean --force
```

#### Android Build Issues
```bash
# Clean Android build
cd android
./gradlew clean
cd ..
```

#### iOS Build Issues (Mac only)
```bash
# Clean iOS build
cd ios
pod deintegrate
pod install
cd ..
```

#### Expo Go Connection Issues
- Ensure device and computer are on the same WiFi network
- Try using tunnel mode: `npx expo start --tunnel`
- Check firewall settings

#### Cache Issues
- Clear app cache in Settings → Storage & Cache
- Or clear AsyncStorage programmatically

### Debug Mode

Enable debug logging:

```typescript
// In development, logs are automatically enabled
// Check console for detailed logs
```

### Network Issues

If API calls fail:

1. Check API URL in `.env` file
2. Verify backend is running
3. Check network connectivity
4. Review API logs in backend

---

## 9. Development Workflow

### Code Structure

- **Components**: Reusable UI components in `mobile/src/components/`
- **Screens**: Screen components in `app/` directory
- **Hooks**: Custom hooks in `mobile/src/hooks/`
- **Services**: API and business logic in `mobile/src/services/`
- **Stores**: Global state in `mobile/src/stores/`

### Adding New Features

1. Create component in `mobile/src/components/`
2. Add screen in `app/` directory
3. Update navigation in `app/_layout.js`
4. Add API methods in `mobile/src/services/apiClient.ts`
5. Update store if needed in `mobile/src/stores/appStore.ts`

### Styling

The app uses a centralized theme system:

- Theme configuration: `mobile/src/constants/theme.ts`
- Theme context: `mobile/src/context/ThemeContext.tsx`
- Supports light/dark/auto modes

---

## 10. Production Deployment

### Railway Backend

1. Deploy backend to Railway
2. Get Railway URL
3. Update `eas.json` with production API URL
4. Build production APK: `npm run build:android:production`

### App Store / Play Store

1. Build production app with EAS Build
2. Submit to App Store (iOS) or Play Store (Android)
3. Follow platform-specific guidelines

---

## 11. Additional Resources

### Documentation

- [Expo Documentation](https://docs.expo.dev/)
- [React Native Documentation](https://reactnative.dev/)
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [Expo Router Documentation](https://docs.expo.dev/router/introduction/)

### Support

- Check `RAILWAY_FIX_SIMPLE.md` for Railway deployment issues
- Check `APP_CRASH_FIX.md` for app crash fixes
- Check `FINAL_STEPS.md` for final deployment steps

---

## 12. Quick Start Checklist

- [ ] Node.js 18+ installed
- [ ] Dependencies installed (`npm install`)
- [ ] `.env` file created with API URL
- [ ] Expo Go app installed on device
- [ ] Development server started (`npm start`)
- [ ] QR code scanned and app loaded
- [ ] Backend running and accessible
- [ ] Tested on physical device
- [ ] Biometrics tested (if available)
- [ ] Push notifications tested

---

## Need Help?

If you encounter issues:

1. Check the Troubleshooting section above
2. Review error messages in console
3. Check Expo documentation
4. Verify all prerequisites are met
5. Ensure backend is running and accessible

Happy coding! 🚀

