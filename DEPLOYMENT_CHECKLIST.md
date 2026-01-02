# AURA App - Deployment Checklist 🚀

## Pre-Deployment Tasks

### Code Quality
- [ ] All TypeScript errors resolved
- [ ] No console.log statements in production code
- [ ] All TODO comments addressed
- [ ] Code reviewed and tested
- [ ] Git repository clean (no uncommitted changes)

### Configuration
- [ ] Environment variables configured for production
- [ ] API endpoints point to production URLs
- [ ] WebSocket URL updated for production
- [ ] Debug mode disabled
- [ ] Logging level set to 'error' or 'warn'

### Assets
- [ ] App icon created (1024x1024 PNG)
- [ ] Splash screen created
- [ ] Adaptive icon for Android
- [ ] Notification icon
- [ ] All images optimized

### Testing
- [ ] All features tested on iOS
- [ ] All features tested on Android
- [ ] Tested on multiple device sizes
- [ ] Tested offline mode
- [ ] Tested push notifications
- [ ] Tested biometric authentication
- [ ] Tested dark mode
- [ ] Performance tested (60 FPS animations)

### Legal & Compliance
- [ ] Privacy Policy written and published
- [ ] Terms of Service written and published
- [ ] GDPR compliance verified
- [ ] Age rating determined
- [ ] App Store guidelines reviewed
- [ ] Google Play policies reviewed

### Backend
- [ ] Production API deployed and tested
- [ ] WebSocket server running
- [ ] Database configured and backed up
- [ ] SSL certificates installed
- [ ] Rate limiting configured
- [ ] Monitoring and logging set up

---

## Build Configuration

### EAS Build Setup
- [ ] EAS account created and logged in (`eas login`)
- [ ] `eas.json` configured with production profile
- [ ] Production environment variables set in `eas.json`
- [ ] API URL set to production Railway URL
- [ ] Version number incremented
- [ ] Build number incremented

### Android Build
- [ ] Android keystore generated or existing one configured
- [ ] Package name verified (`com.aura.app`)
- [ ] Permissions reviewed and necessary only
- [ ] ProGuard rules configured (if needed)
- [ ] Hermes engine enabled
- [ ] Tested APK/AAB on physical device

### iOS Build
- [ ] Apple Developer account active
- [ ] Bundle identifier verified (`com.aura.app`)
- [ ] Provisioning profiles configured
- [ ] Certificates installed
- [ ] App Store Connect app created
- [ ] Tested IPA on physical device

---

## Environment Variables

### Production `.env` (or EAS secrets)
- [ ] `EXPO_PUBLIC_ENVIRONMENT=production`
- [ ] `EXPO_PUBLIC_API_URL=https://aura-private-bootstrap-production.up.railway.app`
- [ ] `WS_URL=wss://aura-private-bootstrap-production.up.railway.app/ws`
- [ ] `EXPO_PUBLIC_ENABLE_ANALYTICS=true`
- [ ] `EXPO_PUBLIC_ENABLE_CRASH_REPORTING=true`
- [ ] `DEBUG_MODE=false`
- [ ] `LOG_LEVEL=error`

### Backend Environment (Railway)
- [ ] `DATABASE_URL` configured
- [ ] `SECRET_KEY` set (strong random string)
- [ ] `CORS_ORIGINS` set to production domains
- [ ] `ENVIRONMENT=production`
- [ ] `LOG_LEVEL=error`

---

## App Store Submission (iOS)

### App Store Connect
- [ ] App created in App Store Connect
- [ ] App information completed (name, subtitle, description)
- [ ] Screenshots uploaded (all required sizes)
- [ ] App preview video (optional)
- [ ] Keywords and categories set
- [ ] Support URL configured
- [ ] Privacy Policy URL added
- [ ] Age rating completed

### App Review Information
- [ ] Demo account credentials provided (if needed)
- [ ] Review notes added
- [ ] Contact information provided
- [ ] Export compliance information completed

### Build Submission
- [ ] Production build uploaded via EAS
- [ ] Build selected in App Store Connect
- [ ] Version and build number match
- [ ] Submission for review initiated

---

## Google Play Submission (Android)

### Google Play Console
- [ ] App created in Google Play Console
- [ ] App details completed (title, short description, full description)
- [ ] Graphic assets uploaded (icon, feature graphic, screenshots)
- [ ] Content rating questionnaire completed
- [ ] Privacy Policy URL added
- [ ] Target audience and content set
- [ ] Data safety section completed

