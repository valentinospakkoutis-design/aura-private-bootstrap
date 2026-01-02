# Environment Variables Setup Guide 🔐

## Overview

This guide explains how to configure environment variables for the AURA app across different environments (development, staging, production).

## Environment Files

### Development
- **Template:** `env.template`
- **Local:** `.env` (not in git)
- **Usage:** Local development and testing

### Staging
- **Template:** `env.staging.template`
- **Local:** `.env.staging` (not in git)
- **Usage:** Pre-production testing and QA

### Production
- **Template:** `env.production.template`
- **Local:** `.env.production` (not in git)
- **Usage:** Live production environment

---

## Quick Setup

### Development
```bash
cp env.template .env
# Edit .env with your local values
```

### Staging
```bash
cp env.staging.template .env.staging
# Edit .env.staging with staging values
```

### Production
```bash
cp env.production.template .env.production
# Edit .env.production with production values
```

---

## EAS Build Profiles

### Development Profile
- **Purpose:** Local development builds
- **Distribution:** Internal
- **Debug:** Enabled
- **Build:** `eas build --platform android --profile development`

### Preview Profile
- **Purpose:** Internal testing builds
- **Distribution:** Internal
- **Debug:** Enabled
- **Build:** `eas build --platform android --profile preview`

### Staging Profile
- **Purpose:** Pre-production testing
- **Distribution:** Internal
- **Debug:** Enabled (for testing)
- **API:** Staging API URL
- **Build:** `eas build --platform android --profile staging`

### Production Profile
- **Purpose:** Live production app
- **Distribution:** Store (App Store / Google Play)
- **Debug:** Disabled
- **API:** Production API URL
- **Build:** `eas build --platform android --profile production`

---

## Environment Variables Reference

### API Configuration

| Variable | Development | Staging | Production |
|----------|-------------|---------|-----------|
| `API_BASE_URL` | `http://localhost:8000` | `https://staging-api.aura.app` | `https://api.aura.app` |
| `WS_URL` | `ws://localhost:8000/ws` | `wss://staging-api.aura.app/ws` | `wss://api.aura.app/ws` |
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | `https://staging-api.aura.app` | `https://api.aura.app` |
| `EXPO_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | `wss://staging-api.aura.app/ws` | `wss://api.aura.app/ws` |

### Feature Flags

| Variable | Development | Staging | Production |
|----------|-------------|---------|-----------|
| `ENABLE_BIOMETRICS` | `true` | `true` | `true` |
| `ENABLE_PUSH_NOTIFICATIONS` | `true` | `true` | `true` |
| `ENABLE_WEBSOCKET` | `true` | `true` | `true` |
| `ENABLE_DARK_MODE` | `true` | `true` | `true` |
| `ENABLE_OFFLINE_MODE` | `true` | `true` | `true` |
| `EXPO_PUBLIC_ENABLE_ANALYTICS` | `false` | `true` | `true` |
| `EXPO_PUBLIC_ENABLE_CRASH_REPORTING` | `false` | `true` | `true` |

### Debug Settings

| Variable | Development | Staging | Production |
|----------|-------------|---------|-----------|
| `DEBUG_MODE` | `true` | `true` | `false` |
| `LOG_LEVEL` | `debug` | `debug` | `error` |
| `EXPO_PUBLIC_ENVIRONMENT` | `development` | `staging` | `production` |
| `NODE_ENV` | `development` | `staging` | `production` |

### Analytics

| Variable | Development | Staging | Production |
|----------|-------------|---------|-----------|
| `SENTRY_DSN` | Not set | Staging DSN | Production DSN |
| `ANALYTICS_ID` | Not set | Staging ID | Production ID |

### App Version

| Variable | Development | Staging | Production |
|----------|-------------|---------|-----------|
| `APP_VERSION` | `1.0.0-dev` | `1.0.0-staging` | `1.0.0` |
| `BUILD_NUMBER` | `1` | `1` | `1` (auto-incremented) |

---

## Staging Environment

### Purpose
Staging environment is used for:
- Pre-production testing
- QA validation
- Client demos
- Integration testing

### Configuration

**API URL:** `https://staging-api.aura.app`  
**WebSocket URL:** `wss://staging-api.aura.app/ws`  
**Environment:** `staging`  
**Debug Mode:** `true` (for testing)  
**Log Level:** `debug`

### Building Staging Build

```bash
# Android
eas build --platform android --profile staging

# iOS
eas build --platform ios --profile staging
```

---

## Production Environment

### Purpose
Production environment is used for:
- Live production app
- App Store / Google Play releases
- End-user access

### Configuration

**API URL:** `https://aura-private-bootstrap-production.up.railway.app`  
**WebSocket URL:** `wss://aura-private-bootstrap-production.up.railway.app/ws`  
**Environment:** `production`  
**Debug Mode:** `false`  
**Log Level:** `error`

