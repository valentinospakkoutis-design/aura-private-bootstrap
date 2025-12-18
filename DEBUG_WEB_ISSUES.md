# 🐛 Web Development Debugging

## 🔍 Common Issues in Browser DevTools

### Issue: `__DEV__ is not defined`

**Problem**: Στο web browser, το `__DEV__` μπορεί να μην είναι defined.

**Fix Applied**: Changed to safe check:
```javascript
const isDev = typeof __DEV__ !== 'undefined' ? __DEV__ : process.env.NODE_ENV !== 'production';
```

---

## 📋 How to Debug

### 1. Check Console Tab

**Open Console** (F12 → Console tab)

**Look for:**
- Red errors
- Yellow warnings
- Debug logs (if enabled)

### 2. Check Sources Tab

**Open Sources** (F12 → Sources tab)

**Look for:**
- Red X badges (errors)
- File names with errors
- Breakpoints

### 3. Check Network Tab

**Open Network** (F12 → Network tab)

**Look for:**
- Failed requests (red)
- API calls to `/api/quote-of-day`
- CORS errors

---

## 🔧 Quick Fixes

### Fix 1: `__DEV__` Error

**Already Fixed**: Changed to safe check in `DailyQuote.js`

### Fix 2: Console Errors

**Check Console tab** for specific errors:
- Click on error to see details
- Check file and line number
- Look for stack trace

### Fix 3: Network Errors

**Check Network tab**:
- Filter by "XHR" or "Fetch"
- Look for failed requests
- Check response status codes

---

## 🎯 Current Status

- ✅ `__DEV__` check fixed in `DailyQuote.js`
- ✅ Safe development mode detection
- ✅ Debug logging works in web

---

## 📊 Expected Console Output

**If API works:**
```
DailyQuote Data: { quote: {...}, index: 0, ... }
```

**If API fails:**
```
DailyQuote Error: Error: Failed to fetch
```

**Component will show fallback quote in both cases!**

---

## ✅ Next Steps

1. **Refresh browser** (Ctrl+R or F5)
2. **Check Console tab** for errors
3. **Check Network tab** for API calls
4. **Verify quote appears** (even if API fails)

---

*Made with 💎 in Cyprus*