### Store Listing
- [ ] App icon (512x512 PNG)
- [ ] Feature graphic (1024x500)
- [ ] Screenshots (at least 2, up to 8)
- [ ] Promotional video (optional)
- [ ] Short description (80 characters)
- [ ] Full description (4000 characters)

### Build Submission
- [ ] Production AAB uploaded via EAS
- [ ] Version code incremented
- [ ] Release notes added
- [ ] Rollout percentage set (start with 20% for staged rollout)
- [ ] Submission for review initiated

---

## Post-Deployment

### Monitoring
- [ ] Crash reporting active (Sentry or alternative)
- [ ] Analytics tracking active
- [ ] Error logs monitored
- [ ] Performance metrics tracked
- [ ] User feedback collection set up

### Communication
- [ ] Release notes prepared
- [ ] Update notification sent to users (if applicable)
- [ ] Support team notified
- [ ] Marketing team notified

### Verification
- [ ] App downloaded from App Store (iOS)
- [ ] App downloaded from Google Play (Android)
- [ ] All features working in production
- [ ] API calls successful
- [ ] WebSocket connection working
- [ ] Push notifications working
- [ ] Offline mode working
- [ ] Dark mode working

---

## Rollback Plan

### If Issues Detected
- [ ] Rollback procedure documented
- [ ] Previous version available
- [ ] Database migration rollback plan
- [ ] API versioning strategy (if needed)
- [ ] Communication plan for users

---

## Security Checklist

### App Security
- [ ] API keys stored securely (not in code)
- [ ] Authentication tokens encrypted
- [ ] Biometric data handled securely
- [ ] Sensitive data encrypted at rest
- [ ] HTTPS only for API calls
- [ ] Certificate pinning (if applicable)

### Backend Security
- [ ] API rate limiting enabled
- [ ] CORS properly configured
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] Input validation on all endpoints
- [ ] Authentication tokens expire properly
- [ ] Password hashing (bcrypt/argon2)

---

## Performance Optimization

### App Performance
- [ ] Bundle size optimized (< 50MB for Android, < 100MB for iOS)
- [ ] Images optimized and compressed
- [ ] Code splitting implemented
- [ ] Lazy loading for heavy components
- [ ] Animations run at 60 FPS
- [ ] Memory leaks checked
- [ ] Battery usage optimized

### Backend Performance
- [ ] Database queries optimized
- [ ] Caching implemented
- [ ] CDN configured (if applicable)
- [ ] Response times < 200ms
- [ ] WebSocket connection efficient

---

## Documentation

### Developer Documentation
- [ ] README.md updated
- [ ] API documentation complete
- [ ] Architecture diagram created
- [ ] Deployment guide written
- [ ] Troubleshooting guide written

### User Documentation
- [ ] In-app help/tutorial
- [ ] FAQ section
- [ ] Support contact information
- [ ] Feature documentation

---

## Final Checks

### Before Final Submission
- [ ] All checkboxes above completed
- [ ] Code reviewed by at least one other person
- [ ] Tested on both iOS and Android
- [ ] Tested on multiple devices
- [ ] All known bugs fixed
- [ ] Performance acceptable
- [ ] Security audit passed
- [ ] Legal review completed

### Launch Day
- [ ] App approved by App Store (iOS)
- [ ] App approved by Google Play (Android)
- [ ] Release scheduled or immediate
- [ ] Monitoring dashboards ready
- [ ] Support team ready
- [ ] Marketing materials ready

---

## Quick Reference

### EAS Commands
```bash
# Login to EAS
eas login

# Build for production
eas build --platform android --profile production
eas build --platform ios --profile production

# Submit to stores
eas submit --platform android
eas submit --platform ios

# Check build status
eas build:list
```

### Railway Commands
```bash
# Deploy backend
railway up

# View logs
railway logs

# Check status
railway status
```

### Version Management
- **Version**: Semantic versioning (e.g., 1.0.0)
- **Build Number**: Increment for each build (iOS)
- **Version Code**: Increment for each build (Android)

---

## Notes

- Update this checklist as you complete items
- Keep a record of any issues encountered during deployment
- Document any workarounds or special configurations needed
- Review and update this checklist after each deployment

---

**Last Updated**: 2026-01-02  
**Next Review**: Before next deployment

