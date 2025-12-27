# 🔧 Railway Root Directory Configuration

## ⚠️ Critical Issue

Το Railway **δεν έχει Root Directory set στο `backend`**, γι' αυτό προσπαθεί να deploy το root directory (με το mobile app) αντί για το backend.

## 🔍 Πώς να το ελέγξεις

1. **Άνοιξε Railway Dashboard**
   - Πήγαινε στο: https://railway.app/dashboard
   - Επίλεξε το project: `aura-private-bootstrap`

2. **Άνοιξε Settings**
   - Κάνε click στο **Settings** tab
   - Scroll down στο **Root Directory** section

3. **Set Root Directory**
   - Βρες το **Root Directory** field
   - Γράψε: `backend`
   - Κάνε click **Save**

## ✅ Verification

Μετά το save, το Railway θα:
- ✅ Build μόνο το `backend` directory
- ✅ Εγκαταστήσει Python dependencies από `backend/requirements.txt`
- ✅ Δημιουργήσει `/opt/venv` virtual environment
- ✅ Τρέξει το `start.sh` script

## 📋 Step-by-Step

```
1. Railway Dashboard → Project → Settings
2. Scroll to "Root Directory"
3. Enter: backend
4. Click "Save"
5. Railway will auto-redeploy
6. Check Deploy Logs - should see Python found in /opt/venv
```

## 🎯 Expected Result

Μετά το Root Directory fix, τα logs θα δείχνουν:
```
=== Finding Python ===
Current directory: /app
Listing current directory:
main.py
requirements.txt
start.sh
...

✓ Found Nixpacks virtual environment at /opt/venv
Using Python from venv: /opt/venv/bin/python3
Python 3.11.x
=== Starting Uvicorn ===
```

## ⚠️ Important

Αν το Root Directory **δεν είναι set στο `backend`**, το Railway:
- ❌ Δεν θα βρει το `requirements.txt`
- ❌ Δεν θα εγκαταστήσει Python dependencies
- ❌ Δεν θα δημιουργήσει `/opt/venv`
- ❌ Το `start.sh` δεν θα βρει Python

**Αυτό είναι το root cause του "Python not found" error!**

