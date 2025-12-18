# ⚡ Quick Build Commands

## Γρήγορη Εγκατάσταση & Build

### 1. Login (Μόνο πρώτη φορά)
```bash
eas login
```

### 2. Build APK (Preview)
```bash
eas build --platform android --profile preview
```

### 3. Check Build Status
```bash
eas build:list
```

### 4. Download APK
```bash
eas build:download
```

---

## 🎯 One-Liner (μετά το login)

```bash
eas build --platform android --profile preview && eas build:download
```

---

## 📝 Notes

- **First build**: ~10-15 λεπτά
- **Subsequent builds**: ~5-10 λεπτά (με cache)
- **APK location**: Downloads folder ή current directory

---

**Ready to build!** 🚀

