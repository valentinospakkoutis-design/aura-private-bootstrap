# 🌐 Web Development Guide - AURA

## 🚀 Starting Web Development

Το `npm run web` έχει ξεκινήσει! 🎉

---

## 📋 What Happens

1. **Metro Bundler** starts for web
2. **Browser** opens automatically (usually)
3. **Development server** runs on `http://localhost:8081` (or similar)
4. **Hot reload** enabled - changes auto-refresh

---

## 🌐 Access Your App

### Automatic
Το browser θα ανοίξει αυτόματα με την app.

### Manual
Αν δεν ανοίξει, άνοιξε:
```
http://localhost:8081
```

---

## 🎨 Web-Specific Features

### ✅ Works on Web:
- ✅ All React Native components (via react-native-web)
- ✅ Navigation (Expo Router)
- ✅ Styling
- ✅ API calls
- ✅ Theme (Dark/Light mode)
- ✅ Animations

### ⚠️ Limited on Web:
- ⚠️ Haptics (not available on web)
- ⚠️ Some native modules (device-specific)
- ⚠️ SecureStore (uses localStorage fallback)

---

## 🔧 Development Commands

| Command | Description |
|---------|-------------|
| `npm run web` | Start web development server |
| `npm start` | Start Expo (choose platform) |
| `npm start -- --web` | Start Expo with web option |

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Kill process on port 8081
npx kill-port 8081

# Or use different port
npx expo start --web --port 8082
```

### Clear Cache

```bash
npx expo start --web --clear
```

### Browser Not Opening

- Manually open: `http://localhost:8081`
- Check terminal for actual URL
- Try different browser

---

## 🎯 Web Development Tips

### 1. Responsive Design
- Test different screen sizes
- Use browser DevTools (F12)
- Check mobile view (Ctrl+Shift+M)

### 2. Performance
- Check Network tab for API calls
- Monitor console for errors
- Use React DevTools extension

### 3. Testing
- Test all screens
- Check navigation
- Verify API connections
- Test theme toggle

---

## 📱 Web vs Mobile Differences

| Feature | Web | Mobile |
|---------|-----|--------|
| Haptics | ❌ No | ✅ Yes |
| SecureStore | ⚠️ localStorage | ✅ Secure |
| Native Modules | ⚠️ Limited | ✅ Full |
| Performance | ⚠️ Slower | ✅ Faster |
| Offline | ⚠️ Limited | ✅ Full |

---

## 🔍 Debugging

### Browser DevTools
- **F12**: Open DevTools
- **Console**: See logs and errors
- **Network**: Monitor API calls
- **Elements**: Inspect DOM

### React DevTools
Install browser extension:
- Chrome: https://chrome.google.com/webstore/detail/react-developer-tools
- Firefox: https://addons.mozilla.org/en-US/firefox/addon/react-devtools/

---

## ✅ Testing Checklist

- [ ] App loads in browser
- [ ] Navigation works
- [ ] All screens render
- [ ] API calls work (if backend running)
- [ ] Theme toggle works
- [ ] Responsive design works
- [ ] No console errors
- [ ] Performance is acceptable

---

## 🎉 Quick Start

1. **Web server**: Already running! ✅
2. **Browser**: Should open automatically
3. **Start coding**: Changes auto-refresh!

---

## 📚 Useful Links

- **Expo Web**: https://docs.expo.dev/workflow/web/
- **React Native Web**: https://necolas.github.io/react-native-web/
- **Metro Bundler**: https://metrobundler.dev/

---

**Your app should be opening in the browser now! 🚀**

*Made with 💎 in Cyprus*

