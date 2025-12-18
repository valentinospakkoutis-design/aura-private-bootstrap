# 🔐 Expo Login Options

## ⚠️ Login is Interactive

Το `eas login` χρειάζεται **manual input** (email/password) στο terminal σου.

---

## 📋 Login Methods

### Method 1: Interactive Login (Recommended)

**Run in YOUR terminal:**
```bash
eas login
```

Θα σου ζητήσει:
- Email or username
- Password

---

### Method 2: Browser Login

```bash
eas login --web
```

Αυτό θα ανοίξει browser για login.

---

### Method 3: Use Access Token (Non-Interactive)

Αν θέλεις να αποφύγεις το interactive login:

1. **Get Token**:
   - Go to: https://expo.dev/accounts/[username]/settings/access-tokens
   - Click "Create Token"
   - Copy the token

2. **Set Environment Variable**:
   ```powershell
   # Windows PowerShell
   $env:EXPO_TOKEN="your-token-here"
   ```

3. **Build** (no login needed):
   ```bash
   npm run build:android:preview
   ```

---

## 🚀 Quick Start

**Easiest way:**

1. Open terminal in project directory
2. Run: `eas login`
3. Enter credentials
4. Run: `npm run build:android:preview`

---

## 📝 Create Account

Αν δεν έχεις Expo account:

1. Visit: https://expo.dev/signup
2. Create free account
3. Verify email
4. Run: `eas login`

---

## ✅ Verify Login

After login, verify:
```bash
eas whoami
```

Should show your username/email.

---

**Next Step**: Run `eas login` in your terminal! 🚀

