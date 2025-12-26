# 🚀 Simple Production Setup Guide

## 📖 Τι είναι το Production API URL;

Το **Production API URL** είναι η διεύθυνση (URL) του backend server σου που:
- ✅ Είναι online στο internet (όχι localhost)
- ✅ Μπορεί να προσπελαστεί από οποιοδήποτε device
- ✅ Έχει HTTPS (ασφαλής σύνδεση)

**Παράδειγμα**: `https://aura-backend.railway.app`

---

## 🎯 Επιλογές για Production Backend

### Option 1: Railway (Easiest - Recommended) ⭐

**Railway** είναι πλατφόρμα που κάνει deploy το backend σου αυτόματα.

#### Step 1: Create Railway Account
1. Go to: https://railway.app
2. Sign up (free tier available)
3. Connect GitHub account (optional)

#### Step 2: Deploy Backend
1. Click "New Project"
2. Select "Deploy from GitHub repo" (ή "Empty Project")
3. Add your backend folder
4. Railway auto-detects Python/FastAPI
5. Click "Deploy"

#### Step 3: Get API URL
1. Railway gives you a URL like: `https://your-app.railway.app`
2. This is your **Production API URL**!

**Cost**: Free tier available, then ~$5/month

---

### Option 2: Render (Also Easy)

**Render** είναι παρόμοια με Railway.

#### Step 1: Create Render Account
1. Go to: https://render.com
2. Sign up (free tier available)

#### Step 2: Deploy Backend
1. Click "New +" → "Web Service"
2. Connect GitHub repo
3. Select backend folder
4. Render auto-detects Python
5. Click "Create Web Service"

#### Step 3: Get API URL
1. Render gives you: `https://your-app.onrender.com`
2. This is your **Production API URL**!

**Cost**: Free tier available, then ~$7/month

---

### Option 3: Use Local Backend (For Testing Only)

**⚠️ Warning**: Αυτό λειτουργεί μόνο για testing, όχι για production!

Αν θέλεις να test το app χωρίς production backend:

1. **Keep development API URL**:
   ```javascript
   // In environment.js - keep as is for now
   production: {
     apiUrl: 'http://192.168.178.97:8000', // Local IP
     // ...
   }
   ```

2. **Limitations**:
   - ❌ Works only on same WiFi network
   - ❌ Not accessible from outside
   - ❌ Not secure (HTTP, not HTTPS)
   - ✅ Good for testing only

---

## 🎯 Recommended: Start with Railway

### Why Railway?
- ✅ Easiest to use
- ✅ Free tier available
- ✅ Auto-deploys from GitHub
- ✅ Automatic HTTPS
- ✅ Good documentation

### Quick Start with Railway:

1. **Sign up**: https://railway.app
2. **New Project** → **Deploy from GitHub**
3. **Select your repo** → **Select backend folder**
4. **Railway auto-detects** Python/FastAPI
5. **Deploy** → Get URL
6. **Copy URL** → This is your Production API URL!

---

## 📝 After You Get Production API URL

### Step 1: Update environment.js

Edit `mobile/src/config/environment.js` line 41:

```javascript
production: {
  apiUrl: 'https://your-railway-url.railway.app', // ← Paste your URL here
  apiTimeout: 20000,
  enableLogging: false,
  enableCache: true,
  cacheTTL: 10 * 60 * 1000,
},
```

### Step 2: Test the URL

Open in browser:
```
https://your-railway-url.railway.app/health
```

Should show: `{"status": "ok"}`

### Step 3: Build APK

```bash
npm run build:android:standalone
```

---

## 🆘 Need Help?

### If Backend Not Deployed Yet:

**Option A**: Deploy to Railway/Render (recommended)
- Follow steps above
- Takes ~10 minutes

**Option B**: Use Local Backend (testing only)
- Keep local IP in production config
- Works only on same WiFi
- Good for initial testing

**Option C**: Ask for Help
- I can help you deploy
- Or guide you step-by-step

---

## 📋 Checklist

- [ ] Choose deployment platform (Railway/Render)
- [ ] Create account
- [ ] Deploy backend
- [ ] Get production API URL
- [ ] Update `environment.js` with URL
- [ ] Test URL in browser
- [ ] Build standalone APK

---

## 💡 Pro Tips

1. **Start with Railway**: Easiest for beginners
2. **Free tier is enough**: For testing and small apps
3. **Test before building**: Make sure backend works
4. **Keep local for development**: Use production URL only for builds

---

## 🎯 Next Steps

1. **Choose**: Railway (recommended) or Render
2. **Deploy**: Follow platform's guide
3. **Get URL**: Copy the URL they give you
4. **Update config**: Paste URL in `environment.js`
5. **Build**: `npm run build:android:standalone`

---

**Don't worry!** Το deployment είναι πιο εύκολο από όσο φαίνεται. Railway/Render κάνουν όλη τη δουλειά για σένα! 🚀

*Made with 💎 in Cyprus*

