# 🚀 Quick Deploy Guide - Backend στο Cloud

## ⚡ Γρήγορη Λύση (10 λεπτά)

### Railway (Συνιστάται)

1. **Πήγαινε στο:** [railway.app](https://railway.app)
2. **Sign up** με GitHub
3. **New Project** → **Deploy from GitHub repo**
4. **Επίλεξε** το `aura-private-bootstrap` repo
5. **Settings:**
   - **Root Directory:** `backend`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. **Πάρε το URL:** `https://your-app.railway.app`
7. **Update mobile app:**
   - Άνοιξε `mobile/src/config/environment.js`
   - Άλλαξε `production.apiUrl` σε `https://your-app.railway.app`
8. **Rebuild app:**
   ```bash
   eas build --profile production --platform android
   ```

**Τέλος!** Το backend τρέχει στο cloud. 🎉

---

## 📱 Update Mobile App

### Επιλογή 1: Environment Variables (Συνιστάται)

**Ενημέρωσε `eas.json`:**

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_URL": "https://your-app.railway.app",
        "EXPO_PUBLIC_WS_URL": "wss://your-app.railway.app/ws"
      }
    }
  }
}
```

### Επιλογή 2: Direct Update

**Ενημέρωσε `mobile/src/config/environment.js`:**

```javascript
production: {
  apiUrl: 'https://your-app.railway.app', // ← Railway URL
  // ...
}
```

---

## 🔄 Rebuild Mobile App

```bash
# Development build (για testing)
eas build --profile preview --platform android

# Production build
eas build --profile production --platform android
```

---

## ✅ Verify Deployment

### 1. Test Backend:
```bash
curl https://your-app.railway.app/api/ai/predictions
```

### 2. Test από Mobile:
- Install το rebuild app
- Test όλα τα features
- Πρέπει να λειτουργούν χωρίς υπολογιστή!

---

## 🆘 Troubleshooting

### Backend δεν απαντάει:
- Ελέγξτε Railway logs
- Ελέγξτε ότι το `PORT` variable είναι set

### CORS errors:
- Το backend έχει `allow_origins=["*"]` - θα λειτουργήσει

### Network errors στο app:
- Ελέγξτε ότι το production URL είναι σωστό
- Rebuild το app με το νέο URL

---

## 📚 Full Guide

Για περισσότερες λεπτομέρειες, δες: `DEPLOYMENT_GUIDE.md

