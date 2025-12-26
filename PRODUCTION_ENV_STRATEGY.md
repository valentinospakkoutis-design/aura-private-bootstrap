# 🔐 Production Environment Strategy

## 📋 Overview

Comprehensive environment management strategy για AURA app με proper separation of concerns.

---

## 🎯 Environment Levels

### 1. Development
- **Purpose**: Local development
- **API URL**: `http://192.168.178.97:8000` (local IP)
- **Logging**: Enabled
- **Analytics**: Disabled
- **Cache TTL**: 5 minutes

### 2. Staging
- **Purpose**: Pre-production testing
- **API URL**: `https://staging-api.aura.com`
- **Logging**: Enabled
- **Analytics**: Enabled
- **Cache TTL**: 5 minutes

### 3. Production
- **Purpose**: Live production
- **API URL**: `https://your-railway-url.railway.app` (from Railway)
- **Logging**: Disabled
- **Analytics**: Enabled
- **Cache TTL**: 10 minutes

---

## 📁 File Structure

```
.env                    # Local development (gitignored)
.env.staging           # Staging config (gitignored)
.env.production        # Production template (gitignored)
env.template          # Template (committed)
```

---

## 🔧 Configuration Priority

### Mobile App (Expo)

1. **Environment Variable** (`EXPO_PUBLIC_API_URL`)
2. **app.config.js** (`extra.apiUrl`)
3. **environment.js** (`production.apiUrl`)
4. **Fallback** (`https://api.aura.com`)

### Backend (Railway/Render)

1. **Platform Environment Variables** (Railway/Render dashboard)
2. **.env file** (if exists)
3. **Default values** (in code)

---

## 🚀 Setup Instructions

### For Mobile App

#### Development:
```bash
# .env file (auto-loaded)
EXPO_PUBLIC_ENVIRONMENT=development
EXPO_PUBLIC_API_URL=http://192.168.178.97:8000
```

#### Staging:
```bash
# .env.staging
EXPO_PUBLIC_ENVIRONMENT=staging
EXPO_PUBLIC_API_URL=https://staging-api.aura.com
```

#### Production:
```bash
# .env.production
EXPO_PUBLIC_ENVIRONMENT=production
EXPO_PUBLIC_API_URL=https://your-railway-url.railway.app
```

### For Backend (Railway)

Add in Railway Dashboard → Environment Variables:

```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET_KEY=your-secret-key
API_SECRET_KEY=your-api-secret
ENVIRONMENT=production
```

---

## 🔒 Security Best Practices

### ✅ DO:
- ✅ Use HTTPS for production
- ✅ Store secrets in environment variables
- ✅ Never commit `.env` files
- ✅ Use different secrets per environment
- ✅ Rotate secrets regularly

### ❌ DON'T:
- ❌ Hardcode API URLs in code
- ❌ Commit `.env` files
- ❌ Share secrets in chat/email
- ❌ Use production secrets in development

---

## 📊 Environment Detection

### Automatic Detection:

```javascript
// Mobile app automatically detects:
1. EXPO_PUBLIC_ENVIRONMENT env var
2. NODE_ENV (development/production)
3. __DEV__ flag (React Native)
4. Build profile (EAS)
```

### Manual Override:

```javascript
// In app.config.js
environment: process.env.EXPO_PUBLIC_ENVIRONMENT || 'production'
```

---

## 🧪 Testing Environments

### Local Testing:
```bash
npm start
# Uses: .env (development)
```

### Staging Testing:
```bash
EXPO_PUBLIC_ENVIRONMENT=staging npm start
# Uses: .env.staging
```

### Production Testing:
```bash
EXPO_PUBLIC_ENVIRONMENT=production npm start
# Uses: .env.production
```

---

## 🔄 Environment Switching

### During Development:
- Auto-detects from `.env` file
- Falls back to development if not set

### During Build:
- EAS Build uses profile-specific env vars
- `preview` profile → staging
- `production` profile → production

### Runtime:
- App checks `Constants.expoConfig.extra.environment`
- Uses appropriate config from `environment.js`

---

## 📋 Checklist

### Development:
- [ ] `.env` file created (from `env.template`)
- [ ] Local API URL configured
- [ ] Backend running locally
- [ ] Logging enabled

### Staging:
- [ ] `.env.staging` file created
- [ ] Staging API deployed
- [ ] Staging API URL configured
- [ ] Analytics enabled

### Production:
- [ ] `.env.production` file created
- [ ] Production API deployed (Railway)
- [ ] Production API URL configured
- [ ] Secrets stored in Railway
- [ ] Analytics enabled
- [ ] Logging disabled

---

## 🎯 Next Steps

1. ✅ Environment files created
2. ⏳ Deploy backend to Railway
3. ⏳ Update production API URL
4. ⏳ Configure Railway environment variables
5. ⏳ Test all environments

---

**Status**: ✅ Environment strategy complete!

*Made with 💎 in Cyprus*

