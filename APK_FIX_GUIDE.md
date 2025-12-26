# 🔧 APK Fix Guide - API Connection Issue

## ⚠️ Το Πρόβλημα

Το APK που έφτιαξα χρησιμοποιεί **local IP address** (`192.168.178.97:8000`) για το API URL. Αυτό σημαίνει:

- ✅ **Λειτουργεί** μόνο αν είσαι στο **ίδιο WiFi network** με τον υπολογιστή που τρέχει το backend
- ❌ **Δεν λειτουργεί** αν είσαι σε διαφορετικό WiFi ή mobile data
- ❌ **Δεν λειτουργεί** αν το backend δεν τρέχει

---

## 🔍 Πώς να Ελέγξεις το Πρόβλημα

1. **Άνοιξε το app** στο Android device
2. **Πάτα "🔍 Debug Info"** στο κάτω μέρος της home screen
3. **Δες το "API Base URL"** - αν είναι `192.168.x.x`, αυτό είναι το πρόβλημα

---

## ✅ Λύσεις

### **Λύση 1: Χρήση στο ίδιο WiFi (Γρήγορη)**

1. Βεβαιώσου ότι το **backend τρέχει** στον υπολογιστή σου
2. Βεβαιώσου ότι το **Android device είναι στο ίδιο WiFi**
3. Το app θα λειτουργήσει κανονικά

**Πώς να τρέξεις το backend:**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### **Λύση 2: Deploy Backend σε Production (Μόνιμη)**

Για να λειτουργεί το app **οπουδήποτε** (χωρίς WiFi), πρέπει να deploy-άρεις το backend σε production server.

#### **Βήμα 1: Deploy Backend**

**Option A: Railway (Προτεινόμενο)**
1. Πήγαινε στο [Railway.app](https://railway.app)
2. Sign up / Login
3. New Project → Deploy from GitHub
4. Επίλεξε το `backend` folder
5. Railway θα deploy-άρει αυτόματα
6. Πάρε το production URL (π.χ. `https://aura-backend.railway.app`)

**Option B: Render**
1. Πήγαινε στο [Render.com](https://render.com)
2. New Web Service
3. Connect GitHub repo
4. Root Directory: `backend`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Πάρε το production URL

#### **Βήμα 2: Update API URL**

**Μέθοδος 1: Environment Variable (Προτεινόμενο)**

1. Άνοιξε `eas.json`
2. Βρες το `production` profile
3. Πρόσθεσε το `EXPO_PUBLIC_API_URL`:

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_ENVIRONMENT": "production",
        "NODE_ENV": "production",
        "EXPO_PUBLIC_API_URL": "https://your-railway-url.railway.app",
        "EXPO_PUBLIC_ENABLE_ANALYTICS": "true",
        "EXPO_PUBLIC_ENABLE_CRASH_REPORTING": "true"
      }
    }
  }
}
```

4. Rebuild το APK:
```bash
npm run build:android:production
```

**Μέθοδος 2: Update environment.js**

1. Άνοιξε `mobile/src/config/environment.js`
2. Βρες το `production` object
3. Άλλαξε το `apiUrl`:

```javascript
production: {
  apiUrl: 'https://your-railway-url.railway.app', // ← CHANGE THIS
  apiTimeout: 20000,
  enableLogging: false,
  enableCache: true,
  cacheTTL: 10 * 60 * 1000,
},
```

4. Rebuild το APK:
```bash
npm run build:android:production
```

---

## 🧪 Testing

Μετά το rebuild:

1. **Download το νέο APK**
2. **Εγκατάστησέ το** στο device
3. **Άνοιξε το app**
4. **Πάτα "🔍 Debug Info"**
5. **Ελέγξε** ότι το API URL είναι το production URL (όχι local IP)
6. **Test** ότι λειτουργεί χωρίς WiFi (με mobile data)

---

## 📝 Debug Info Features

Το app τώρα έχει **Debug Info** που δείχνει:

- ✅ Environment (development/production)
- ✅ API Base URL
- ✅ Connection Status
- ✅ Health Check
- ✅ App Version
- ✅ Troubleshooting tips

**Πώς να το ανοίξεις:**
- Στο home screen, πάτα "🔍 Debug Info" στο footer
- Ή όταν υπάρχει network error, πάτα "🔍 Debug Info" button

---

## 🚨 Common Issues

### **Issue: "Failed to fetch" Error**

**Αιτία:** Το backend δεν είναι reachable

**Λύσεις:**
1. Ελέγξε ότι το backend τρέχει (αν local IP)
2. Ελέγξε ότι είσαι στο ίδιο WiFi (αν local IP)
3. Ελέγξε ότι το production URL είναι σωστό (αν production)
4. Test το backend URL στο browser: `https://your-url.railway.app/health`

### **Issue: App Crashes on Startup**

**Αιτία:** Missing dependencies ή configuration error

**Λύσεις:**
1. Check logs: `npm run build:status` → View Logs
2. Rebuild: `npm run build:android:production`
3. Check `app.config.js` για errors

### **Issue: "Network Error" αλλά έχω internet**

**Αιτία:** Το API URL είναι λάθος ή το backend δεν τρέχει

**Λύσεις:**
1. Άνοιξε Debug Info
2. Ελέγξε το API URL
3. Test το backend URL manually
4. Ελέγξε firewall settings

---

## 📚 Additional Resources

- **Backend Deployment:** `QUICK_DEPLOY_BACKEND.md`
- **API Configuration:** `API_URL_CONFIGURATION.md`
- **Production Setup:** `SIMPLE_PRODUCTION_SETUP.md`

---

## ✅ Summary

**Γρήγορη Λύση (Testing):**
- Χρησιμοποίησε το app στο ίδιο WiFi με τον υπολογιστή που τρέχει το backend

**Μόνιμη Λύση (Production):**
1. Deploy backend σε Railway/Render
2. Update `EXPO_PUBLIC_API_URL` στο `eas.json`
3. Rebuild APK
4. Test με mobile data

---

*Made with 💎 in Cyprus*

