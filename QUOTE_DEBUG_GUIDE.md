# 🐛 Quote of Day Debugging Guide

## 🔍 Problem: Το γνωμικό δεν λειτουργεί

### ✅ Fixes Applied

1. **Improved Error Handling**: Το component τώρα δείχνει fallback quote αν το API fails
2. **Better Data Structure Handling**: Υποστηρίζει διαφορετικές δομές δεδομένων
3. **Debug Logging**: Προσθήκη console logs για debugging

---

## 🔧 Troubleshooting Steps

### 1. Check Backend is Running

Το API endpoint είναι: `GET /api/quote-of-day`

**Test manually:**
```bash
# Αν το backend τρέχει στο localhost:8000
curl http://localhost:8000/api/quote-of-day

# Ή στο browser
http://localhost:8000/api/quote-of-day
```

**Expected Response:**
```json
{
  "quote": {
    "id": 1,
    "el": "Η υπομονή είναι το κλειδί του παραδείσου. Και του πλούτου.",
    "en": "Patience is the key to paradise. And to wealth.",
    "author": "",
    "category": "general"
  },
  "index": 0,
  "total_quotes": 4,
  "date": "2025-12-17"
}
```

### 2. Check API URL Configuration

**File**: `mobile/src/config/environment.js`

**Default Development URL**: `http://192.168.178.97:8000`

**For Web Development**:
- Αν τρέχεις στο browser, το URL μπορεί να είναι `http://localhost:8000`
- Update το `environment.js` αν χρειάζεται

### 3. Check Browser Console

**Open DevTools (F12)** και δες:
- **Console tab**: Για errors και debug logs
- **Network tab**: Για API calls

**Look for:**
- `DailyQuote Error:` - Αν υπάρχει error
- `DailyQuote Data:` - Αν υπάρχει data
- Network requests to `/api/quote-of-day`

### 4. CORS Issues (Web Only)

Αν τρέχεις στο web browser, μπορεί να υπάρχει CORS issue.

**Check backend CORS config** (`backend/main.py`):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. Network Issues

**For Web**:
- Make sure backend is accessible from browser
- Check if `localhost:8000` works
- Try `127.0.0.1:8000` instead

**For Mobile (Expo Go)**:
- Make sure phone and computer are on same WiFi
- Use computer's local IP (not localhost)
- Check firewall settings

---

## 🎯 Current Behavior

### ✅ What Works Now:

1. **Loading State**: Shows spinner while fetching
2. **Error Handling**: Shows fallback quote on error
3. **Fallback Quote**: Always shows something, even if API fails
4. **Debug Logging**: Console logs in development mode

### 📋 Component Logic:

1. **Loading**: Shows spinner
2. **Error/No Data**: Shows fallback quote
3. **Success**: Shows API quote
4. **Always**: Shows something (never blank)

---

## 🔍 Debug Checklist

- [ ] Backend is running (`http://localhost:8000`)
- [ ] API endpoint works (`/api/quote-of-day`)
- [ ] API URL is correct in `environment.js`
- [ ] No CORS errors in browser console
- [ ] Network tab shows API call
- [ ] Console shows debug logs
- [ ] Component shows fallback quote (if API fails)

---

## 🚀 Quick Fixes

### Fix 1: Update API URL for Web

**File**: `mobile/src/config/environment.js`

```javascript
development: {
  apiUrl: typeof window !== 'undefined' 
    ? 'http://localhost:8000'  // Web
    : 'http://192.168.178.97:8000',  // Mobile
  // ...
}
```

### Fix 2: Start Backend

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Fix 3: Check Backend Health

```bash
curl http://localhost:8000/health
```

---

## 📊 Expected Console Output

**Success:**
```
DailyQuote Data: {
  quote: { id: 1, el: "...", en: "..." },
  index: 0,
  total_quotes: 4,
  date: "2025-12-17"
}
```

**Error:**
```
DailyQuote Error: Error: Failed to fetch
```

---

## ✅ Current Status

Το component τώρα:
- ✅ Always shows something (fallback if needed)
- ✅ Handles errors gracefully
- ✅ Logs debug info in development
- ✅ Supports multiple data structures

**Even if the API doesn't work, you'll see a quote!**

---

## 🎯 Next Steps

1. **Check browser console** for errors
2. **Verify backend is running**
3. **Test API endpoint directly**
4. **Check network tab** for API calls

**The component will always show a quote, even if the API fails!**

---

*Made with 💎 in Cyprus*

