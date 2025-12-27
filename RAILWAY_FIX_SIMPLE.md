# 🔧 Railway Fix - Simple Solution

## ⚠️ Το Πρόβλημα

Το Railway **δεν έχει Root Directory set στο `backend`**, γι' αυτό:
- Προσπαθεί να deploy το root directory (με mobile app)
- Δεν βρίσκει το `requirements.txt`
- Δεν εγκαθιστά Python dependencies
- Δεν δημιουργεί `/opt/venv`
- Το `start.sh` δεν βρίσκει Python

## ✅ Η Λύση (2 Λεπτά)

### Βήμα 1: Άνοιξε Railway Dashboard
1. Πήγαινε στο: https://railway.app/dashboard
2. Επίλεξε το project: **aura-private-bootstrap**

### Βήμα 2: Set Root Directory
1. Κάνε click στο **Settings** tab (αριστερά)
2. Scroll down στο **"Root Directory"** field
3. Γράψε: `backend`
4. Κάνε click **Save**

### Βήμα 3: Wait for Redeploy
- Το Railway θα κάνει **auto-redeploy** μετά το save
- Περίμενε 2-3 λεπτά
- Ελέγξε τα **Deploy Logs**

## ✅ Expected Result

Μετά το Root Directory fix, τα logs θα δείχνουν:
```
=== Railway Backend Startup ===
Current directory: /app
Listing files:
main.py
requirements.txt
start.sh
...

✓ Found Nixpacks virtual environment at /opt/venv
Using Python: /opt/venv/bin/python3
Python 3.11.x
=== Starting Uvicorn ===
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🎯 Status Check

Μετά το fix, το Railway θα:
- ✅ Build μόνο το `backend` directory
- ✅ Εγκαταστήσει Python dependencies από `requirements.txt`
- ✅ Δημιουργήσει `/opt/venv` virtual environment
- ✅ Τρέξει το `start.sh` script
- ✅ Start το uvicorn server

## 📸 Visual Guide

```
Railway Dashboard
├── Project: aura-private-bootstrap
│   ├── Settings (click here)
│   │   ├── Root Directory: [backend] ← Enter here
│   │   └── Save (click here)
│   └── Deploy Logs (check after save)
```

## ⚠️ Important

**Αν το Root Directory δεν είναι set στο `backend`:**
- ❌ Το Railway deploy το root directory (με mobile app)
- ❌ Δεν βρίσκει το `requirements.txt`
- ❌ Δεν εγκαθιστά Python dependencies
- ❌ Δεν δημιουργεί `/opt/venv`
- ❌ Το `start.sh` δεν βρίσκει Python

**Αυτό είναι το root cause του "Python not found" error!**

## 🆘 Αν Δεν Δουλεύει

1. **Ελέγξε ότι το Root Directory είναι `backend`** (όχι `./backend` ή `/backend`)
2. **Ελέγξε τα Build Logs** - πρέπει να δεις:
   - "Installing dependencies from requirements.txt"
   - "Creating virtual environment"
3. **Ελέγξε τα Deploy Logs** - πρέπει να δεις:
   - "✓ Found Nixpacks virtual environment at /opt/venv"
   - "Starting Uvicorn"

## 📞 Next Steps

Μετά το fix:
1. ✅ Railway backend θα είναι online
2. ✅ Θα πάρεις το Railway URL (π.χ. `https://aura-private-bootstrap-production.up.railway.app`)
3. ✅ Θα update το `eas.json` με το production API URL
4. ✅ Θα κάνεις rebuild του APK

