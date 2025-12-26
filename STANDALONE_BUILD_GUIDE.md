# 📱 Standalone Android Build Guide

## 🎯 Goal: Standalone APK για Android Device

Αυτός ο οδηγός εξηγεί πώς να δημιουργήσεις ένα **standalone APK** που:
- ✅ Μπορεί να εγκατασταθεί απευθείας στο Android device
- ✅ **Δεν χρειάζεται** υπολογιστή για να λειτουργήσει
- ✅ **Δεν χρειάζεται** Expo Go
- ✅ Λειτουργεί **100% ανεξάρτητα**

---

## ✅ Configuration Complete

### 1. **app.config.js** ✅
- Production environment detection
- API URL configuration
- Android permissions
- Version code

### 2. **eas.json** ✅
- New `standalone` profile για standalone builds
- Production environment variables
- APK build type

### 3. **environment.js** ✅
- Smart API URL detection
- Production fallbacks
- No hardcoded localhost URLs in production

### 4. **package.json** ✅
- New build script: `build:android:standalone`

---

## 🚀 Build Steps

### Step 1: Configure Production API URL

**Είναι σημαντικό!** Το app χρειάζεται production API URL.

**Option A: Via Environment Variable (Recommended)**

Δημιούργησε `.env.production` file:
```bash
EXPO_PUBLIC_ENVIRONMENT=production
EXPO_PUBLIC_API_URL=https://your-production-api-url.com
EXPO_PUBLIC_ENABLE_ANALYTICS=true
EXPO_PUBLIC_ENABLE_CRASH_REPORTING=true
```

**Option B: Update app.config.js**

Edit `app.config.js` line 41:
```javascript
apiUrl: process.env.EXPO_PUBLIC_API_URL || (process.env.NODE_ENV === 'production' ? 'https://your-production-api-url.com' : undefined),
```

**Option C: Update environment.js**

Edit `mobile/src/config/environment.js` line 41:
```javascript
production: {
  apiUrl: 'https://your-production-api-url.com', // YOUR PRODUCTION API URL
  // ...
}
```

---

### Step 2: Build Standalone APK

```bash
npm run build:android:standalone
```

**Ή:**

```bash
eas build --platform android --profile standalone
```

---

### Step 3: Download APK

Μετά το build:

```bash
npm run build:download
```

**Ή:**

```bash
eas build:download
```

---

### Step 4: Install on Android Device

1. **Transfer APK** στο Android device (USB, email, cloud)
2. **Enable Unknown Sources**:
   - Settings → Security → Install Unknown Apps
   - Enable για το app που θα χρησιμοποιήσεις (Browser, Files, etc.)
3. **Install APK**:
   - Tap το APK file
   - Follow installation prompts
4. **Open App**:
   - Το app θα λειτουργήσει standalone!

---

## 🔧 Configuration Details

### Environment Detection

Το app **αυτόματα** ανιχνεύει το environment:

1. **Development**: Αν τρέχει με `expo start` ή `npm start`
2. **Production**: Αν είναι built APK (standalone)

### API URL Priority

Το app χρησιμοποιεί API URL με αυτή τη σειρά:

1. `EXPO_PUBLIC_API_URL` environment variable
2. `app.config.js` extra.apiUrl
3. `environment.js` production.apiUrl
4. Fallback: `https://api.aura.com`

---

## ⚠️ Important Notes

### 1. Backend API Required

Το standalone app **χρειάζεται** production backend API:
- ✅ Πρέπει να είναι accessible από internet
- ✅ Πρέπει να έχει HTTPS (secure)
- ✅ Πρέπει να έχει CORS configured

### 2. No Localhost URLs

Στο production build:
- ❌ Δεν χρησιμοποιείται `localhost`
- ❌ Δεν χρησιμοποιείται local IP
- ✅ Μόνο production API URL

### 3. Offline Mode

Το app έχει offline detection:
- Shows offline banner αν δεν υπάρχει internet
- Fallback data αν το API fails
- Error handling για network issues

---

## 📋 Pre-Build Checklist

- [ ] Production API URL configured
- [ ] Backend API is running and accessible
- [ ] HTTPS enabled στο backend
- [ ] CORS configured στο backend
- [ ] Environment variables set (if using .env)
- [ ] All dependencies installed (`npm install`)
- [ ] EAS account logged in (`eas login`)

---

## 🧪 Testing Standalone Build

### Test 1: Install & Launch
- [ ] APK installs successfully
- [ ] App opens without errors
- [ ] No Expo Go required

### Test 2: Network Connectivity
- [ ] App connects to production API
- [ ] Data loads correctly
- [ ] Offline mode works

### Test 3: Features
- [ ] All screens work
- [ ] Navigation works
- [ ] API calls succeed
- [ ] Theme toggle works
- [ ] Haptics work (on physical device)

---

## 🔍 Troubleshooting

### Issue: App can't connect to API

**Solution:**
1. Check production API URL is correct
2. Verify backend is accessible from internet
3. Check CORS settings on backend
4. Verify HTTPS is enabled

### Issue: App shows development mode

**Solution:**
1. Check `EXPO_PUBLIC_ENVIRONMENT=production` is set
2. Verify `NODE_ENV=production` in build
3. Check `app.config.js` environment detection

### Issue: Build fails

**Solution:**
1. Run `npx expo-doctor` to check for issues
2. Verify all dependencies are installed
3. Check EAS credentials are set
4. Review build logs on Expo dashboard

---

## 📊 Build Profiles

| Profile | Use Case | Distribution |
|---------|----------|--------------|
| `development` | Development with Expo Go | Internal |
| `preview` | Testing builds | Internal |
| `standalone` | **Standalone APK (this guide)** | Internal |
| `production` | App Store release | Store |

---

## 🎯 Quick Start

1. **Set Production API URL**:
   ```bash
   # Edit mobile/src/config/environment.js
   # Set production.apiUrl to your API URL
   ```

2. **Build**:
   ```bash
   npm run build:android:standalone
   ```

3. **Download**:
   ```bash
   npm run build:download
   ```

4. **Install** on Android device

5. **Done!** 🎉

---

## 📚 Related Documentation

- `docs/DEPLOYMENT.md` - Full deployment guide
- `BUILD_APK_GUIDE.md` - General APK build guide
- `APK_DOWNLOAD_GUIDE.md` - Download instructions

---

**Status**: ✅ Ready for standalone build!

*Made with 💎 in Cyprus*

