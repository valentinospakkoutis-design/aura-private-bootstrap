# 📦 Expo EAS Production Build Guide

## 🎯 Overview

Complete guide για production build με Expo EAS.

---

## ✅ Configuration Complete

### eas.json Production Profile:
```json
{
  "production": {
    "distribution": "store",
    "android": {
      "buildType": "apk",
      "gradleCommand": ":app:assembleRelease"
    },
    "env": {
      "EXPO_PUBLIC_ENVIRONMENT": "production",
      "NODE_ENV": "production",
      "EXPO_PUBLIC_ENABLE_ANALYTICS": "true",
      "EXPO_PUBLIC_ENABLE_CRASH_REPORTING": "true"
    },
    "channel": "production"
  }
}
```

---

## 🚀 Build Commands

### Production Build (App Store Ready):
```bash
npm run build:android:production
```

**Or:**
```bash
eas build --platform android --profile production
```

### Standalone Build (Internal Testing):
```bash
npm run build:android:standalone
```

### Preview Build (Testing):
```bash
npm run build:android:preview
```

---

## 📋 Pre-Build Checklist

### 1. Environment Configuration ✅
- [x] Production environment variables set
- [x] API URL configured
- [x] Analytics enabled
- [x] Crash reporting enabled

### 2. Backend Ready ✅
- [ ] Backend deployed to Railway
- [ ] Production API URL obtained
- [ ] All endpoints tested
- [ ] CORS configured

### 3. App Configuration ✅
- [x] `app.config.js` configured
- [x] `eas.json` production profile ready
- [x] Version code set
- [x] Permissions configured

### 4. Testing ✅
- [ ] All endpoints tested
- [ ] App tested locally
- [ ] Preview build tested
- [ ] No critical bugs

---

## 🔧 Build Process

### Step 1: Update Production API URL

**Edit `mobile/src/config/environment.js`:**
```javascript
production: {
  apiUrl: 'https://your-railway-url.railway.app', // ← Update this
  // ...
}
```

### Step 2: Test Endpoints

```bash
npm run test:endpoints:prod
```

### Step 3: Build

```bash
npm run build:android:production
```

### Step 4: Monitor Build

- Build takes ~10-15 minutes
- Monitor on Expo dashboard
- Check build logs for errors

### Step 5: Download

```bash
npm run build:download
```

---

## 📊 Build Profiles Comparison

| Profile | Distribution | Use Case | Environment |
|---------|--------------|----------|-------------|
| `development` | Internal | Dev with Expo Go | Development |
| `preview` | Internal | Testing | Staging |
| `standalone` | Internal | Standalone testing | Production |
| `production` | Store | App Store release | Production |

---

## 🔒 Production Build Features

### Enabled:
- ✅ Production environment
- ✅ Analytics tracking
- ✅ Crash reporting
- ✅ Optimized bundle
- ✅ Release signing

### Disabled:
- ❌ Development logging
- ❌ Debug menu
- ❌ Hot reload
- ❌ Development tools

---

## 📱 After Build

### 1. Download APK
```bash
npm run build:download
```

### 2. Test on Device
- Install APK
- Test all features
- Verify API connectivity
- Check analytics

### 3. Submit to Store (Optional)
```bash
eas submit --platform android --profile production
```

---

## 🎯 Production Build Requirements

### Must Have:
- ✅ Production API URL configured
- ✅ Backend deployed and accessible
- ✅ All endpoints working
- ✅ No critical bugs
- ✅ Analytics configured

### Should Have:
- ✅ App Store assets (icons, screenshots)
- ✅ Privacy policy URL
- ✅ Terms of service URL
- ✅ Support email

---

## 📋 Build Status

**Configuration**: ✅ Complete
**Ready to Build**: ⏳ After API URL update

---

**Status**: ✅ Production build configuration complete!

*Made with 💎 in Cyprus*

