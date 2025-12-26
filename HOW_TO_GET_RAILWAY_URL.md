# 🔗 How to Get Railway URL - Step by Step

## 📋 Step-by-Step Guide

### **Method 1: From Networking Settings** (Easiest)

1. **Go to Railway Dashboard**
   - Open: https://railway.app
   - Login if needed

2. **Select Your Project**
   - Click on project: `diplomatic-peace` (or your project name)
   - Or click on service: `aura-private-bootstrap`

3. **Go to Settings**
   - Click **"Settings"** tab (top navigation)

4. **Go to Networking**
   - In Settings, click **"Networking"** tab

5. **Find Public Domain**
   - Look for **"Public Domain"** section
   - You'll see a URL like:
     ```
     https://aura-private-bootstrap-production.up.railway.app
     ```
   - Or:
     ```
     https://aura-backend.railway.app
     ```

6. **Copy the URL**
   - Click the **copy icon** (📋) next to the URL
   - Or select and copy manually

---

### **Method 2: From Service Overview** (Alternative)

1. **Go to Railway Dashboard**
   - Open: https://railway.app

2. **Select Service**
   - Click on service: `aura-private-bootstrap`

3. **Check Service Header**
   - At the top, you might see the URL
   - Or click **"Settings"** → **"Networking"**

---

### **Method 3: From Deployments** (If URL is shown)

1. **Go to Railway Dashboard**
   - Open: https://railway.app

2. **Select Service**
   - Click on service: `aura-private-bootstrap`

3. **Go to Deployments**
   - Click **"Deployments"** tab

4. **Check Active Deployment**
   - Look at the **"ACTIVE"** deployment
   - Sometimes the URL is shown there

---

## 🔍 What the URL Looks Like

**Railway URLs typically look like:**
```
https://aura-private-bootstrap-production.up.railway.app
```

**Or with custom domain:**
```
https://aura-backend.railway.app
```

**Format:**
- Starts with `https://`
- Contains your service/project name
- Ends with `.railway.app` or custom domain

---

## ⚠️ If You Don't See a URL

### **Option 1: Generate Public Domain**

1. **Go to Settings** → **Networking**
2. **Click "Generate Domain"** button
3. Railway will create a public URL
4. Copy the generated URL

### **Option 2: Check if Service is Exposed**

1. **Go to Settings** → **Networking**
2. **Check "Public" toggle**
3. Make sure it's **enabled** (green/on)
4. If disabled, enable it
5. Railway will generate a URL

---

## 🧪 Test the URL

After you get the URL, test it:

1. **Open in browser:**
   ```
   https://your-railway-url.railway.app/health
   ```

2. **Expected response:**
   ```json
   {"status": "ok"}
   ```

3. **If you see this, the URL is correct!** ✅

---

## 📝 Quick Checklist

- [ ] Logged into Railway Dashboard
- [ ] Selected `aura-private-bootstrap` service
- [ ] Went to Settings → Networking
- [ ] Found Public Domain URL
- [ ] Copied the URL
- [ ] Tested URL in browser (should return `{"status": "ok"}`)

---

## 🎯 Next Steps After Getting URL

1. **Copy the URL**
2. **Test it** in browser: `https://your-url.railway.app/health`
3. **Update `eas.json`** with the URL
4. **Rebuild APK**

---

*Made with 💎 in Cyprus*

