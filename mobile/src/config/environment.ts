// Environment Configuration
// Handles API URLs for different environments

const API_BASE_URL = 'http://116.203.75.114:8080';

const getEnvironment = (): string => {
  if (typeof process !== 'undefined' && process.env.EXPO_PUBLIC_ENVIRONMENT) {
    return process.env.EXPO_PUBLIC_ENVIRONMENT;
  }

  return 'development';
};

export const getApiBaseUrl = (): string => {
  if (typeof process !== 'undefined' && process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }

  return API_BASE_URL;
};

export const getWebSocketUrl = (): string => {
  const apiUrl = getApiBaseUrl();

  if (apiUrl.startsWith('https://')) {
    return apiUrl.replace('https://', 'wss://') + '/ws';
  }

  return apiUrl.replace('http://', 'ws://') + '/ws';
};

export const environment = {
  isDevelopment: getEnvironment() === 'development',
  isStaging: getEnvironment() === 'staging',
  isProduction: getEnvironment() === 'production',
  apiUrl: getApiBaseUrl(),
  wsUrl: getWebSocketUrl(),
};
