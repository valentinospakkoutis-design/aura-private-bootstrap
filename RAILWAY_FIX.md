# 🔧 Railway Deployment Fix

## ⚠️ Problem

Το Railway τρέχει **Metro Bundler** (mobile app) αντί για το **backend** (FastAPI).

**Reason**: Το Railway έχει deploy το root directory αντί για το `backend/` folder.

---

## ✅ Solution: Configure Railway

### Option 1: Change Root Directory (Easiest)

1. **Go to Railway Dashboard**
2. **Select your service**
3. **Settings** tab
4. **Root Directory**: Change to `backend`
5. **Save**
6. **Redeploy**

### Option 2: Use railway.json (Already Created)

Έχω δημιουργήσει `railway.json` που:
- ✅ Sets build command to `backend` folder
- ✅ Sets start command to run FastAPI
- ✅ Uses correct port (`$PORT`)

**Railway should auto-detect this file!**

---

## 🚀 Quick Fix Steps

### Step 1: Update Railway Settings

1. **Railway Dashboard** → Your service
2. **Settings** → **Root Directory**
3. Change to: `backend`
4. **Save**

### Step 2: Redeploy

1. **Deployments** tab
2. Click **"Redeploy"** (or push new commit)

### Step 3: Verify

Check logs - should see:
```
Starting uvicorn
Application startup complete
```

**Not**:
```
Starting Metro Bundler
```

---

## 📋 Files Created

1. **`railway.json`** (root) - Railway configuration
2. **`Procfile`** - Process file for Railway
3. **`backend/railway.json`** - Backend-specific config

---

## 🔍 Verify Deployment

### Check Logs

Should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT
```

### Test API

Open in browser:
```
https://your-railway-url.railway.app/health
```

Should return:
```json
{"status": "ok"}
```

---

## ⚠️ If Still Not Working

### Check Railway Settings:

1. **Root Directory**: Must be `backend`
2. **Start Command**: Should be `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **Build Command**: Should install from `requirements.txt`

### Manual Override:

In Railway Settings → **Deploy**:
- **Start Command**: 
  ```
  cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

---

## ✅ After Fix

1. Get production API URL from Railway
2. Update `mobile/src/config/environment.js`
3. Build standalone APK

---

**Status**: Configuration files created! Update Railway settings and redeploy! 🚀

*Made with 💎 in Cyprus*

