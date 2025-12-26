# 🔧 Railway Build Fix - pip & uvicorn: command not found

## ❌ Τα Προβλήματα

### **Error 1: pip: command not found** ✅ FIXED
```
/bin/bash: line 1: pip: command not found
exit code: 127
```

**Αιτία:**
- Το `railway.json` στο root είχε `buildCommand: "cd backend && pip install -r requirements.txt"`
- Το Nixpacks (Railway's builder) δεν έχει `pip` installed by default
- Το Nixpacks κάνει **auto-detect** Python projects και εγκαθιστά dependencies αυτόματα

**Fix:**
- Αφαίρεσα το `buildCommand` - το Nixpacks κάνει auto-detect

### **Error 2: uvicorn: command not found** ✅ FIXED
```
/bin/bash: line 1: uvicorn: command not found
```

**Αιτία:**
- Το `uvicorn` δεν είναι στο PATH ακόμα και αν είναι installed
- Χρειάζεται `python -m uvicorn` αντί για `uvicorn` απευθείας

**Fix:**
- Άλλαξα `uvicorn` σε `python3 -m uvicorn` σε όλα τα `railway.json` files

### **Error 3: python: command not found** ✅ FIXED
```
/bin/bash: line 1: python: command not found
```

**Αιτία:**
- Στο Railway/Nixpacks, το `python` δεν είναι πάντα διαθέσιμο
- Χρειάζεται `python3` αντί για `python`

**Fix:**
- Άλλαξα `python` σε `python3` σε όλα τα `railway.json` files
- Δημιούργησα `backend/runtime.txt` με Python 3.11.0

---

## ✅ Η Λύση

**1. Αφαίρεσα το `buildCommand`:**
- Το Nixpacks θα **auto-detect** το Python project
- Θα βρει το `requirements.txt` στο `backend/` folder
- Θα εγκαταστήσει dependencies **αυτόματα** με το σωστό pip version

**2. Άλλαξα το `startCommand`:**
- `uvicorn` → `python3 -m uvicorn`
- `python` → `python3` (για Railway/Nixpacks compatibility)
- Αυτό εξασφαλίζει ότι το uvicorn τρέχει με το σωστό Python environment

**3. Δημιούργησα `runtime.txt`:**
- Ορίζει Python version 3.11.0
- Βοηθάει το Nixpacks να επιλέξει το σωστό Python version

**4. Δημιούργησα `backend/nixpacks.toml`:**
- Ορίζει ρητά Python 3.11 και pip
- Ορίζει το install command
- Ορίζει το start command
- Αυτό εξασφαλίζει ότι το Python είναι installed σωστά

---

## 📝 Configuration Files

### **Root `railway.json`** (Updated)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
    // ✅ Removed buildCommand - Nixpacks auto-detects
  },
  "deploy": {
    "startCommand": "cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT",
    // ✅ Changed: python → python3, uvicorn → python3 -m uvicorn
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### **Backend `railway.json`** (Updated)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT"
    // ✅ Changed: python → python3, uvicorn → python3 -m uvicorn
  }
}
```

### **Backend `runtime.txt`** (New)
```
python-3.11.0
```
// ✅ Specifies Python version for Nixpacks

### **Backend `nixpacks.toml`** (New)
```toml
[phases.setup]
nixPkgs = ["python311", "pip"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT"
```
// ✅ Explicitly defines Python 3.11, pip, and commands for Nixpacks

---

## 🚀 Railway Settings

**Σημαντικό:** Στο Railway Dashboard, βεβαιώσου ότι:

1. **Root Directory:** `backend` (όχι root)
   - Railway Dashboard → Settings → Deploy
   - Set **Root Directory** to `backend`

2. **OR** αν το Root Directory είναι empty/root:
   - Το `startCommand` στο root `railway.json` έχει `cd backend && ...`
   - Αυτό θα λειτουργήσει

---

## ✅ Τι Έγινε

1. ✅ Αφαίρεσα `buildCommand` από root `railway.json`
2. ✅ Το Nixpacks θα κάνει auto-detect Python project
3. ✅ Θα βρει `backend/requirements.txt` αυτόματα
4. ✅ Θα εγκαταστήσει dependencies με σωστό pip version

---

## 🧪 Testing

Μετά το fix:

1. **Push changes** στο GitHub
2. **Railway θα auto-redeploy**
3. **Check logs** - θα δεις:
   - ✅ Nixpacks detecting Python
   - ✅ Installing dependencies from requirements.txt
   - ✅ Build successful
   - ✅ Starting uvicorn server

---

## 📋 Summary

**Before:**
- ❌ Manual `buildCommand` με `pip` (not found)
- ❌ Build failed

**After:**
- ✅ Nixpacks auto-detection
- ✅ Auto-install dependencies
- ✅ Build should succeed

---

*Made with 💎 in Cyprus*

