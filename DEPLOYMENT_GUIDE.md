# Deployment Guide - Backend στο Cloud

## 🎯 Στόχος
Να λειτουργεί το AURA app **χωρίς να είναι ανοιχτός ο υπολογιστής σου**.

## 🚀 Επιλογές Deployment

### 1. **Railway** (Συνιστάται - Εύκολο & Γρήγορο)
- ✅ **Δωρεάν tier:** $5 credit/μήνα
- ✅ **Auto-deploy** από GitHub
- ✅ **Built-in PostgreSQL & Redis**
- ✅ **HTTPS αυτόματα**
- ⏱️ **Setup:** 10-15 λεπτά

### 2. **Render**
- ✅ **Δωρεάν tier:** 750 ώρες/μήνα
- ✅ **Auto-deploy** από GitHub
- ⚠️ **Sleeps** μετά από 15 λεπτά inactivity (δωρεάν tier)
- ⏱️ **Setup:** 10-15 λεπτά

### 3. **Fly.io**
- ✅ **Δωρεάν tier:** 3 VMs
- ✅ **Δεν κοιμάται** (always-on)
- ✅ **Global edge network**
- ⏱️ **Setup:** 15-20 λεπτά

### 4. **DigitalOcean App Platform**
- 💰 **$5/μήνα** (πάντα online)
- ✅ **Auto-deploy** από GitHub
- ✅ **Built-in databases**
- ⏱️ **Setup:** 15-20 λεπτά

### 5. **Heroku**
- 💰 **$7/μήνα** (Eco Dyno)
- ✅ **Πολύ εύκολο setup**
- ⚠️ **Sleeps** μετά από 30 λεπτά (δωρεάν tier δεν υπάρχει πια)
- ⏱️ **Setup:** 10 λεπτά

---

## 📋 Προετοιμασία

### 1. Δημιούργησε `Procfile` για το backend:

```bash
# backend/Procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 2. Δημιούργησε `runtime.txt` (για Python version):

```bash
# backend/runtime.txt
python-3.11.0
```

### 3. Ενημέρωσε `requirements.txt` (αν λείπει κάτι):

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
sqlalchemy==2.0.23
pydantic==2.5.0
python-multipart==0.0.6
jinja2==3.1.2
```

---

## 🚂 Railway Deployment (Συνιστάται)

### Βήμα 1: Δημιούργησε Account
1. Πήγαινε στο [railway.app](https://railway.app)
2. Sign up με GitHub
3. **New Project** → **Deploy from GitHub repo**

### Βήμα 2: Connect Repository
1. Επίλεξε το `aura-private-bootstrap` repo
2. Railway θα detect το backend folder

### Βήμα 3: Configure Service
1. **Root Directory:** `backend`
2. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **Python Version:** 3.11

### Βήμα 4: Add PostgreSQL (Optional)
1. **New** → **Database** → **PostgreSQL**
2. Railway θα δημιουργήσει connection string

### Βήμα 5: Environment Variables
Πρόσθεσε στο Railway dashboard:

```env
# Database (αν χρησιμοποιείς PostgreSQL)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (αν χρειάζεται)
REDIS_URL=${{Redis.REDIS_URL}}

# CORS (για mobile app)
CORS_ORIGINS=*

# Environment
ENVIRONMENT=production
```

### Βήμα 6: Get URL
1. Railway θα δώσει URL: `https://your-app.railway.app`
2. **Copy αυτό το URL**

### Βήμα 7: Update Mobile App
Ενημέρωσε το `mobile/src/config/environment.js`:

```javascript
production: {
  apiUrl: 'https://your-app.railway.app', // ← Railway URL
  // ...
}
```

---

## 🎨 Render Deployment

### Βήμα 1: Δημιούργησε Account
1. Πήγαινε στο [render.com](https://render.com)
2. Sign up με GitHub

### Βήμα 2: New Web Service
1. **New** → **Web Service**
2. Connect το GitHub repo
3. **Root Directory:** `backend`
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Βήμα 3: Environment Variables
```env
ENVIRONMENT=production
CORS_ORIGINS=*
```

### Βήμα 4: Get URL
Render URL: `https://your-app.onrender.com`

⚠️ **Σημείωση:** Στο δωρεάν tier, το service **κοιμάται** μετά από 15 λεπτά inactivity. Το πρώτο request θα πάρει 30-60 δευτερόλεπτα.

---

## ✈️ Fly.io Deployment (Always-On)

### Βήμα 1: Install Fly CLI
```bash
# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

### Βήμα 2: Login
```bash
fly auth login
```

### Βήμα 3: Create Fly App
```bash
cd backend
fly launch
```

### Βήμα 4: Deploy
```bash
fly deploy
```

### Βήμα 5: Get URL
```bash
fly status
# URL: https://your-app.fly.dev
```

---

## 🔧 Configuration για Production

### 1. Update `backend/main.py` για Production:

```python
# backend/main.py
import os

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Update Mobile App Environment:

**Ενημέρωσε `eas.json`:**

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_URL": "https://your-app.railway.app",
        "EXPO_PUBLIC_WS_URL": "wss://your-app.railway.app/ws"
      }
    }
  }
}
```

**Ενημέρωσε `app.config.js`:**

```javascript
extra: {
  apiUrl: process.env.EXPO_PUBLIC_API_URL || 'https://your-app.railway.app',
  wsUrl: process.env.EXPO_PUBLIC_WS_URL || 'wss://your-app.railway.app/ws',
}
```

### 3. Rebuild Mobile App:

```bash
# Development build (για testing)
eas build --profile preview --platform android

