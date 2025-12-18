# 🔐 Setup Credentials - Execute Now

## ⚠️ Interactive Command Required

Το `eas credentials` είναι **interactive** και πρέπει να το τρέξεις **manually** στο terminal σου.

---

## 🚀 Quick Setup (2 Options)

### Option 1: Setup Credentials First (Recommended)

**Run in YOUR terminal:**
```bash
eas credentials --platform android
```

**Follow prompts:**
1. **Which build profile?** → Select: `preview` (or press Enter for default)
2. **What would you like to do?** → Select: `Set up credentials for Android`
3. **How to upload?** → Select: `Generate a new Android Keystore`
4. **Confirm** → Type: `Y`

---

### Option 2: Auto-Generate During Build

**Run in YOUR terminal:**
```bash
npm run build:android:preview
```

**When prompted:**
- **Generate a new Android Keystore?** → Type: `Y`

This will automatically:
- Generate keystore
- Store on Expo servers
- Continue with build

---

## 📋 Detailed Steps (Option 1)

### Step 1: Run Command
```bash
eas credentials --platform android
```

### Step 2: Select Build Profile
```
? Which build profile do you want to configure? ›
❯ preview
  development
  production
```
→ Press **Enter** (preview is default)

### Step 3: Select Action
```
? What would you like to do? ›
❯ Set up credentials for Android
  Remove credentials for Android
```
→ Press **Enter** (Set up is default)

### Step 4: Select Keystore Option
```
? How would you like to upload your credentials? ›
❯ Generate a new Android Keystore
  I want to upload my own keystore
```
→ Press **Enter** (Generate new is default)

### Step 5: Confirm
```
? Generate a new Android Keystore? › (Y/n)
```
→ Type: **Y** and press Enter

---

## ✅ Success Message

After setup, you'll see:
```
✔ Android Keystore generated and saved
✔ Credentials configured for Android
```

---

## 🚀 After Credentials Setup

Once credentials are configured, run:

```bash
npm run build:android:preview
```

The build will:
- Use stored credentials automatically
- Build APK on Expo servers
- Take ~10-15 minutes
- Provide download link

---

## 🔍 Verify Setup

Check credentials:
```bash
eas credentials --platform android
```

Should show your keystore information.

---

## 📝 Quick Reference

**Easiest way:**
```bash
# Just run build - it will prompt for keystore
npm run build:android:preview
# When asked → Type: Y
```

**Or setup first:**
```bash
eas credentials --platform android
# Follow prompts → All defaults (just press Enter)
```

---

**Status**: ⏳ Waiting for credentials setup  
**Action**: Run `eas credentials --platform android` in your terminal

*Made with 💎 in Cyprus*

