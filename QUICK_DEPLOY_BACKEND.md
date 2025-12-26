# ⚡ Quick Backend Deployment Guide

## 🎯 Goal: Deploy Backend σε 10 λεπτά

Αυτός ο οδηγός σου δείχνει πώς να deploy το backend σου στο Railway (πιο εύκολο).

---

## 📋 Prerequisites

- ✅ Backend folder exists (`backend/`)
- ✅ GitHub account (optional, αλλά recommended)
- ✅ 10 minutes

---

## 🚀 Railway Deployment (Step-by-Step)

### Step 1: Create Railway Account (2 min)

1. Go to: **https://railway.app**
2. Click **"Start a New Project"**
3. Sign up with:
   - Email, ή
   - GitHub (recommended - easier)
4. Verify email

### Step 2: Create New Project (1 min)

1. Click **"New Project"**
2. Choose:
   - **"Deploy from GitHub repo"** (if connected GitHub)
   - **"Empty Project"** (if not using GitHub)

### Step 3: Add Backend (2 min)

**If using GitHub:**
1. Select your repository
2. Railway auto-detects the backend
3. Select `backend/` folder
4. Click **"Deploy"**

**If using Empty Project:**
1. Click **"New"** → **"GitHub Repo"**
2. Connect your repo
3. Select `backend/` folder
4. Click **"Deploy"**

### Step 4: Configure (2 min)

Railway auto-detects Python, but check:

1. **Build Command**: (usually auto)
   ```
   pip install -r requirements.txt
   ```

2. **Start Command**: (usually auto)
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

3. **Environment Variables**: (if needed)
   - Add any `.env` variables here

### Step 5: Get Your URL (1 min)

1. Wait for deployment (~2-3 minutes)
2. Click on your service
3. Go to **"Settings"** tab
4. Find **"Public Domain"**
5. Copy the URL: `https://your-app.railway.app`

**This is your Production API URL!** 🎉

### Step 6: Test (1 min)

Open in browser:
```
https://your-app.railway.app/health
```

Should show: `{"status": "ok"}`

---

## 📝 Update Mobile App

### Edit `mobile/src/config/environment.js`:

```javascript
production: {
  apiUrl: 'https://your-app.railway.app', // ← Paste Railway URL here
  apiTimeout: 20000,
  enableLogging: false,
  enableCache: true,
  cacheTTL: 10 * 60 * 1000,
},
```

---

## ✅ Done!

Τώρα μπορείς να build το standalone APK:

```bash
npm run build:android:standalone
```

---

## 🆘 Troubleshooting

### Issue: "Build failed"
**Solution**: Check Railway logs, verify `requirements.txt` exists

### Issue: "Port error"
**Solution**: Make sure backend uses `$PORT` environment variable

### Issue: "Module not found"
**Solution**: Add missing packages to `requirements.txt`

### Issue: "CORS error"
**Solution**: Update backend CORS settings (see below)

---

## 🔧 Backend CORS Fix

If you get CORS errors, update `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 💰 Railway Pricing

- **Free Tier**: $5 credit/month (enough for testing)
- **Hobby**: $5/month (after free tier)
- **Pro**: $20/month (for production)

**For testing**: Free tier is enough!

---

## 🎯 Alternative: Render

If Railway doesn't work, try Render:

1. Go to: **https://render.com**
2. Sign up
3. **New +** → **Web Service**
4. Connect GitHub repo
5. Select `backend/` folder
6. Click **"Create Web Service"**
7. Get URL: `https://your-app.onrender.com`

---

## 📚 Next Steps

1. ✅ Deploy backend to Railway
2. ✅ Get production API URL
3. ✅ Update `environment.js`
4. ✅ Test API URL
5. ✅ Build standalone APK

---

**That's it!** Railway does most of the work for you! 🚀

*Made with 💎 in Cyprus*

