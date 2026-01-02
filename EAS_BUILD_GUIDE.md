# EAS Build Configuration Guide 🚀

## Overview

This guide explains the EAS build profiles configured in `eas.json` and how to use them for different deployment scenarios.

---

## Build Profiles

### 1. Development Profile

**Purpose:** Local development and testing with Expo Go or development client.

**Configuration:**
- **Distribution:** Internal
- **Development Client:** Enabled
- **iOS:** Simulator builds, Debug configuration
- **Android:** APK build type
- **Environment:** Development

**Build Commands:**
```bash
# Android
eas build --platform android --profile development

# iOS (simulator)
eas build --platform ios --profile development
```

**Use Cases:**
- Local development
- Testing new features
- Debug builds
- Quick iteration

---

### 2. Preview Profile

**Purpose:** Internal testing builds for team members and stakeholders.

**Configuration:**
- **Distribution:** Internal
- **iOS:** Release configuration, no simulator
- **Android:** APK build type
- **Environment:** Preview
- **Channel:** `preview`

**Build Commands:**
```bash
# Android
eas build --platform android --profile preview

# iOS
eas build --platform ios --profile preview
```

**Use Cases:**
- Internal testing
- Stakeholder demos
- Pre-release validation
- Team feedback

---

### 3. Staging Profile

**Purpose:** Pre-production testing with staging API and full feature set.

**Configuration:**
- **Distribution:** Internal
- **iOS:** Release configuration, `m-medium` resource class
- **Android:** APK build type, Release gradle command
- **Environment:** Staging
- **Channel:** `staging`
- **API:** `https://staging-api.aura.app`
- **WebSocket:** `wss://staging-api.aura.app/ws`
- **Debug Mode:** Enabled (for testing)
- **Log Level:** `debug`

**Build Commands:**
```bash
# Android
eas build --platform android --profile staging

# iOS
eas build --platform ios --profile staging
```

**Use Cases:**
- Pre-production testing
- QA validation
- Integration testing
- Client demos
- Performance testing

**Environment Variables:**
- All feature flags enabled
- Staging API endpoints
- Debug mode enabled for troubleshooting

---

### 4. Production Profile

**Purpose:** Live production builds for App Store and Google Play.

**Configuration:**
- **Distribution:** Store (App Store / Google Play)
- **Auto Increment:** Enabled (version numbers auto-increment)
- **iOS:** Release configuration, `m-medium` resource class, auto-increment
- **Android:** AAB build type (required for Google Play), Release gradle command, auto-increment
- **Environment:** Production
- **Channel:** `production`
- **API:** `https://aura-private-bootstrap-production.up.railway.app`
- **WebSocket:** `wss://aura-private-bootstrap-production.up.railway.app/ws`
- **Debug Mode:** Disabled
- **Log Level:** `error`

**Build Commands:**
```bash
# Android (AAB for Google Play)
eas build --platform android --profile production

# iOS (IPA for App Store)
eas build --platform ios --profile production
```

**Use Cases:**
- App Store submission
- Google Play submission
- Production releases
- End-user distribution

**Environment Variables:**
- All feature flags enabled
- Production API endpoints
- Debug mode disabled
- Error-level logging only

---

## Build Types

### Android Build Types

| Build Type | Use Case | Distribution |
|------------|----------|--------------|
| `apk` | Development, Preview, Staging | Internal |
| `aab` | Production (Google Play) | Store |

**Note:** Google Play requires AAB (Android App Bundle) format for production releases.

### iOS Build Types

| Build Configuration | Use Case | Distribution |
|---------------------|----------|--------------|
| `Debug` | Development | Internal |
| `Release` | Preview, Staging, Production | Internal / Store |

---

## Resource Classes

### iOS Resource Classes

| Resource Class | Description | Use Case |
|----------------|-------------|----------|
| `m-medium` | Medium resources | Staging, Production |
| `m-large` | Large resources | Large apps |
| `m1-medium` | M1 Mac medium | Faster builds |

**Current Configuration:**
- **Staging:** `m-medium`
- **Production:** `m-medium`

---

## Auto Increment

### Production Profile

Both iOS and Android production builds have `autoIncrement: true`:
- **iOS:** Build number increments automatically
- **Android:** Version code increments automatically

**Manual Override:**
```bash
# iOS
eas build --platform ios --profile production --non-interactive --no-wait

# Android
eas build --platform android --profile production --non-interactive --no-wait
```

