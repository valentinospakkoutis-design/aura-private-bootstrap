# AURA App Testing Checklist 🧪

## Phase 1: Unit Testing

### UI Components
- [ ] Button - all variants (primary, secondary, ghost, gradient, danger)
- [ ] Button - all sizes (small, medium, large)
- [ ] Button - loading state
- [ ] Button - disabled state
- [ ] LoadingSpinner - small and large sizes
- [ ] LoadingSpinner - fullScreen mode
- [ ] Toast - all types (success, error, warning, info)
- [ ] Toast - auto-hide after duration
- [ ] Modal - open/close
- [ ] Modal - confirm/cancel actions

### Empty States
- [ ] NoPredictions - displays correctly
- [ ] NoTrades - displays correctly
- [ ] NoVoiceBriefing - displays correctly
- [ ] NoBrokerConnected - displays correctly
- [ ] NoData - retry functionality
- [ ] NoInternet - retry functionality

---

## Phase 2: Integration Testing

### API Integration
- [ ] Login - successful
- [ ] Login - failed (wrong credentials)
- [ ] Logout - clears token
- [ ] Get predictions - returns data
- [ ] Get predictions - handles empty response
- [ ] Get brokers - returns data
- [ ] Connect broker - successful
- [ ] Connect broker - invalid credentials
- [ ] Disconnect broker - successful
- [ ] Get trades - returns data
- [ ] Upload voice sample - successful
- [ ] Get voice briefing - returns audio URL

### State Management (Zustand)
- [ ] User state - set/get
- [ ] Brokers state - add/remove
- [ ] Predictions state - set/get
- [ ] Toast state - show/hide
- [ ] Modal state - show/hide
- [ ] Loading state - set/get
- [ ] Error state - set/get

---

## Phase 3: Screen Testing

### AI Predictions Screen
- [ ] Loading state displays
- [ ] Empty state displays when no predictions
- [ ] Predictions list displays correctly
- [ ] Pull-to-refresh works
- [ ] Tap prediction navigates to details
- [ ] Error state displays on API failure
- [ ] Retry works after error

### Paper Trading Screen
- [ ] Loading state displays
- [ ] Empty state displays when no trades
- [ ] Stats card displays correctly
- [ ] Trades list displays correctly
- [ ] Pull-to-refresh works
- [ ] Close trade shows confirmation modal
- [ ] Close trade updates list
- [ ] Navigate to live trading works

### Voice Briefing Screen
- [ ] Empty state displays when no voice
- [ ] Recording starts correctly
- [ ] Recording stops at 30 seconds
- [ ] Recording duration updates
- [ ] Upload voice sample works
- [ ] Play briefing works
- [ ] Stop briefing works
- [ ] Microphone permission requested

### Settings Screen
- [ ] Profile info displays correctly
- [ ] Risk profile modal opens
- [ ] Risk profile updates successfully
- [ ] Toggle notifications works
- [ ] Toggle biometrics works
- [ ] Toggle paper trading shows warning
- [ ] Logout shows confirmation
- [ ] Delete account shows double confirmation

### Brokers Screen
- [ ] Loading state displays
- [ ] Available brokers list displays
- [ ] Connect modal opens
- [ ] API key validation works
- [ ] Connect broker successful
- [ ] Connect broker failed - shows error
- [ ] Disconnect broker shows confirmation
- [ ] Disconnect broker successful
- [ ] Credentials stored securely

---

## Phase 4: Error Handling

### Network Errors
- [ ] No internet - shows NoInternet component
- [ ] Timeout - shows error message
- [ ] 401 Unauthorized - redirects to login
- [ ] 403 Forbidden - shows error message
- [ ] 404 Not Found - shows error message
- [ ] 500 Server Error - shows error message
- [ ] Network retry works

### Input Validation
- [ ] Empty API key - shows error
- [ ] Invalid API key format - shows error
- [ ] Empty email - shows error
- [ ] Invalid email format - shows error
- [ ] Weak password - shows error
- [ ] Invalid trade amount - shows error

### Edge Cases
- [ ] App works with slow network
- [ ] App handles large data sets
- [ ] App handles rapid button taps
- [ ] App handles background/foreground transitions
- [ ] App handles memory warnings

---

## Phase 5: Security Testing

### Authentication
- [ ] Token stored securely (SecureStore)
- [ ] Token cleared on logout
- [ ] Expired token handled correctly
- [ ] Biometric authentication works (if enabled)

### Data Protection
- [ ] API credentials encrypted
- [ ] Sensitive data not logged in production
- [ ] No credentials in error messages
- [ ] HTTPS only for API calls

---

## Phase 6: Performance Testing

### Load Times
- [ ] App launches < 2 seconds
- [ ] Screens load < 1 second
- [ ] API calls complete < 3 seconds
- [ ] Images load progressively

### Memory Usage
- [ ] No memory leaks on navigation
- [ ] Large lists use FlatList (virtualized)
- [ ] Images optimized and cached
- [ ] Animations run at 60 FPS

### Battery Usage
- [ ] No excessive background activity
- [ ] Location services off when not needed
- [ ] Network calls batched when possible

---

## Phase 7: User Experience

### Navigation
- [ ] Back button works correctly
- [ ] Deep links work (if implemented)
- [ ] Tab navigation smooth
- [ ] Modal dismisses correctly

### Feedback
- [ ] Loading indicators show during waits
- [ ] Success messages clear and helpful
- [ ] Error messages clear and actionable
- [ ] Haptic feedback on interactions

### Accessibility
- [ ] Text readable at all sizes
- [ ] Buttons large enough to tap
- [ ] Color contrast sufficient
- [ ] Screen reader compatible (basic)

---

## Phase 8: Device Testing

### iOS
- [ ] iPhone 12/13/14/15 (various sizes)
- [ ] iPad (if supported)
- [ ] iOS 15, 16, 17

### Android
- [ ] Samsung Galaxy S21/S22/S23
- [ ] Google Pixel 6/7/8
- [ ] Various screen sizes
- [ ] Android 11, 12, 13, 14

---

## Phase 9: Production Readiness

### Configuration
- [ ] Environment variables set correctly
- [ ] API base URL points to production
- [ ] Analytics configured
- [ ] Error tracking configured (Sentry/Bugsnag)
- [ ] Push notifications configured

### App Store
- [ ] App icon set (all sizes)
- [ ] Splash screen configured
- [ ] App name and description ready
- [ ] Screenshots prepared
- [ ] Privacy policy URL ready
- [ ] Terms of service URL ready

### Compliance
- [ ] GDPR compliance checked
- [ ] CySEC compliance checked (Cyprus)
- [ ] User data handling documented
- [ ] Disclaimers added for trading risks

---

## Sign-off

- [ ] All critical tests passed
- [ ] All high-priority bugs fixed
- [ ] Performance acceptable
- [ ] Security audit passed
- [ ] Ready for beta testing
- [ ] Ready for production release

**Tested by:** _________________  
**Date:** _________________  
**Version:** _________________

