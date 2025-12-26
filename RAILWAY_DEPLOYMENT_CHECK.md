# 🔍 Railway Deployment Check Guide

## ✅ After Fixes Applied

Έχουμε διορθώσει:
1. ✅ **pip: command not found** - Αφαίρεσα buildCommand, Nixpacks auto-detects
2. ✅ **uvicorn: command not found** - Άλλαξα σε `python -m uvicorn`

---

## 📋 Step-by-Step Check

### **Step 1: Verify Railway Settings**

1. **Go to Railway Dashboard**: https://railway.app
2. **Select your project**: `aura-private-bootstrap`
3. **Settings** → **Deploy** tab
4. **Check:**
   - ✅ **Root Directory**: `backend` (ή empty/root)
   - ✅ **Start Command**: Should be auto-detected from `railway.json`
   - ✅ **Build Command**: Should be empty (Nixpacks auto-detects)

---

### **Step 2: Check Build Logs**

1. **Go to Deployments** tab
2. **Click on latest deployment**
3. **Click "Build Logs"** tab
4. **Look for:**

**✅ Success indicators:**
```
✓ Nixpacks detecting Python
✓ Installing dependencies from requirements.txt
✓ Build successful
✓ Container built successfully
```

**❌ If you see errors:**
- Check if `requirements.txt` exists in `backend/` folder
- Check if Python version is compatible
- Check Railway logs for specific error messages

---

### **Step 3: Check Deploy Logs**

1. **Click "Deploy Logs"** tab
2. **Look for:**

**✅ Success indicators:**
```
Starting Container
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT
```

**❌ If you see errors:**
- `uvicorn: command not found` → Check if `python -m uvicorn` is used
- `Module not found` → Check if dependencies installed correctly
- `Port already in use` → Railway handles this automatically

---

### **Step 4: Test API Endpoints**

1. **Get your Railway URL:**
   - Railway Dashboard → **Settings** → **Networking**
   - Copy the **Public Domain** (e.g., `aura-backend.railway.app`)

2. **Test Health Endpoint:**
   ```bash
   curl https://your-railway-url.railway.app/health
   ```
   
   **Expected response:**
   ```json
   {"status": "ok"}
   ```

3. **Test in Browser:**
   - Open: `https://your-railway-url.railway.app/health`
   - Should see: `{"status": "ok"}`

4. **Test API Root:**
   - Open: `https://your-railway-url.railway.app/`
   - Should see API documentation or welcome page

---

### **Step 5: Test More Endpoints**

Use the test script:
```bash
npm run test:endpoints:prod
```

Or manually test:
```bash
# Health check
curl https://your-railway-url.railway.app/health

# Quote of the day
curl https://your-railway-url.railway.app/api/quote-of-day

# AI Assets
curl https://your-railway-url.railway.app/api/ai/assets
```

---

## 🐛 Troubleshooting

### **Issue: Build Still Failing**

**Check:**
1. Railway Dashboard → Build Logs
2. Look for specific error message
3. Common issues:
   - Missing `requirements.txt`
   - Python version incompatibility
   - Missing dependencies

**Fix:**
- Ensure `backend/requirements.txt` exists
- Check Python version in `requirements.txt` (if specified)
- Verify all dependencies are listed

---

### **Issue: Deploy Still Failing**

**Check:**
1. Railway Dashboard → Deploy Logs
2. Look for error after "Starting Container"

**Common errors:**

**1. `python: command not found`**
- Railway might need Python 3 explicitly
- Try: `python3 -m uvicorn` in `railway.json`

**2. `Module not found: uvicorn`**
- Dependencies not installed
- Check Build Logs for installation errors

**3. `Port already in use`**
- Railway handles this automatically
- Check if another service is using the port

---

### **Issue: API Not Responding**

**Check:**
1. Railway Dashboard → Deploy Logs
2. Verify uvicorn started successfully
3. Check Railway URL is correct

**Fix:**
- Verify Railway service is running (green status)
- Check networking settings (public domain enabled)
- Test with curl or browser

---

## 📝 Configuration Summary

### **Root `railway.json`:**
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port $PORT"
  }
}
```

### **Backend `railway.json`:**
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python -m uvicorn main:app --host 0.0.0.0 --port $PORT"
  }
}
```

---

## ✅ Success Checklist

- [ ] Build logs show successful build
- [ ] Deploy logs show uvicorn starting
- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] API endpoints respond correctly
- [ ] Railway URL is accessible
- [ ] No errors in logs

---

## 🚀 Next Steps After Successful Deployment

1. **Get Production API URL:**
   - Railway Dashboard → Settings → Networking
   - Copy Public Domain URL

2. **Update Mobile App:**
   - Update `eas.json`:
     ```json
     "EXPO_PUBLIC_API_URL": "https://your-railway-url.railway.app"
     ```

3. **Rebuild APK:**
   ```bash
   npm run build:android:production
   ```

4. **Test APK:**
   - Download and install on device
   - Open Debug Info
   - Verify API URL is correct
   - Test API connection

---

*Made with 💎 in Cyprus*

