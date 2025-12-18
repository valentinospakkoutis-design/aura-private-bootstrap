# 🚀 Expo Start Guide - Run AURA Locally

## ✅ Project Status: Ready for Expo!

Το project είναι έτοιμο για local development! 🎉

---

## 📋 Quick Start

### Step 1: Install Dependencies (if needed)

```bash
npm install
```

### Step 2: Start Expo Development Server

```bash
npm start
```

Ή:

```bash
npx expo start
```

---

## 📱 Run on Device/Emulator

### Option 1: Expo Go App (Easiest)

1. **Install Expo Go**:
   - Android: https://play.google.com/store/apps/details?id=host.exp.exponent
   - iOS: https://apps.apple.com/app/expo-go/id982107779

2. **Start Expo**:
   ```bash
   npm start
   ```

3. **Scan QR Code**:
   - Android: Open Expo Go → Scan QR code
   - iOS: Open Camera app → Scan QR code

### Option 2: Android Emulator

```bash
npm run android
```

**Note**: Requires Android Studio + emulator running

### Option 3: iOS Simulator (Mac only)

```bash
npm run ios
```

### Option 4: Web Browser

```bash
npm run web
```

---

## 🔧 Available Commands

| Command | Description |
|---------|-------------|
| `npm start` | Start Expo dev server |
| `npm run android` | Run on Android emulator |
| `npm run ios` | Run on iOS simulator (Mac only) |
| `npm run web` | Run in web browser |

---

## ⚙️ Environment Variables (Optional)

Αν χρειάζεσαι environment variables, δημιούργησε `.env` file:

```bash
# Copy template
cp env.template .env
```

Edit `.env`:
```
EXPO_PUBLIC_ENVIRONMENT=development
EXPO_PUBLIC_API_URL=http://192.168.178.97:8000
EXPO_PUBLIC_ENABLE_ANALYTICS=false
EXPO_PUBLIC_ENABLE_CRASH_REPORTING=false
```

---

## 🎯 What Happens When You Start

1. **Metro Bundler** starts
2. **QR Code** appears in terminal
3. **Development server** runs on local network
4. **Hot reload** enabled (auto-refresh on code changes)

---

## 📊 Current Configuration

- ✅ **Expo SDK**: 52.0.48
- ✅ **React Native**: 0.76.9
- ✅ **Expo Router**: 4.0.22
- ✅ **Config**: Valid (expo-doctor passed)
- ✅ **Plugins**: Configured
- ✅ **EAS Project**: Set

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Kill process on port 8081
npx kill-port 8081
```

### Clear Cache

```bash
npx expo start --clear
```

### Reset Metro Cache

```bash
npm start -- --reset-cache
```

### Network Issues

- Make sure phone and computer are on **same WiFi network**
- Try **tunnel mode**:
  ```bash
  npx expo start --tunnel
  ```

---

## 🎨 Development Features

- ✅ **Hot Reload**: Auto-refresh on save
- ✅ **Fast Refresh**: React component updates
- ✅ **Error Overlay**: See errors in app
- ✅ **Debug Menu**: Shake device or press `Cmd+D` (iOS) / `Cmd+M` (Android)

---

## 📱 Testing Checklist

- [ ] App opens in Expo Go
- [ ] Navigation works
- [ ] API calls work (if backend running)
- [ ] Dark mode toggle works
- [ ] Haptics work (on physical device)
- [ ] Offline banner appears when offline
- [ ] Error boundary catches errors

---

## 🚀 Next Steps

1. **Start Expo**:
   ```bash
   npm start
   ```

2. **Scan QR** with Expo Go app

3. **Start developing!**

---

## 📚 Useful Links

- **Expo Docs**: https://docs.expo.dev/
- **Expo Router**: https://docs.expo.dev/router/introduction/
- **React Native**: https://reactnative.dev/

---

**Ready to start! Run `npm start` and scan the QR code! 🎉**

*Made with 💎 in Cyprus*

