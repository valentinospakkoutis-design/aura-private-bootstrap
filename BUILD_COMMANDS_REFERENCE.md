# Build Commands Reference 🚀

## Setup

### Install EAS CLI
```bash
npm install -g eas-cli
```

### Verify Installation
```bash
eas --version
```

### Login to EAS
```bash
eas login
```

### Logout
```bash
eas logout
```

### Check Login Status
```bash
eas whoami
```

---

## Project Setup

### Initialize EAS in Project
```bash
eas init
```

### Configure EAS Project
```bash
eas build:configure
```

### Link Project to EAS
```bash
eas project:init
```

---

## Build Commands

### Development Builds

#### Android Development
```bash
eas build --platform android --profile development
```

#### iOS Development (Simulator)
```bash
eas build --platform ios --profile development
```

#### Both Platforms
```bash
eas build --platform all --profile development
```

### Preview Builds

#### Android Preview
```bash
eas build --platform android --profile preview
```

#### iOS Preview
```bash
eas build --platform ios --profile preview
```

#### Both Platforms
```bash
eas build --platform all --profile preview
```

### Staging Builds

#### Android Staging
```bash
eas build --platform android --profile staging
```

#### iOS Staging
```bash
eas build --platform ios --profile staging
```

#### Both Platforms
```bash
eas build --platform all --profile staging
```

### Production Builds

#### Android Production (AAB for Google Play)
```bash
eas build --platform android --profile production
```

#### iOS Production (IPA for App Store)
```bash
eas build --platform ios --profile production
```

#### Both Platforms
```bash
eas build --platform all --profile production
```

---

## Build Options

### Non-Interactive Mode
```bash
eas build --platform android --profile production --non-interactive
```

### No Wait (Background Build)
```bash
eas build --platform android --profile production --no-wait
```

### Local Build (Requires Native Tools)
```bash
eas build --platform android --profile production --local
```

### Clear Cache
```bash
eas build --platform android --profile production --clear-cache
```

### Specific Channel
```bash
eas build --platform android --profile staging --channel staging
```

### Message for Build
```bash
eas build --platform android --profile production --message "Production build v1.0.0"
```

### Combined Options
```bash
eas build --platform android --profile production --non-interactive --no-wait --clear-cache
```

---

## Build Management

### List All Builds
```bash
eas build:list
```

### List Builds for Platform
```bash
eas build:list --platform android
eas build:list --platform ios
```

### List Builds for Profile
```bash
eas build:list --profile production
```

### View Build Details
```bash
eas build:view <build-id>
```

### View Latest Build
```bash
eas build:view
```

### Download Build
```bash
eas build:download <build-id>
```

### Download Latest Build
```bash
eas build:download
```

### Download to Specific Directory
```bash
eas build:download <build-id> --output ./builds/
```

### Cancel Build
```bash
eas build:cancel <build-id>
```

### Retry Build
```bash
eas build:retry <build-id>
```

---

## Credentials Management

### View Credentials
```bash
eas credentials
```

### View iOS Credentials
```bash
eas credentials --platform ios
```

### View Android Credentials
```bash
eas credentials --platform android
```

### Setup Credentials
```bash
eas credentials --platform android
eas credentials --platform ios
```

### Update Credentials
```bash
eas credentials --platform android --update
```

### Remove Credentials
```bash
eas credentials --platform android --remove
```

---

## Submit to Stores

### Submit to Google Play
```bash
eas submit --platform android --profile production
```

### Submit to App Store
```bash
eas submit --platform ios --profile production
```

### Submit Latest Build
```bash
eas submit --platform android
```

### Submit Specific Build
```bash
eas submit --platform android --id <build-id>
```

### Submit Options
```bash
# Non-interactive
eas submit --platform android --non-interactive

# Latest build only
eas submit --platform android --latest

# No wait
eas submit --platform android --no-wait
```

---

## Updates (OTA)

### Publish Update
```bash
eas update --branch production --message "Bug fixes and improvements"
```

### Publish to Staging
```bash
eas update --branch staging --message "Staging update"
```

### Publish to Preview
```bash
eas update --branch preview --message "Preview update"
```

### Publish with Channel
```bash
eas update --channel production --message "Production update"
```

### List Updates
```bash
eas update:list
```

### View Update
```bash
eas update:view <update-id>
```

### Delete Update
```bash
eas update:delete <update-id>
```

### Rollback Update
```bash
eas update:rollback
```

---

## Environment Variables

### Set Secret
```bash
eas secret:create --scope project --name API_KEY --value "your-api-key"
```

### Set Secret for Profile
```bash
eas secret:create --scope project --name SENTRY_DSN --value "your-dsn" --type string
```

### List Secrets
```bash
eas secret:list
```

### Delete Secret
```bash
eas secret:delete --name API_KEY
```

### View Secret
```bash
eas secret:view --name API_KEY
```

---

## Project Management

### View Project Info
```bash
eas project:info
```

### View Project Settings
```bash
eas project:settings
```

### Link to Different Project
```bash
eas project:link
```

---

## Account Management

### View Account Info
```bash
eas account:view
```

