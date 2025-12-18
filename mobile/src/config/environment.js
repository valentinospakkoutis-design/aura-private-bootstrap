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
    apiUrl: 'https://api.aura.com', // Production server
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
  // Use environment config if available
  if (config.apiUrl) {
    return config.apiUrl;
  }
  
  // Fallback to old logic
  if (!__DEV__) {
    return 'https://your-production-url.com';
  }
  
  // Check if running on web (browser)
  if (typeof window !== 'undefined' && window.location) {
    return 'http://localhost:8000';
  }
  
  // For mobile device, use local IP
  return 'http://192.168.178.97:8000';
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

