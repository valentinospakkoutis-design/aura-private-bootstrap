# 📱 AURA - Build APK Instructions

**Last Updated**: December 2025

---

## ⚡ Quick Start (3 Steps)

### Step 1: Login to Expo
```bash
eas login
```
Enter your Expo account credentials.  
If you don't have an account: https://expo.dev/signup

### Step 2: Build APK
```bash
npm run build:android:preview
```
Or use the script:
```bash
# Windows
.\scripts\build-apk.ps1

# Mac/Linux
chmod +x scripts/build-apk.sh
./scripts/build-apk.sh
```

### Step 3: Download APK
```bash
npm run build:download
```
Or visit: https://expo.dev/accounts/[your-account]/projects/aura/builds

---

## 📋 Available Build Commands

### Preview Build (Recommended)
```bash
npm run build:android:preview
```
- ✅ APK format
- ✅ Internal distribution
- ✅ Best for testing
- ⏱️ ~10-15 minutes

### Development Build
```bash
npm run build:android:dev
```
- Development client
- For development testing

### Production Build
```bash
npm run build:android:production
```
- Store-ready APK
- For Google Play submission

### Check Build Status
```bash
npm run build:status
```

### Download Latest Build
```bash
npm run build:download
```

---

## 🔧 Manual Build Commands

If you prefer to run EAS directly:

```bash
# Preview
eas build --platform android --profile preview

# Development
eas build --platform android --profile development

# Production
eas build --platform android --profile production
```

---

## ✅ Pre-Build Checklist

- [ ] ✅ EAS CLI installed (`eas --version`)
- [ ] ✅ Logged in to Expo (`eas login`)
- [ ] ✅ All dependencies installed (`npm install`)
- [ ] ✅ `eas.json` configured
- [ ] ✅ `app.config.js` configured
- [ ] ✅ Backend server running (for testing)

---

## 📥 After Build

### Download APK

**Option 1: Command Line**
```bash
npm run build:download
```

**Option 2: Web Dashboard**
1. Go to https://expo.dev
2. Navigate to your project
3. Click on "Builds"
4. Download the APK

### Install on Android Device

1. **Transfer APK** to device (USB, email, cloud)
2. **Enable Unknown Sources**:
   - Settings → Security → Unknown Sources
3. **Open APK file**
4. **Install**

---

## 🐛 Troubleshooting

### "Not logged in"
```bash
eas login
```

### "Build failed"
- Check logs: `eas build:view [build-id]`
- Verify all dependencies: `npm install`
- Check `app.config.js` for errors
- Ensure backend is accessible (if needed)

### "No credentials found"
```bash
eas credentials
```
This will auto-generate credentials.

### Build taking too long
- First build: 10-15 minutes (normal)
- Subsequent builds: 5-10 minutes (with cache)
- Check build queue: https://expo.dev

---

## 📊 Build Configuration

### Current Settings

**Package Name**: `com.valentinospakkoutisdesign.aura`  
**App Name**: AURA  
**Version**: 1.0.0  
**Build Type**: APK  
**Plugins**: expo-secure-store, expo-haptics

### Files

- `eas.json` - Build profiles
- `app.config.js` - App configuration
- `package.json` - Build scripts

---

## 🎯 Next Steps After Build

1. **Test APK** on Android device
2. **Verify all features** work
3. **Fix any issues**
4. **Build again** if needed
5. **Prepare for production** (if ready)

---

## 📚 Resources

- [EAS Build Docs](https://docs.expo.dev/build/introduction/)
- [Android Builds](https://docs.expo.dev/build-reference/android-builds/)
- [Expo Dashboard](https://expo.dev)

---

**Ready to build!** 🚀

Run: `eas login` then `npm run build:android:preview`

*Made with 💎 in Cyprus*