### Switch Account
```bash
eas account:switch
```

### View Organizations
```bash
eas organization:list
```

---

## Common Workflows

### Development Workflow

```bash
# 1. Make code changes
git add .
git commit -m "Feature: Add new feature"

# 2. Build development version
eas build --platform android --profile development

# 3. Test on device
# Download and install APK

# 4. Iterate
# Make more changes and repeat
```

### Staging Workflow

```bash
# 1. Build staging version
eas build --platform android --profile staging

# 2. Wait for build to complete
eas build:list

# 3. Download and test
eas build:download

# 4. If approved, proceed to production
```

### Production Workflow

```bash
# 1. Build production version
eas build --platform android --profile production

# 2. Wait for build
eas build:list

# 3. Download and verify
eas build:download

# 4. Submit to store
eas submit --platform android --profile production

# 5. Monitor submission
# Check Google Play Console / App Store Connect
```

### Update Workflow (OTA)

```bash
# 1. Make code changes (no native changes)
git add .
git commit -m "Fix: Bug fix"

# 2. Publish OTA update
eas update --branch production --message "Bug fix"

# 3. Users get update automatically
# No need to rebuild or resubmit
```

### Full Release Workflow

```bash
# 1. Update version in app.config.js
# version: "1.0.1"

# 2. Build production
eas build --platform all --profile production

# 3. Wait for builds
eas build:list

# 4. Test builds
eas build:download

# 5. Submit to stores
eas submit --platform android --profile production
eas submit --platform ios --profile production

# 6. Monitor submissions
# Check store consoles
```

---

## Troubleshooting

### Build Fails

```bash
# 1. Check build logs
eas build:view <build-id>

# 2. Check credentials
eas credentials --platform android

# 3. Clear cache and retry
eas build --platform android --profile production --clear-cache

# 4. Check environment variables
# Verify in eas.json
```

### Credentials Issues

```bash
# 1. View current credentials
eas credentials --platform android

# 2. Setup new credentials
eas credentials --platform android

# 3. Remove and recreate
eas credentials --platform android --remove
eas credentials --platform android
```

### Submission Fails

```bash
# 1. Check build status
eas build:view <build-id>

# 2. Verify build is complete
eas build:list

# 3. Check submission configuration
# Verify in eas.json submit section

# 4. Retry submission
eas submit --platform android --id <build-id>
```

---

## Quick Reference

### Most Common Commands

```bash
# Build for production
eas build --platform android --profile production

# Submit to store
eas submit --platform android --profile production

# Publish OTA update
eas update --branch production --message "Update message"

# List builds
eas build:list

# Download latest build
eas build:download
```

### Build Profiles

| Profile | Use Case | Distribution |
|---------|----------|--------------|
| `development` | Local dev | Internal |
| `preview` | Internal testing | Internal |
| `staging` | Pre-production | Internal |
| `production` | Store release | Store |

### Platform Options

| Option | Description |
|--------|-------------|
| `--platform android` | Android only |
| `--platform ios` | iOS only |
| `--platform all` | Both platforms |

### Common Flags

| Flag | Description |
|------|-------------|
| `--non-interactive` | No prompts |
| `--no-wait` | Don't wait for completion |
| `--clear-cache` | Clear build cache |
| `--local` | Build locally |
| `--message` | Build message |

---

## Environment-Specific Commands

### Development
```bash
# Build
eas build --platform android --profile development

# Update
eas update --branch development --message "Dev update"
```

### Preview
```bash
# Build
eas build --platform android --profile preview

# Update
eas update --branch preview --message "Preview update"
```

### Staging
```bash
# Build
eas build --platform android --profile staging

# Update
eas update --branch staging --message "Staging update"
```

### Production
```bash
# Build
eas build --platform android --profile production

# Submit
eas submit --platform android --profile production

# Update
eas update --branch production --message "Production update"
```

---

## Tips & Best Practices

### ✅ DO:
- Use `--non-interactive` in CI/CD
- Use `--no-wait` for long builds
- Use `--clear-cache` if builds fail unexpectedly
- Test staging builds before production
- Use OTA updates for non-native changes
- Monitor build status regularly
- Keep credentials secure

### ❌ DON'T:
- Don't commit credentials
- Don't skip staging builds
- Don't submit without testing
- Don't use production profile for testing
- Don't ignore build warnings
- Don't skip OTA updates when possible

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: EAS Build

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm install -g eas-cli
      - run: eas login --non-interactive
        env:
          EXPO_TOKEN: ${{ secrets.EXPO_TOKEN }}
      - run: eas build --platform android --profile production --non-interactive --no-wait
```

### Environment Variables for CI/CD

```bash
# Set in CI/CD secrets
EXPO_TOKEN=your-expo-token
```

---

## Additional Resources

- **EAS Documentation:** https://docs.expo.dev/eas/
- **EAS Build Docs:** https://docs.expo.dev/eas/build/
- **EAS Submit Docs:** https://docs.expo.dev/eas/submit/
- **EAS Update Docs:** https://docs.expo.dev/eas/update/

---

**Last Updated:** 2026-01-02  
**Maintained By:** Development Team

