# 🚀 Build APK - Execute Now

## ⚠️ Important: Login Required

Το `eas login` είναι **interactive** και χρειάζεται να το τρέξεις **manually** στο terminal σου.

---

## 📋 Step-by-Step Instructions

### Step 1: Open Terminal
Άνοιξε το terminal (PowerShell, CMD, ή Terminal) στο project directory:
```
C:\Users\vpakk\Desktop\Coding\aura-private-bootstrap
```

### Step 2: Login to Expo
```bash
eas login
```

Θα σου ζητήσει:
- **Email or username**: [Enter your Expo email]
- **Password**: [Enter your password]

**Αν δεν έχεις account:**
1. Πήγαινε στο: https://expo.dev/signup
2. Δημιούργησε account (free)
3. Επιστρέψε και τρέξε `eas login`

### Step 3: Build APK
Μετά το successful login, τρέξε:
```bash
npm run build:android:preview
```

---

## ⏱️ Build Process

1. **Upload**: Το code θα upload στο Expo servers (~2-3 min)
2. **Build**: Το APK θα φτιαχτεί στο cloud (~10-15 min)
3. **Complete**: Θα λάβεις notification όταν είναι ready

---

## 📥 After Build Completes

### Download APK

**Option 1: Command Line**
```bash
npm run build:download
```

**Option 2: Web Dashboard**
1. Go to: https://expo.dev
2. Login με το account σου
3. Navigate to "Projects" → "aura"
4. Click "Builds"
5. Download το APK

---

## 🔄 Alternative: Use EXPO_TOKEN (Non-Interactive)

Αν θέλεις να αυτοματοποιήσεις (για CI/CD):

1. **Get Token**:
   - Go to: https://expo.dev/accounts/[username]/settings/access-tokens
   - Create new token
   - Copy token

2. **Set Environment Variable**:
   ```powershell
   # Windows PowerShell
   $env:EXPO_TOKEN="your-token-here"
   ```

3. **Build**:
   ```bash
   npm run build:android:preview
   ```

---

## ✅ Quick Commands

```bash
# 1. Login (interactive - run manually)
eas login

# 2. Build
npm run build:android:preview

# 3. Check status
npm run build:status

# 4. Download
npm run build:download
```

---

## 🐛 Troubleshooting

### "Not logged in"
→ Run `eas login` first

### "Build failed"
→ Check logs: `eas build:list`
→ Verify all dependencies installed: `npm install`

### "No credentials found"
→ Run: `eas credentials` (will auto-generate)

---

## 📱 Install APK on Device

1. Transfer APK to Android device
2. Enable "Install from unknown sources"
3. Open APK file
4. Install

---

**Status**: ✅ Ready - Just need manual login  
**Next**: Run `eas login` in your terminal

*Made with 💎 in Cyprus*

