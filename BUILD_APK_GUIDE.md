# 📱 AURA - Build APK Guide

**Last Updated**: December 2025

---

## 🚀 Quick Start

Για να φτιάξεις APK για Android, ακολούθησε αυτά τα βήματα:

### 1. Login στο Expo

```bash
eas login
```

Θα σου ζητήσει:
- Email ή username
- Password

Αν δεν έχεις account, δημιούργησε ένα εδώ: https://expo.dev/signup

---

### 2. Build APK (Preview - για testing)

```bash
eas build --platform android --profile preview
```

Αυτό θα:
- Φτιάξει APK file
- Το upload στο Expo servers
- Σου δώσει download link

**Χρόνος**: ~10-15 λεπτά

---

### 3. Build APK (Production)

```bash
eas build --platform android --profile production
```

**Σημείωση**: Production build χρειάζεται signing keys (θα δημιουργηθούν αυτόματα)

---

## 📋 Build Profiles

Έχουμε 3 profiles στο `eas.json`:

### Development
```bash
eas build --platform android --profile development
```
- Development client
- APK format
- Internal distribution

### Preview (Recommended για πρώτο build)
```bash
eas build --platform android --profile preview
```
- APK format
- Internal distribution
- Καλό για testing

### Production
```bash
eas build --platform android --profile production
```
- APK format
- Store distribution
- Ready για Google Play

---

## 🔧 Configuration

### eas.json
Το `eas.json` είναι ήδη configured με:
- ✅ Android APK builds
- ✅ Development, Preview, Production profiles
- ✅ Correct build types

### app.config.js
Το `app.config.js` έχει:
- ✅ Package name: `com.valentinospakkoutisdesign.aura`
- ✅ App name: AURA
- ✅ Version: 1.0.0
- ✅ Plugins: expo-secure-store, expo-haptics

---

## 📥 Download APK

Μετά το build:

1. **Check build status**:
   ```bash
   eas build:list
   ```

2. **Download APK**:
   - Πήγαινε στο https://expo.dev/accounts/[your-account]/projects/aura/builds
   - Κάνε click στο build
   - Download το APK

Ή από command line:
```bash
eas build:download
```

---

## 🛠️ Troubleshooting

### "An Expo user account is required"
```bash
eas login
```

### "Build failed"
- Ελέγξτε τα logs: `eas build:view`
- Βεβαιωθείτε ότι όλα τα dependencies είναι installed
- Ελέγξτε το `app.config.js` για errors

### "No credentials found"
```bash
eas credentials
```
Αυτό θα setup τα credentials αυτόματα.

---

## 📱 Install APK

Μετά το download:

1. **Transfer στο Android device** (USB, email, cloud)
2. **Enable "Install from unknown sources"**:
   - Settings → Security → Unknown Sources
3. **Open το APK file**
4. **Install**

---

## ✅ Pre-Build Checklist

- [ ] Login στο Expo (`eas login`)
- [ ] All dependencies installed (`npm install`)
- [ ] `eas.json` configured ✅
- [ ] `app.config.js` configured ✅
- [ ] Backend server running (για testing)
- [ ] Environment variables set (αν χρειάζεται)

---

## 🎯 Next Steps

Μετά το πρώτο build:

1. **Test το APK** στο device
2. **Fix any issues**
3. **Build again** αν χρειάζεται
4. **Prepare για Google Play** (production build)

---

## 📚 Resources

- [EAS Build Documentation](https://docs.expo.dev/build/introduction/)
- [Android Build Guide](https://docs.expo.dev/build-reference/android-builds/)
- [Expo Account](https://expo.dev)

---

## 💡 Tips

1. **Preview build πρώτα** - Γρηγορότερο και καλύτερο για testing
2. **Check build logs** - Αν κάτι πάει στραβά
3. **Test thoroughly** - Πριν το production build
4. **Keep credentials safe** - Μην commit credentials

---

**Status**: ✅ Ready to Build  
**Last Updated**: December 2025

*Made with 💎 in Cyprus*

