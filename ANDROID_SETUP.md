# 📱 Android Setup Guide

## ⚠️ ADB Error Explanation

Το error `adb executable doesn't seem to work` εμφανίζεται μόνο για **local Android development** (όταν τρέχεις `expo start --android`).

**Για EAS Build (cloud build)**: Δεν χρειάζεται adb! Το build τρέχει στο cloud.

---

## 🚀 EAS Build (Recommended - No ADB Needed)

Το EAS build **δεν χρειάζεται** Android Studio ή adb:

```bash
npm run build:android:preview
```

Αυτό:
- ✅ Τρέχει στο cloud (Expo servers)
- ✅ Δεν χρειάζεται Android Studio
- ✅ Δεν χρειάζεται adb
- ✅ Δεν χρειάζεται Android SDK

---

## 💻 Local Android Development (Optional)

Αν θέλεις να τρέξεις την app **locally** στο Android emulator/device:

### Option 1: Android Studio (Full Setup)

1. **Install Android Studio**:
   - Download: https://developer.android.com/studio
   - Install with Android SDK

2. **Set Environment Variables**:
   ```powershell
   # Windows PowerShell
   $env:ANDROID_HOME = "C:\Users\$env:USERNAME\AppData\Local\Android\Sdk"
   $env:PATH += ";$env:ANDROID_HOME\platform-tools"
   ```

3. **Verify**:
   ```bash
   adb version
   ```

### Option 2: Use Expo Go (Easier)

Για development, μπορείς να χρησιμοποιήσεις Expo Go app:

```bash
npm start
```

Στη συνέχεια:
- Scan QR code με Expo Go app (Android/iOS)
- No Android Studio needed!

---

## 🎯 For APK Build (Current Goal)

**You don't need ADB!**

Just run:
```bash
npm run build:android:preview
```

When prompted:
- **Generate a new Android Keystore?** → Type: **Y**

The build runs on Expo cloud - no local Android setup needed!

---

## ✅ Current Status

- ✅ EAS Build: Ready (no adb needed)
- ✅ Config: Fixed
- ✅ Dependencies: Updated
- ✅ expo-doctor: All checks pass
- ⏳ Credentials: Need setup (interactive)

---

## 📋 Quick Reference

**For APK Build** (what you need now):
```bash
npm run build:android:preview
# No Android Studio needed!
```

**For Local Development** (optional):
- Use Expo Go app (easiest)
- Or install Android Studio (if you want emulator)

---

**Status**: ✅ Ready for EAS Build  
**ADB Error**: Not relevant for cloud builds

*Made with 💎 in Cyprus*

