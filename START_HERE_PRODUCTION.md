# 🎯 Start Here: Production Setup για Αρχάριους

## 📖 Τι χρειάζεται;

Για να λειτουργήσει το standalone APK **χωρίς υπολογιστή**, χρειάζεσαι:

1. ✅ **Backend online** (στο internet, όχι localhost)
2. ✅ **Production API URL** (η διεύθυνση του backend)

---

## 🎯 Δύο Επιλογές

### Option 1: Testing Mode (Τώρα) ⚡

**Για testing χωρίς production backend:**

✅ **Έτοιμο!** Το configuration είναι ήδη setup για testing.

**Πώς λειτουργεί:**
- Χρησιμοποιεί local IP (`192.168.178.97:8000`)
- Λειτουργεί **μόνο** αν:
  - Το backend τρέχει στον υπολογιστή σου
  - Το Android device είναι στο **ίδιο WiFi**
  - Το backend είναι accessible

**Build command:**
```bash
npm run build:android:standalone
```

**Limitations:**
- ❌ Δεν λειτουργεί αν δεν είσαι στο ίδιο WiFi
- ❌ Δεν λειτουργεί αν ο υπολογιστής είναι off
- ✅ Καλό για testing

---

### Option 2: Production Mode (Μετά) 🚀

**Για πραγματικό standalone (χωρίς υπολογιστή):**

**Χρειάζεσαι:**
1. Deploy backend στο Railway/Render (10 λεπτά)
2. Get production API URL
3. Update configuration

**Οδηγός**: Δες `QUICK_DEPLOY_BACKEND.md`

---

## 🚀 Quick Start: Testing Mode

### Step 1: Start Backend Locally

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Step 2: Build Standalone APK

```bash
npm run build:android:standalone
```

### Step 3: Install on Device

1. Download APK
2. Install on Android device
3. **Important**: Device must be on **same WiFi** as computer

### Step 4: Test

- App should connect to backend
- Data should load
- All features should work

---

## 📚 Documentation

### Για Testing (Τώρα):
- ✅ **Configuration ready** - Just build!
- ✅ Works on same WiFi
- ✅ Good for initial testing

### Για Production (Μετά):
- 📖 `QUICK_DEPLOY_BACKEND.md` - Deploy backend guide
- 📖 `SIMPLE_PRODUCTION_SETUP.md` - Simple explanation
- 📖 `API_URL_CONFIGURATION.md` - API URL setup

---

## 🎯 Recommended Path

1. **Now**: Test with local backend (same WiFi)
2. **Later**: Deploy to Railway (10 minutes)
3. **Then**: Update API URL and rebuild

---

## ✅ Current Status

**Configuration**: ✅ Ready for testing mode

**Next Step**: 
- Build APK: `npm run build:android:standalone`
- Test on device (same WiFi)

**For Production**: Follow `QUICK_DEPLOY_BACKEND.md` when ready

---

**Don't worry!** Μπορείς να test τώρα και να deploy production αργότερα! 🚀

*Made with 💎 in Cyprus*

