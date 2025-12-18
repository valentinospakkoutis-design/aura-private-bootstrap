# 🔐 Credentials Setup - Manual Steps

## ⚠️ Interactive Process Required

Το `eas credentials` είναι **interactive** και χρειάζεται manual input στο terminal σου.

---

## 📋 Step-by-Step Instructions

### Run in YOUR Terminal:

```bash
eas credentials
```

### Follow These Steps:

1. **Select Platform**:
   ```
   ? Select platform ›
   ❯ Android
     iOS
   ```
   → Select: **Android**

2. **Select Action**:
   ```
   ? What would you like to do? ›
   ❯ Set up credentials for Android
     Remove credentials for Android
   ```
   → Select: **Set up credentials for Android**

3. **Select Keystore Option**:
   ```
   ? How would you like to upload your credentials? ›
   ❯ Generate a new Android Keystore
     I want to upload my own keystore
   ```
   → Select: **Generate a new Android Keystore**

4. **Confirm**:
   ```
   ? Generate a new Android Keystore? › (Y/n)
   ```
   → Type: **Y** (Yes)

---

## ✅ After Credentials Setup

Once credentials are configured, you'll see:
```
✔ Android Keystore generated and saved
```

Then run:
```bash
npm run build:android:preview
```

---

## 🚀 Alternative: Auto-Generate During Build

You can also let EAS generate credentials automatically during the first build:

```bash
npm run build:android:preview
```

When prompted:
- **Generate a new Android Keystore?** → Type: **Y**

This will:
- Generate keystore automatically
- Store it on Expo servers
- Continue with build

---

## 📝 Quick Reference

**Option 1: Setup First** (Recommended)
```bash
eas credentials
# Follow prompts → Android → Setup → Generate new
```

**Option 2: Auto-Generate During Build**
```bash
npm run build:android:preview
# When prompted → Generate new keystore → Y
```

---

## 🔍 Verify Credentials

After setup, check:
```bash
eas credentials --platform android
```

---

**Status**: ⏳ Waiting for credentials setup  
**Action**: Run `eas credentials` in your terminal

*Made with 💎 in Cyprus*

