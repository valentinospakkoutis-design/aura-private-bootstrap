# 🌐 Πώς να Βρεις το Railway URL

## 📍 Location 1: Settings → Networking

1. **Railway Dashboard** → Project → **Settings**
2. Κάνε click στο **"Networking"** tab (αριστερά)
3. Βρες το **"Public Domain"** section
4. Θα δεις το URL, π.χ.:
   ```
   aura-private-bootstrap-production.up.railway.app
   ```

---

## 📍 Location 2: Service Overview

1. **Railway Dashboard** → Project
2. Κάνε click στο service **"aura-private-bootstrap"**
3. Στο **top header**, δίπλα στο όνομα, θα δεις το URL
4. Ή στο **"Details"** tab, θα δεις το **"Public Domain"**

---

## 📍 Location 3: Deployments Tab

1. **Railway Dashboard** → Project → **Deployments**
2. Κάνε click στο **latest deployment**
3. Στο **"Details"** section, θα δεις το **"Public Domain"**

---

## ✅ Το URL που χρειάζεσαι

Το URL θα είναι κάτι σαν:
```
https://aura-private-bootstrap-production.up.railway.app
```

**Σημαντικό:** Χρησιμοποίησε το **full URL με `https://`** στο `eas.json`!

---

## 🔧 Πού να το βάλεις

Μετά που θα πάρεις το Railway URL, θα το βάλεις στο:

**File:** `eas.json`
**Section:** `production` profile
**Field:** `EXPO_PUBLIC_API_URL`

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_URL": "https://aura-private-bootstrap-production.up.railway.app"
      }
    }
  }
}
```

---

## 🎯 Quick Steps

1. ✅ Railway Dashboard → Settings → Networking
2. ✅ Copy το **Public Domain** URL
3. ✅ Update το `eas.json` με το URL
4. ✅ Κάνε rebuild του APK

---

## ⚠️ Important

- Χρησιμοποίησε **`https://`** (όχι `http://`)
- Μην βάλεις trailing slash (`/`) στο τέλος
- Το URL πρέπει να είναι **publicly accessible** (δηλαδή το Railway service να είναι **Online**)

---

## 🆘 Αν Δεν Βλέπεις URL

Αν δεν βλέπεις Public Domain:
1. Ελέγξε ότι το service είναι **Online** (όχι Crashed)
2. Ελέγξε το **Networking** tab → μπορεί να χρειάζεται να κάνεις click **"Generate Domain"**
3. Αν δεν υπάρχει, κάνε click **"Generate Domain"** ή **"Add Domain"**