# Production build
eas build --profile production --platform android
```

---

## 🧪 Testing Production Backend

### 1. Test API Endpoint:
```bash
curl https://your-app.railway.app/api/ai/predictions
```

### 2. Test από Mobile App:
1. Build app με production environment
2. Install στο device
3. Test όλα τα features

---

## 📊 Monitoring & Logs

### Railway:
- **Dashboard:** railway.app → Project → Logs
- **Metrics:** CPU, Memory, Network

### Render:
- **Dashboard:** render.com → Dashboard → Logs
- **Metrics:** Available στο dashboard

### Fly.io:
```bash
fly logs
fly status
```

---

## 🔒 Security Best Practices

1. **Environment Variables:**
   - Μην commit secrets στο Git
   - Χρησιμοποίησε platform secrets

2. **CORS:**
   - Στο production, περιορίσε origins:
   ```python
   ALLOWED_ORIGINS = [
     "https://aura.app",
     "exp://your-expo-url",
   ]
   ```

3. **HTTPS:**
   - Όλα τα platforms παρέχουν HTTPS αυτόματα

4. **Rate Limiting:**
   - Προσθήκη rate limiting στο backend

---

## 💰 Cost Comparison

| Platform | Free Tier | Paid Tier | Always-On |
|----------|-----------|-----------|-----------|
| Railway | $5 credit | $20+/month | ✅ |
| Render | 750h/month | $7+/month | ⚠️ Sleeps |
| Fly.io | 3 VMs | $1.94/VM | ✅ |
| DigitalOcean | - | $5/month | ✅ |
| Heroku | - | $7/month | ✅ |

---

## 🎯 Συνιστώμενη Λύση

**Για Development/Testing:**
- **Railway** (εύκολο, γρήγορο setup)

**Για Production:**
- **Fly.io** (always-on, global, δωρεάν tier)
- **DigitalOcean** (αν θέλεις πιο πολλά features)

---

## 📝 Next Steps

1. **Επίλεξε platform** (Railway συνιστάται)
2. **Deploy backend** (ακολούθησε τα βήματα)
3. **Get production URL**
4. **Update mobile app** environment
5. **Rebuild mobile app** με production config
6. **Test** όλα τα features

---

## 🆘 Troubleshooting

### Backend δεν απαντάει:
- Ελέγξτε logs στο platform dashboard
- Ελέγξτε environment variables
- Ελέγξτε ότι το PORT variable είναι set

### CORS errors:
- Ενημερώστε `CORS_ORIGINS` environment variable
- Ελέγξτε ότι το mobile app URL είναι allowed

### Database connection errors:
- Ελέγξτε `DATABASE_URL` environment variable
- Ελέγξτε ότι το database service είναι running

---

## 📚 Resources

- [Railway Docs](https://docs.railway.app)
- [Render Docs](https://render.com/docs)
- [Fly.io Docs](https://fly.io/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

