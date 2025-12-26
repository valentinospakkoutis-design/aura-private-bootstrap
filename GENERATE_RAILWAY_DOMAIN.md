# 🌐 Generate Railway Public Domain - Step by Step

## 📋 What You See

Στο Railway Dashboard → Settings → Networking:
- ✅ "Public Networking" section
- ✅ Input field για port (τώρα έχει 8080)
- ✅ "Generate Domain" button

---

## ✅ Step-by-Step Instructions

### **Step 1: Change Port to 8000**

1. **Find the input field** που λέει "Enter the port your app is listening on"
2. **Change the port** από `8080` σε `8000`
   - Το FastAPI/uvicorn τρέχει στο port 8000 (ή $PORT που δίνει το Railway)
   - **Important:** Το Railway δίνει το port μέσω environment variable `$PORT`
   - Αλλά για το domain generation, χρησιμοποίησε `8000` ή `$PORT`

### **Step 2: Generate Domain**

1. **Click the purple "Generate Domain" button** (με το lightning bolt icon ⚡)
2. Railway θα δημιουργήσει ένα public URL
3. Θα εμφανιστεί το URL κάπου στο page

### **Step 3: Copy the URL**

1. **Find the generated URL**
   - Θα είναι κάτι σαν: `https://aura-private-bootstrap-production.up.railway.app`
2. **Click the copy icon** (📋) δίπλα στο URL
3. **Save it** - αυτό είναι το Production API URL!

---

## ⚠️ Important Notes

### **About the Port:**

Το Railway δίνει το port μέσω `$PORT` environment variable. Το uvicorn το χρησιμοποιεί:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**For domain generation:**
- Μπορείς να βάλεις `8000` (default FastAPI port)
- Ή `$PORT` (αν το Railway το υποστηρίζει)
- Το Railway θα route-άρει σωστά ανεξάρτητα

---

## 🧪 After Generating Domain

1. **Test the URL:**
   ```
   https://your-generated-url.railway.app/health
   ```

2. **Expected response:**
   ```json
   {"status": "ok"}
   ```

3. **If you see this, it works!** ✅

---

## 📝 Quick Checklist

- [ ] Changed port from 8080 to 8000 (or $PORT)
- [ ] Clicked "Generate Domain" button
- [ ] Copied the generated URL
- [ ] Tested URL in browser (should return `{"status": "ok"}`)

---

## 🎯 Next Steps

After you get the URL:

1. **Send me the URL** - θα ενημερώσω το `eas.json`
2. **Rebuild APK** - με το production URL
3. **Test APK** - verify everything works

---

*Made with 💎 in Cyprus*

