# AURA Testing Checklist

## ✅ Mobile App Testing

### Navigation Testing
- [ ] Home screen loads correctly
- [ ] Settings screen accessible from Home
- [ ] Profile screen accessible from Home and Settings
- [ ] Back button works on all screens
- [ ] Header titles correct on all screens

### Home Screen
- [ ] Greeting shows correct time-based message (Καλημέρα/Καλησπέρα)
- [ ] System Status card displays correctly
- [ ] Daily Quote loads (with fallback if API fails)
- [ ] Stats cards show 0 values initially
- [ ] All buttons are clickable
- [ ] Scroll works smoothly

### Settings Screen
- [ ] All sections display correctly
- [ ] Switches toggle properly
- [ ] Navigation to Profile works
- [ ] All menu items are tappable
- [ ] Logout button visible

### Profile Screen
- [ ] Avatar displays
- [ ] User info shows correctly
- [ ] Stats cards display
- [ ] Risk profile card shows
- [ ] Navigation to Settings works
- [ ] All buttons work

### Performance
- [ ] App starts within 3 seconds
- [ ] Navigation is instant (< 300ms)
- [ ] Scrolling is smooth (60fps)
- [ ] No memory leaks
- [ ] Works on low-end devices

### Error Handling
- [ ] Graceful handling when backend is offline
- [ ] Fallback quote displays if API fails
- [ ] No app crashes on errors
- [ ] Error messages are user-friendly in Greek

## ✅ Backend Testing

### Endpoints
- [ ] GET / returns status
- [ ] GET /health returns health check
- [ ] GET /api/quote-of-day returns quote
- [ ] GET /api/stats returns stats
- [ ] GET /api/system-status returns status

### CORS
- [ ] Mobile app can connect to backend
- [ ] No CORS errors in console

### Error Handling
- [ ] Returns proper error codes
- [ ] Error messages are clear
- [ ] No server crashes

## ✅ Integration Testing

### API Connection
- [ ] Mobile successfully connects to backend
- [ ] Quote fetching works
- [ ] Loading states display correctly
- [ ] Error states display correctly

## 🐛 Known Issues

### To Fix:
1. Backend not running by default (needs manual start)
2. API connection requires localhost (needs deployment)
3. Quotes.json has only 1 quote (needs 365)

### Future Improvements:
1. Add proper error logging
2. Add analytics
3. Add offline mode
4. Add data persistence

