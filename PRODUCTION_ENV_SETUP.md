# Production Environment Variables Setup 🔐

## Overview

This guide explains how to configure production environment variables for the AURA app.

## Files

### 1. `env.production.template`
Template file with all production environment variables. **DO NOT commit actual values to git.**

### 2. `eas.json`
Contains production environment variables for EAS builds. These are embedded in the build.

### 3. `.env.production` (local file - not in git)
Your actual production environment variables. Create this file locally and never commit it.

---

## Setup Instructions

### Step 1: Create Local Production Environment File

```bash
# Copy the template
cp env.production.template .env.production

# Edit with your actual values
# Use a secure editor (not in git)
```

### Step 2: Update `env.production.template` Values

Edit `.env.production` and replace placeholder values:

```bash
# API Configuration
API_BASE_URL=https://api.aura.app  # Your actual production API URL
WS_URL=wss://api.aura.app/ws        # Your actual WebSocket URL

# Analytics
SENTRY_DSN=https://your-actual-sentry-dsn@sentry.io/project-id
ANALYTICS_ID=your-actual-analytics-id

# App Version
APP_VERSION=1.0.0  # Update for each release
BUILD_NUMBER=1    # Increment for each build
```

### Step 3: Update `eas.json` Production Environment

The `eas.json` file already contains production environment variables. Update these if needed:

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_ENVIRONMENT": "production",
        "NODE_ENV": "production",
        "EXPO_PUBLIC_API_URL": "https://aura-private-bootstrap-production.up.railway.app",
        "EXPO_PUBLIC_WS_URL": "wss://aura-private-bootstrap-production.up.railway.app/ws",
        // ... other variables
      }
    }
  }
}
```

**Important:** Variables prefixed with `EXPO_PUBLIC_` are embedded in the build and accessible in the app.

---

## Environment Variables Reference

### API Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `API_BASE_URL` | Production API base URL | `https://api.aura.app` |
| `WS_URL` | WebSocket URL for real-time updates | `wss://api.aura.app/ws` |
| `EXPO_PUBLIC_API_URL` | Expo public API URL (embedded in build) | `https://api.aura.app` |
| `EXPO_PUBLIC_WS_URL` | Expo public WebSocket URL (embedded in build) | `wss://api.aura.app/ws` |

### Feature Flags

| Variable | Description | Production Value |
|----------|-------------|------------------|
| `ENABLE_BIOMETRICS` | Enable biometric authentication | `true` |
| `ENABLE_PUSH_NOTIFICATIONS` | Enable push notifications | `true` |
| `ENABLE_WEBSOCKET` | Enable WebSocket connections | `true` |
| `ENABLE_DARK_MODE` | Enable dark mode | `true` |
| `ENABLE_OFFLINE_MODE` | Enable offline mode | `true` |
| `EXPO_PUBLIC_ENABLE_ANALYTICS` | Enable analytics tracking | `true` |
| `EXPO_PUBLIC_ENABLE_CRASH_REPORTING` | Enable crash reporting | `true` |

### Debug Settings

| Variable | Description | Production Value |
|----------|-------------|------------------|
| `DEBUG_MODE` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `error` |

### Analytics

| Variable | Description | Example |
|----------|-------------|---------|
| `SENTRY_DSN` | Sentry DSN for error tracking | `https://xxx@sentry.io/xxx` |
| `ANALYTICS_ID` | Analytics tracking ID | `UA-XXXXXXXXX-X` |

### App Version

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_VERSION` | App version (semantic versioning) | `1.0.0` |
| `BUILD_NUMBER` | Build number (increment for each build) | `1` |

---

## Security Best Practices

### ✅ DO:
- Use `.env.production.template` as a template only
- Store actual values in `.env.production` (local, not in git)
- Use EAS secrets for sensitive values
- Use `EXPO_PUBLIC_` prefix only for non-sensitive public variables
- Rotate API keys and secrets regularly

### ❌ DON'T:
- Commit `.env.production` to git
- Commit actual API keys or secrets
- Use `EXPO_PUBLIC_` prefix for sensitive data
- Share production environment files
- Hardcode secrets in code

---

## Using EAS Secrets (Recommended)

For sensitive values, use EAS secrets instead of embedding in `eas.json`:

```bash
# Set a secret
eas secret:create --scope project --name SENTRY_DSN --value "https://xxx@sentry.io/xxx"

# List secrets
eas secret:list

# Use in eas.json
{
  "build": {
    "production": {
      "env": {
        "SENTRY_DSN": "@sentry-dsn"  # References EAS secret
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
```

### Runtime Variables

For variables that need to be set at runtime, use `expo-constants`:

```javascript
import Constants from 'expo-constants';

const debugMode = Constants.expoConfig?.extra?.debugMode === 'true';
```

---

## Updating Production Variables

### For EAS Builds

1. Update `eas.json` production `env` section
2. Rebuild the app: `eas build --platform android --profile production`

### For Local Development

1. Update `.env.production` (local file)
2. Restart Expo dev server: `npx expo start -c`

---

## Verification

After setting up production environment variables:

1. ✅ Verify API URL is correct
2. ✅ Verify WebSocket URL is correct
3. ✅ Verify debug mode is disabled
4. ✅ Verify analytics are enabled
5. ✅ Test production build locally (if possible)
6. ✅ Verify environment variables in production build

---

## Troubleshooting

### Variables Not Available in App

- Ensure variables are prefixed with `EXPO_PUBLIC_` for Expo
- Rebuild the app after changing `eas.json`
- Check `Constants.expoConfig?.extra` for available variables

### Wrong API URL

- Check `eas.json` production `env` section
- Verify Railway URL is correct
- Rebuild the app after changes

### Debug Mode Still Enabled

- Set `DEBUG_MODE=false` in `eas.json`
- Set `LOG_LEVEL=error` in `eas.json`
- Rebuild the app

---

## Quick Reference

### Current Production Configuration

**API URL:** `https://aura-private-bootstrap-production.up.railway.app`  
**WebSocket URL:** `wss://aura-private-bootstrap-production.up.railway.app/ws`  
**Environment:** `production`  
**Debug Mode:** `false`  
**Log Level:** `error`

---

**Last Updated:** 2026-01-02  
**Maintained By:** Development Team

