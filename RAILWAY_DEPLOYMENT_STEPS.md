# 🚂 Railway Deployment - Step by Step

## Prerequisites
- ✅ GitHub account
- ✅ Repository pushed to GitHub
- ✅ Backend folder ready

---

## Method 1: Web Interface (Easiest - Recommended)

### Step 1: Create Railway Account
1. Go to [railway.app](https://railway.app)
2. Click **"Start a New Project"**
3. Sign up with **GitHub** (recommended)

### Step 2: Deploy from GitHub
1. Click **"Deploy from GitHub repo"**
2. Select your repository: `aura-private-bootstrap`
3. Railway will detect the project

### Step 3: Configure Service
1. Railway will create a service automatically
2. Click on the service to configure:
   - **Root Directory:** `backend`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Step 4: Add Environment Variables (Optional)
1. Go to **Variables** tab
2. Add if needed:
   ```
   CORS_ORIGINS=*
   ENVIRONMENT=production
   ```

### Step 5: Get Your URL
1. Go to **Settings** → **Networking**
2. Click **"Generate Domain"**
3. Copy the URL: `https://your-app.railway.app`

### Step 6: Update Mobile App
1. Open `eas.json`
2. Update production environment:
   ```json
   "production": {
     "env": {
       "EXPO_PUBLIC_API_URL": "https://your-app.railway.app",
       "EXPO_PUBLIC_WS_URL": "wss://your-app.railway.app/ws"
     }
   }
   ```

### Step 7: Rebuild Mobile App
```bash
eas build --profile production --platform android
```

**Done!** 🎉

---

## Method 2: Railway CLI

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login
```bash
railway login
```

### Step 3: Initialize Project
```bash
cd backend
railway init
```

### Step 4: Link to Existing Project (if needed)
```bash
railway link
```

### Step 5: Deploy
```bash
railway up
```

### Step 6: Get URL
```bash
railway domain
```

### Step 7: View Logs
```bash
railway logs
```

---

## Verification

### Test Backend
```bash
curl https://your-app.railway.app/api/ai/predictions
```

Should return JSON with predictions.

### Test from Mobile
1. Install rebuilt app
2. Test all features
3. Should work without your computer!

---

## Troubleshooting

### Backend not starting
- Check logs: `railway logs` or Railway dashboard
- Verify `Procfile` exists in `backend/` folder
- Verify `requirements.txt` is complete

### CORS errors
- Add to Railway environment variables:
  ```
  CORS_ORIGINS=*
  ```

### Port errors
- Railway automatically sets `$PORT` variable
- Make sure start command uses `$PORT`

### Database connection
- If using PostgreSQL, add Railway PostgreSQL service
- Connection string will be in `DATABASE_URL` variable

---

## Cost
- **Free tier:** $5 credit/month
- **Hobby:** $5/month (if you exceed free tier)
- **Pro:** $20/month (for production)

---

## Next Steps After Deployment

1. ✅ Backend deployed
2. ✅ Got production URL
3. ✅ Updated `eas.json`
4. ✅ Rebuilt mobile app
5. ✅ Tested all features

**Your app now works without your computer!** 🚀

