// Expo App Configuration
// Supports environment variables via .env files

export default {
  expo: {
    name: "AURA",
    slug: "aura",
    version: "1.0.0",
    orientation: "portrait",
    userInterfaceStyle: "dark",
    newArchEnabled: true,
    scheme: "aura",
    splash: {
      backgroundColor: "#0a0a0a",
      resizeMode: "contain"
    },
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.valentinospakkoutisdesign.aura"
    },
    android: {
      package: "com.valentinospakkoutisdesign.aura",
      backgroundColor: "#0a0a0a",
      versionCode: 1,
      // adaptiveIcon: {
      //   foregroundImage: "./assets/adaptive-icon.png",
      //   backgroundColor: "#0a0a0a"
      // },
      permissions: [
        "INTERNET",
        "ACCESS_NETWORK_STATE",
        "VIBRATE"
      ]
    },
    web: {
      bundler: "metro"
    },
    plugins: [
      "expo-router",
      "expo-secure-store"
      // Note: expo-haptics doesn't need plugin config, works at runtime
    ],
    updates: {
      url: "https://u.expo.dev/8e6aeafd-b2a9-41b2-a06d-5b55044ec68d"
    },
    runtimeVersion: {
      policy: "appVersion"
    },
    extra: {
      // EAS Project ID
      eas: {
        projectId: "8e6aeafd-b2a9-41b2-a06d-5b55044ec68d"
      },
      // Environment variables from .env files
      // Access via Constants.expoConfig.extra
      environment: process.env.EXPO_PUBLIC_ENVIRONMENT || (process.env.NODE_ENV !== 'production' ? 'development' : 'production'),
      // API URL: Set via environment variable or use production default
      // For standalone builds, this should be your production API URL
      apiUrl: process.env.EXPO_PUBLIC_API_URL || (process.env.NODE_ENV === 'production' ? 'https://api.aura.com' : undefined),
      enableAnalytics: process.env.EXPO_PUBLIC_ENABLE_ANALYTICS === 'true',
      enableCrashReporting: process.env.EXPO_PUBLIC_ENABLE_CRASH_REPORTING === 'true',
    }
  }
};