---

## Channels

Channels are used for OTA (Over-The-Air) updates:

| Profile | Channel | Purpose |
|---------|---------|---------|
| Preview | `preview` | Preview updates |
| Staging | `staging` | Staging updates |
| Production | `production` | Production updates |

**Publishing Updates:**
```bash
# Staging
eas update --branch staging --message "Staging update"

# Production
eas update --branch production --message "Production update"
```

---

## Submit Configuration

### Production Submission

The `submit` section configures automatic submission to app stores:

**iOS:**
```json
{
  "ios": {
    "appleId": "your-apple-id@email.com",
    "ascAppId": "your-asc-app-id",
    "appleTeamId": "your-apple-team-id"
  }
}
```

**Android:**
```json
{
  "android": {
    "serviceAccountKeyPath": "./google-play-service-account.json",
    "track": "production"
  }
}
```

**Submit Commands:**
```bash
# iOS
eas submit --platform ios --profile production

# Android
eas submit --platform android --profile production
```

**Setup Required:**

1. **iOS:**
   - Apple ID
   - App Store Connect App ID
   - Apple Team ID

2. **Android:**
   - Google Play Service Account JSON key
   - Service account with Play Console access

---

## Environment Variables

### Development
- `APP_ENV=development`
- `EXPO_PUBLIC_ENVIRONMENT=development`
- `NODE_ENV=development`

### Preview
- `APP_ENV=preview`
- `EXPO_PUBLIC_ENVIRONMENT=preview`
- `NODE_ENV=preview`

### Staging
- `APP_ENV=staging`
- `EXPO_PUBLIC_ENVIRONMENT=staging`
- `NODE_ENV=staging`
- `API_BASE_URL=https://staging-api.aura.app`
- `WS_URL=wss://staging-api.aura.app/ws`
- All feature flags enabled
- `DEBUG_MODE=true`
- `LOG_LEVEL=debug`

### Production
- `APP_ENV=production`
- `EXPO_PUBLIC_ENVIRONMENT=production`
- `NODE_ENV=production`
- `API_BASE_URL=https://aura-private-bootstrap-production.up.railway.app`
- `WS_URL=wss://aura-private-bootstrap-production.up.railway.app/ws`
- All feature flags enabled
- `DEBUG_MODE=false`
- `LOG_LEVEL=error`

---

## Build Workflow

### Typical Workflow

1. **Development**
   ```bash
   eas build --platform android --profile development
   ```

2. **Preview** (after feature complete)
   ```bash
   eas build --platform android --profile preview
   ```

3. **Staging** (before production)
   ```bash
   eas build --platform android --profile staging
   ```

4. **Production** (for release)
   ```bash
   eas build --platform android --profile production
   eas submit --platform android --profile production
   ```

---

## Build Status

### Check Build Status
```bash
# List all builds
eas build:list

# View specific build
eas build:view <build-id>

# Download build
eas build:download <build-id>
```

---

## Troubleshooting

### Build Fails

1. **Check logs:**
   ```bash
   eas build:view <build-id>
   ```

2. **Verify credentials:**
   ```bash
   eas credentials
   ```

3. **Check environment variables:**
   - Ensure all required variables are set
   - Verify API URLs are correct

### Android AAB Build Issues

- Ensure `buildType: "aab"` for production
- Verify `gradleCommand: ":app:bundleRelease"`
- Check Google Play Console for requirements

### iOS Build Issues

- Verify Apple Developer account
- Check provisioning profiles
- Ensure certificates are valid

---

## Best Practices

### ✅ DO:
- Use development profile for local testing
- Use preview profile for internal demos
- Use staging profile for pre-production testing
- Use production profile only for releases
- Test staging builds before production
- Verify environment variables before building
- Use auto-increment for production builds
- Submit to stores after successful builds

### ❌ DON'T:
- Don't use production profile for testing
- Don't skip staging builds
- Don't hardcode API URLs
- Don't commit credentials
- Don't submit without testing
- Don't use APK for Google Play production

---

## Quick Reference

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
eas build --platform ios --profile production
```

### Submit Commands
```bash
# Production
eas submit --platform android --profile production
eas submit --platform ios --profile production
```

### Update Commands
```bash
# Staging
eas update --branch staging --message "Update message"

# Production
eas update --branch production --message "Update message"
```

---

**Last Updated:** 2026-01-02  
**Maintained By:** Development Team

