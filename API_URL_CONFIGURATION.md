# 🔧 Production API URL Configuration

## 📍 Current Configuration

Το production API URL είναι currently set to:
```javascript
apiUrl: 'https://api.aura.com' // Placeholder - needs to be updated
```

---

## ⚠️ Action Required

**Πρέπει να αλλάξεις το production API URL** με το πραγματικό URL του backend σου.

---

## 🎯 Where to Change

### Option 1: Update environment.js (Recommended)

**File**: `mobile/src/config/environment.js`

**Line 41**:
```javascript
production: {
  apiUrl: 'https://your-actual-api-url.com', // ← CHANGE THIS
  apiTimeout: 20000,
  enableLogging: false,
  enableCache: true,
  cacheTTL: 10 * 60 * 1000,
},
```

**Examples**:
- Railway: `https://your-app.railway.app`
- Render: `https://your-app.onrender.com`
- Custom domain: `https://api.aura.com`
- VPS: `https://your-server-ip.com`

---

### Option 2: Use Environment Variable

**Create `.env.production`**:
```bash
EXPO_PUBLIC_API_URL=https://your-actual-api-url.com
EXPO_PUBLIC_ENVIRONMENT=production
```

**Then update `app.config.js`** (line 41):
```javascript
apiUrl: process.env.EXPO_PUBLIC_API_URL || (process.env.NODE_ENV === 'production' ? 'https://your-actual-api-url.com' : undefined),
```

---

### Option 3: Update app.config.js Directly

**File**: `app.config.js`

**Line 41**:
```javascript
apiUrl: process.env.EXPO_PUBLIC_API_URL || (process.env.NODE_ENV === 'production' ? 'https://your-actual-api-url.com' : undefined),
```

---

## 🔍 How to Find Your Production API URL

### If Using Railway:
1. Go to Railway dashboard
2. Select your backend service
3. Copy the "Public Domain" URL
4. Example: `https://aura-backend.railway.app`

### If Using Render:
1. Go to Render dashboard
2. Select your backend service
3. Copy the "URL"
4. Example: `https://aura-backend.onrender.com`

### If Using Custom Server:
1. Use your domain or IP
2. Make sure HTTPS is enabled
3. Example: `https://api.aura.com` or `https://your-server.com`

---

## ✅ Requirements for Production API

### 1. HTTPS Required
- ✅ Must use `https://` (not `http://`)
- ✅ SSL certificate must be valid
- ✅ Android requires secure connections

### 2. CORS Configuration
Backend must allow requests from your app:
```python
# FastAPI example
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Accessible from Internet
- ✅ Must be accessible from any network
- ✅ No localhost or local IP
- ✅ Firewall must allow connections

---

## 🧪 Testing Your API URL

### Test 1: Health Check
```bash
curl https://your-api-url.com/health
```

Should return:
```json
{"status": "ok"}
```

### Test 2: From Browser
Open in browser:
```
https://your-api-url.com/api/quote-of-day
```

Should return JSON data.

### Test 3: CORS Test
Open browser console and test:
```javascript
fetch('https://your-api-url.com/health')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);
```

---

## 📋 Configuration Priority

Το app χρησιμοποιεί API URL με αυτή τη σειρά:

1. **Environment Variable** (`EXPO_PUBLIC_API_URL`)
2. **app.config.js** (`extra.apiUrl`)
3. **environment.js** (`production.apiUrl`)
4. **Fallback** (`https://api.aura.com`)

---

## 🚀 After Configuration

1. **Save changes**
2. **Build standalone APK**:
   ```bash
   npm run build:android:standalone
   ```
3. **Test the build**:
   - Install on device
   - Check if API connects
   - Verify data loads

---

## ⚠️ Common Issues

### Issue: "Network request failed"
**Solution**: Check API URL is correct and accessible

### Issue: "CORS error"
**Solution**: Configure CORS on backend

### Issue: "SSL certificate error"
**Solution**: Use valid HTTPS certificate

---

## 📝 Example Configurations

### Railway:
```javascript
apiUrl: 'https://aura-backend-production.railway.app'
```

### Render:
```javascript
apiUrl: 'https://aura-backend.onrender.com'
```

### Custom Domain:
```javascript
apiUrl: 'https://api.aura.com'
```

### VPS with Domain:
```javascript
apiUrl: 'https://your-server.com/api'
```

---

**Status**: ⚠️ **Action Required** - Update production API URL before building!

*Made with 💎 in Cyprus*