### Building Production Build

```bash
# Android
eas build --platform android --profile production

# iOS
eas build --platform ios --profile production
```

---

## Security Best Practices

### ✅ DO:
- Use template files (`.template`) as reference only
- Store actual values in local `.env.*` files (not in git)
- Use EAS secrets for sensitive values
- Use `EXPO_PUBLIC_` prefix only for non-sensitive public variables
- Rotate API keys and secrets regularly
- Use different credentials for each environment

### ❌ DON'T:
- Commit `.env`, `.env.staging`, or `.env.production` to git
- Commit actual API keys or secrets
- Use `EXPO_PUBLIC_` prefix for sensitive data
- Share environment files
- Hardcode secrets in code
- Use production credentials in staging/development

---

## Using EAS Secrets (Recommended)

For sensitive values, use EAS secrets instead of embedding in `eas.json`:

```bash
# Set a secret for staging
eas secret:create --scope project --name SENTRY_DSN_STAGING --value "https://xxx@sentry.io/xxx"

# Set a secret for production
eas secret:create --scope project --name SENTRY_DSN_PRODUCTION --value "https://xxx@sentry.io/xxx"

# List secrets
eas secret:list

# Use in eas.json
{
  "build": {
    "staging": {
      "env": {
        "SENTRY_DSN": "@sentry-dsn-staging"
      }
    },
    "production": {
      "env": {
        "SENTRY_DSN": "@sentry-dsn-production"
      }
    }
  }
}
```

---

## Accessing Variables in Code

### Expo Public Variables

Variables prefixed with `EXPO_PUBLIC_` are available at build time:

```javascript
import Constants from 'expo-constants';

const apiUrl = Constants.expoConfig?.extra?.apiUrl || 
               process.env.EXPO_PUBLIC_API_URL;

const environment = Constants.expoConfig?.extra?.environment ||
                    process.env.EXPO_PUBLIC_ENVIRONMENT;
```

### Runtime Variables

For variables that need to be set at runtime:

```javascript
import Constants from 'expo-constants';

const debugMode = Constants.expoConfig?.extra?.debugMode === 'true';
const logLevel = Constants.expoConfig?.extra?.logLevel || 'info';
```

### Environment Detection

```javascript
import Constants from 'expo-constants';

const isDevelopment = Constants.expoConfig?.extra?.environment === 'development';
const isStaging = Constants.expoConfig?.extra?.environment === 'staging';
const isProduction = Constants.expoConfig?.extra?.environment === 'production';
```

---

## Updating Environment Variables

### For EAS Builds

1. Update `eas.json` for the specific profile (staging/production)
2. Rebuild the app: `eas build --platform android --profile <profile>`

### For Local Development

1. Update `.env`, `.env.staging`, or `.env.production` (local files)
2. Restart Expo dev server: `npx expo start -c`

---

## Verification Checklist

### Staging
- [ ] API URL points to staging server
- [ ] WebSocket URL points to staging server
- [ ] Debug mode enabled
- [ ] Analytics enabled (staging project)
- [ ] Test staging build on device
- [ ] Verify all features work in staging

### Production
- [ ] API URL points to production server
- [ ] WebSocket URL points to production server
- [ ] Debug mode disabled
- [ ] Log level set to error
- [ ] Analytics enabled (production project)
- [ ] Test production build on device
- [ ] Verify all features work in production

---

## Troubleshooting

### Variables Not Available in App

- Ensure variables are prefixed with `EXPO_PUBLIC_` for Expo
- Rebuild the app after changing `eas.json`
- Check `Constants.expoConfig?.extra` for available variables

### Wrong API URL

- Check `eas.json` for the correct profile
- Verify environment variables in the build profile
- Rebuild the app after changes

### Debug Mode Still Enabled in Production

- Set `DEBUG_MODE=false` in production profile
- Set `LOG_LEVEL=error` in production profile
- Rebuild the app

### Staging vs Production Confusion

- Use different API URLs for each environment
- Use different analytics projects
- Use different Sentry projects
- Verify environment in app: `Constants.expoConfig?.extra?.environment`

---

## Quick Reference

### Current Configurations

**Staging:**
- API: `https://staging-api.aura.app`
- WebSocket: `wss://staging-api.aura.app/ws`
- Debug: `true`
- Log Level: `debug`

**Production:**
- API: `https://aura-private-bootstrap-production.up.railway.app`
- WebSocket: `wss://aura-private-bootstrap-production.up.railway.app/ws`
- Debug: `false`
- Log Level: `error`

### Build Commands

```bash
# Development
eas build --platform android --profile development

# Preview
eas build --platform android --profile preview

# Staging
eas build --platform android --profile staging

# Production
eas build --platform android --profile production
```

---

**Last Updated:** 2026-01-02  
**Maintained By:** Development Team

