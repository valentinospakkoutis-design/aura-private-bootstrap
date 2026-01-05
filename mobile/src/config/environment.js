// Environment Configuration
// Manages environment variables and API URLs

import Constants from 'expo-constants';

// Get environment from expo-constants
const getEnvironment = () => {
  // Check if we have environment variables from .env
  const env = Constants.expoConfig?.extra || {};
  
  // Fallback to __DEV__ if no env vars
  if (env.environment) {
    return env.environment;
  }
  
  // Use __DEV__ if available (React Native), otherwise check NODE_ENV
  if (typeof __DEV__ !== 'undefined') {
    return __DEV__ ? 'development' : 'production';
  }
  
  return process.env.NODE_ENV === 'development' ? 'development' : 'production';
};

// Environment configuration
const ENVIRONMENTS = {
  development: {
    apiUrl: 'http://192.168.178.97:8000', // Local development
    apiTimeout: 10000,
    enableLogging: true,
    enableCache: true,
    cacheTTL: 5 * 60 * 1000, // 5 minutes
  },
  staging: {
    apiUrl: 'https://staging-api.aura.com', // Staging server
    apiTimeout: 15000,
    enableLogging: true,
    enableCache: true,
    cacheTTL: 5 * 60 * 1000,
  },
  production: {
    // ⚠️ IMPORTANT: Production API URL
    // Priority 1: From Constants.expoConfig.extra.apiUrl (from app.config.js, which reads from eas.json)
    // Priority 2: Fallback to Railway URL
    // Note: process.env.EXPO_PUBLIC_API_URL is NOT available at runtime, only at build time
    // The value is passed through app.config.js -> Constants.expoConfig.extra.apiUrl
    // See: APK_FIX_GUIDE.md for detailed instructions
    apiUrl: Constants.expoConfig?.extra?.apiUrl || 
            'https://web-production-5a28a.up.railway.app', // Railway production URL
    apiTimeout: 20000,
    enableLogging: false,
    enableCache: true,
    cacheTTL: 10 * 60 * 1000, // 10 minutes
  },
};

// Get current environment
const currentEnv = getEnvironment();

// Get configuration for current environment
export const config = {
  ...ENVIRONMENTS[currentEnv],
  environment: currentEnv,
  isDevelopment: currentEnv === 'development',
  isStaging: currentEnv === 'staging',
  isProduction: currentEnv === 'production',
};

// Smart API URL detection (backward compatible)
export const getApiBaseUrl = () => {
  // Priority 1: Use environment config (already includes Constants.expoConfig.extra.apiUrl)
  if (config.apiUrl && config.apiUrl !== 'https://api.aura.com') {
    return config.apiUrl;
  }
  
  // Priority 2: Check Constants.expoConfig.extra.apiUrl directly (from app.config.js)
  const extraApiUrl = Constants.expoConfig?.extra?.apiUrl;
  if (extraApiUrl && extraApiUrl !== 'https://api.aura.com') {
    return extraApiUrl;
  }
  
  // Priority 3: Check for explicit API URL from environment (build-time)
  if (typeof process !== 'undefined' && process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  
  // Priority 4: Development fallback
  // Check if running on web (browser)
  if (typeof window !== 'undefined' && window.location) {
    return 'http://localhost:8000';
  }
  
  // Priority 5: Mobile development (only if in development mode)
  if (config.isDevelopment) {
    return 'http://192.168.178.97:8000'; // Local development IP
  }
  
  // Priority 6: Production fallback (for standalone builds)
  if (config.isProduction || config.isStaging) {
    return 'https://web-production-5a28a.up.railway.app'; // Railway production URL
  }
  
  // Final fallback: Railway URL (should not reach here)
  return 'https://web-production-5a28a.up.railway.app';
};

// Export API base URL
export const API_BASE_URL = getApiBaseUrl();

// Feature flags
export const features = {
  enableAnalytics: config.isProduction,
  enableCrashReporting: config.isProduction,
  enablePerformanceMonitoring: config.isProduction,
  enableDebugMenu: config.isDevelopment,
};

// App version info
export const appInfo = {
  version: Constants.expoConfig?.version || '1.0.0',
  buildNumber: Constants.expoConfig?.ios?.buildNumber || Constants.expoConfig?.android?.versionCode || '1',
  environment: config.environment,
};

export default config;

