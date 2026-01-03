// Expo App Configuration
// Supports environment variables via .env files

export default {
  expo: {
    name: "AURA",
    slug: "aura",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "automatic",
    newArchEnabled: true,
    scheme: "aura",
    splash: {
      image: "./assets/splash.png",
      resizeMode: "contain",
      backgroundColor: "#6366F1"
    },
    assetBundlePatterns: [
      "**/*"
    ],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.aura.app",
      buildNumber: "1",
      infoPlist: {
        NSFaceIDUsageDescription: "We use Face ID to securely authenticate you and protect your financial data.",
        NSCameraUsageDescription: "We need camera access to update your profile picture.",
        NSMicrophoneUsageDescription: "We need microphone access to record your voice for personalized briefings.",
        NSPhotoLibraryUsageDescription: "We need photo library access to update your profile picture.",
        UIBackgroundModes: ["remote-notification"],
        ITSAppUsesNonExemptEncryption: false
      },
      associatedDomains: ["applinks:aura.app"],
      usesAppleSignIn: false
    },
    android: {
      jsEngine: "hermes",
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#6366F1"
      },
      package: "com.aura.app",
      backgroundColor: "#6366F1",
      versionCode: 1,
      permissions: [
        "USE_BIOMETRIC",
        "USE_FINGERPRINT",
        "CAMERA",
        "RECORD_AUDIO",
        "READ_EXTERNAL_STORAGE",
        "WRITE_EXTERNAL_STORAGE",
        "INTERNET",
        "ACCESS_NETWORK_STATE"
      ],
      intentFilters: [
        {
          action: "VIEW",
          autoVerify: true,
          data: [
            {
              scheme: "https",
              host: "aura.app",
              pathPrefix: "/"
            }
          ],
          category: ["BROWSABLE", "DEFAULT"]
        }
      ]
    },
    web: {
      favicon: "./assets/favicon.png",
      bundler: "metro"
    },
    plugins: [
      [
        "expo-notifications",
        {
          icon: "./assets/notification-icon.png",
          color: "#6366F1"
        }
      ],
      "expo-router",
      "expo-secure-store"
    ],
    updates: {
      url: "https://u.expo.dev/8e6aeafd-b2a9-41b2-a06d-5b55044ec68d"
    },
    runtimeVersion: "1.0.0",
    extra: {
      // EAS Project ID
      eas: {
        projectId: "8e6aeafd-b2a9-41b2-a06d-5b55044ec68d"
      },
      // Environment variables from .env files
      // Access via Constants.expoConfig.extra
      environment: process.env.EXPO_PUBLIC_ENVIRONMENT || (process.env.NODE_ENV !== 'production' ? 'development' : 'production'),
      // API URL: Set via environment variable from eas.json or use production default
      // For standalone builds, this should be your production API URL
      // EAS build sets EXPO_PUBLIC_API_URL from eas.json env variables
      apiUrl: process.env.EXPO_PUBLIC_API_URL || (process.env.NODE_ENV === 'production' ? 'https://web-production-5a28a.up.railway.app' : undefined),
      wsUrl: process.env.EXPO_PUBLIC_WS_URL || (process.env.NODE_ENV === 'production' ? 'wss://web-production-5a28a.up.railway.app/ws' : undefined),
      enableAnalytics: process.env.EXPO_PUBLIC_ENABLE_ANALYTICS === 'true',
      enableCrashReporting: process.env.EXPO_PUBLIC_ENABLE_CRASH_REPORTING === 'true',
    },
    owner: process.env.EXPO_OWNER || undefined
  }
};

