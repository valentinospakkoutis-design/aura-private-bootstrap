# 🚀 AURA Deployment Guide

**Last Updated**: December 2025

---

## 📋 Table of Contents

1. [Environment Configuration](#environment-configuration)
2. [EAS Build Setup](#eas-build-setup)
3. [CI/CD Pipeline](#cicd-pipeline)
4. [Monitoring & Logging](#monitoring--logging)
5. [Production Checklist](#production-checklist)

---

## 🔧 Environment Configuration

### Setup

1. **Copy environment template**:
   ```bash
   cp env.template .env
   ```

2. **Configure environment variables** in `.env`:
   ```env
   EXPO_PUBLIC_ENVIRONMENT=production
   EXPO_PUBLIC_API_URL=https://api.aura.com
   EXPO_PUBLIC_ENABLE_ANALYTICS=true
   EXPO_PUBLIC_ENABLE_CRASH_REPORTING=true
   ```

3. **Environment files**:
   - `.env` - Local development (gitignored)
   - `.env.staging` - Staging environment
   - `.env.production` - Production environment

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EXPO_PUBLIC_ENVIRONMENT` | Environment (development/staging/production) | `development` |
| `EXPO_PUBLIC_API_URL` | Backend API URL | `http://192.168.178.97:8000` |
| `EXPO_PUBLIC_ENABLE_ANALYTICS` | Enable analytics | `false` |
| `EXPO_PUBLIC_ENABLE_CRASH_REPORTING` | Enable crash reporting | `false` |

### Accessing Environment Variables

```javascript
import { config, appInfo } from '../mobile/src/config/environment';

console.log(config.apiUrl);
console.log(config.environment);
console.log(appInfo.version);
```

---

## 📦 EAS Build Setup

### Prerequisites

1. **Install EAS CLI**:
   ```bash
   npm install -g eas-cli
   ```

2. **Login to Expo**:
   ```bash
   eas login
   ```

3. **Configure project**:
   ```bash
   eas build:configure
   ```

### Build Configuration

Create `eas.json`:

```json
{
  "cli": {
    "version": ">= 5.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": {
        "simulator": true
      }
    },
    "preview": {
      "distribution": "internal",
      "ios": {
        "simulator": false
      }
    },
    "production": {
      "distribution": "store",
      "env": {
        "EXPO_PUBLIC_ENVIRONMENT": "production"
      }
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your-apple-id@example.com",
        "ascAppId": "your-app-store-connect-app-id"
      },
      "android": {
        "serviceAccountKeyPath": "./google-service-account.json",
        "track": "production"
      }
    }
  }
}
```

### Building

**Development build**:
```bash
eas build --profile development --platform ios
eas build --profile development --platform android
```

**Preview build**:
```bash
eas build --profile preview --platform all
```

**Production build**:
```bash
eas build --profile production --platform all
```

### OTA Updates

**Publish update**:
```bash
eas update --branch production --message "Bug fixes and improvements"
```

**Check update status**:
```bash
eas update:list
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

Create `.github/workflows/build.yml`:

```yaml
name: Build and Deploy

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm test
      
      - name: Build
        run: |
          npm install -g eas-cli
          eas build --profile production --platform all --non-interactive
        env:
          EXPO_TOKEN: ${{ secrets.EXPO_TOKEN }}
```

### Environment Secrets

Add to GitHub Secrets:
- `EXPO_TOKEN` - Expo access token
- `APPLE_ID` - Apple Developer account
- `APPLE_APP_SPECIFIC_PASSWORD` - App-specific password
- `GOOGLE_SERVICE_ACCOUNT` - Google Play service account JSON

---

## 📊 Monitoring & Logging

### Sentry Setup

1. **Install Sentry**:
   ```bash
   npm install @sentry/react-native
   ```

2. **Configure Sentry** in `app.config.js`:
   ```javascript
   extra: {
     sentryDsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
   }
   ```

3. **Initialize Sentry** in `app/_layout.js`:
   ```javascript
   import * as Sentry from '@sentry/react-native';
   
   if (!__DEV__) {
     Sentry.init({
       dsn: config.sentryDsn,
       environment: config.environment,
     });
   }
   ```

### Analytics

**Firebase Analytics** (optional):
```bash
npm install @react-native-firebase/analytics
```

**Custom Analytics**:
```javascript
import { features } from '../mobile/src/config/environment';

if (features.enableAnalytics) {
  // Track events
  analytics.track('screen_view', { screen_name: 'Home' });
}
```

---

## ✅ Production Checklist

### Pre-Deployment

- [ ] All environment variables configured
- [ ] API endpoints tested
- [ ] Security audit completed
- [ ] Performance testing done
- [ ] Error handling verified
- [ ] Offline mode tested
- [ ] Form validation tested
- [ ] Encryption working correctly

### Build

- [ ] EAS build configuration complete
- [ ] iOS certificates configured
- [ ] Android keystore configured
- [ ] App icons and splash screens ready
- [ ] Version numbers updated

### Submission

- [ ] App Store Connect configured
- [ ] Google Play Console configured
- [ ] Privacy policy URL added
- [ ] Terms of service URL added
- [ ] App screenshots prepared
- [ ] App description written
- [ ] Keywords optimized

### Post-Deployment

- [ ] Monitoring enabled
- [ ] Crash reporting active
- [ ] Analytics tracking
- [ ] OTA updates configured
- [ ] Backup strategy in place

---

## 🔐 Security Checklist

- [ ] API keys encrypted
- [ ] Environment variables secure
- [ ] No hardcoded secrets
- [ ] SSL/TLS enabled
- [ ] Rate limiting configured
- [ ] Input validation active
- [ ] Error messages sanitized

---

## 📱 Platform-Specific Notes

### iOS

- **Bundle Identifier**: `com.valentinospakkoutisdesign.aura`
- **Minimum iOS Version**: 13.0
- **App Store Categories**: Finance, Productivity

### Android

- **Package Name**: `com.valentinospakkoutisdesign.aura`
- **Minimum SDK**: 21 (Android 5.0)
- **Target SDK**: 34
- **Play Store Categories**: Finance, Productivity

---

## 🆘 Troubleshooting

### Build Issues

**"No credentials found"**:
```bash
eas credentials
```

**"Build failed"**:
- Check EAS build logs
- Verify environment variables
- Check app.json configuration

### Update Issues

**"Update not showing"**:
- Check branch name matches
- Verify update channel
- Check app version compatibility

---

## 📚 Resources

- [EAS Build Documentation](https://docs.expo.dev/build/introduction/)
- [EAS Update Documentation](https://docs.expo.dev/eas-update/introduction/)
- [Expo Environment Variables](https://docs.expo.dev/guides/environment-variables/)
- [Sentry React Native](https://docs.sentry.io/platforms/react-native/)

---

**Status**: ✅ Ready for Production  
**Last Updated**: December 2025

*Made with 💎 in Cyprus*

