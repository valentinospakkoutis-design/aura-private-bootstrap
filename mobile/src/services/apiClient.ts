import axios, { AxiosInstance, AxiosError } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { getApiBaseUrl } from '../config/environment';
import { logger } from '../utils/Logger';
import { cacheService, CACHE_KEYS, CACHE_TTL } from './CacheService';

// Base URL - uses environment configuration
const BASE_URL = getApiBaseUrl();

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token + logging
    this.client.interceptors.request.use(
      async (config) => {
        try {
          const token = await SecureStore.getItemAsync('auth_token');
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
          
          // Log API call
          logger.api(config.method?.toUpperCase() || 'GET', config.url || '', config.data);
        } catch (error) {
          logger.error('Request interceptor error:', error);
        }
        return config;
      },
      (error) => {
        logger.error('Request interceptor error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor - handle errors + logging
    this.client.interceptors.response.use(
      (response) => {
        logger.debug('API Response:', response.status, response.data);
        return response;
      },
      async (error: AxiosError) => {
        logger.error('API Error:', error.response?.status, error.message);
        
        if (error.response?.status === 401) {
          // Unauthorized - clear token and redirect to login
          try {
            await SecureStore.deleteItemAsync('auth_token');
          } catch (e) {
            logger.warn('Error deleting auth token:', e);
          }
          // You can add navigation logic here
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth
  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', { email, password });
    const { token, user } = response.data;
    await SecureStore.setItemAsync('auth_token', token);
    return user;
  }

  async logout() {
    try {
      await SecureStore.deleteItemAsync('auth_token');
      logger.info('User logged out');
    } catch (error) {
      logger.warn('Error deleting auth token:', error);
    }
  }

  // Predictions
  async getPredictions(useCache: boolean = true) {
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.PREDICTIONS);
      if (cached) {
        logger.info('Using cached predictions');
        return cached;
      }
    }

    const response = await this.client.get('/predictions');
    await cacheService.set(CACHE_KEYS.PREDICTIONS, response.data, CACHE_TTL.MEDIUM);
    return response.data;
  }

  async getPredictionById(id: string) {
    const response = await this.client.get(`/predictions/${id}`);
    return response.data;
  }

  // Brokers
  async getBrokers(useCache: boolean = true) {
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.BROKERS);
      if (cached) {
        logger.info('Using cached brokers');
        return cached;
      }
    }

    const response = await this.client.get('/brokers');
    await cacheService.set(CACHE_KEYS.BROKERS, response.data, CACHE_TTL.LONG);
    return response.data;
  }

  async connectBroker(brokerName: string, apiKey: string, apiSecret: string) {
    const response = await this.client.post('/brokers/connect', {
      broker_name: brokerName,
      api_key: apiKey,
      api_secret: apiSecret,
    });
    // Invalidate brokers cache after connecting
    await cacheService.remove(CACHE_KEYS.BROKERS);
    return response.data;
  }

  async disconnectBroker(brokerId: string) {
    const response = await this.client.delete(`/brokers/${brokerId}`);
    // Invalidate brokers cache after disconnecting
    await cacheService.remove(CACHE_KEYS.BROKERS);
    return response.data;
  }

  // Trades
  async getTrades(limit: number = 50) {
    const response = await this.client.get(`/trades?limit=${limit}`);
    return response.data;
  }

  // Paper Trades with cache
  async getPaperTrades(useCache: boolean = true) {
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.PAPER_TRADES);
      if (cached) {
        logger.info('Using cached paper trades');
        return cached;
      }
    }

    const response = await this.client.get('/paper-trades');
    await cacheService.set(CACHE_KEYS.PAPER_TRADES, response.data, CACHE_TTL.SHORT);
    return response.data;
  }

  async executeTrade(asset: string, action: 'buy' | 'sell', amount: number) {
    const response = await this.client.post('/trades/execute', {
      asset,
      action,
      amount,
    });
    // Invalidate trades cache after executing trade
    await cacheService.remove(CACHE_KEYS.PAPER_TRADES);
    await cacheService.remove(CACHE_KEYS.LIVE_TRADES);
    return response.data;
  }

  // Voice
  async uploadVoiceSample(audioUri: string) {
    const formData = new FormData();
    formData.append('audio', {
      uri: audioUri,
      type: 'audio/m4a',
      name: 'voice_sample.m4a',
    } as any);

    const response = await this.client.post('/voice/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getVoiceBriefing() {
    const response = await this.client.get('/voice/briefing');
    return response.data;
  }

  // Analytics
  async getPortfolioStats() {
    const response = await this.client.get('/analytics/portfolio');
    return response.data;
  }

  async getPerformance(period: 'day' | 'week' | 'month' | 'year') {
    const response = await this.client.get(`/analytics/performance?period=${period}`);
    return response.data;
  }

  async getAnalytics(timeRange: '7d' | '30d' | '90d' | 'all', useCache: boolean = true) {
    const cacheKey = `${CACHE_KEYS.ANALYTICS}_${timeRange}`;
    
    if (useCache) {
      const cached = await cacheService.get(cacheKey);
      if (cached) {
        logger.info('Using cached analytics');
        return cached;
      }
    }

    const response = await this.client.get(`/analytics?range=${timeRange}`);
    await cacheService.set(cacheKey, response.data, CACHE_TTL.LONG);
    return response.data;
  }

  // User
  async getProfile(useCache: boolean = true) {
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.USER_PROFILE);
      if (cached) {
        logger.info('Using cached user profile');
        return cached;
      }
    }

    const response = await this.client.get('/user/profile');
    await cacheService.set(CACHE_KEYS.USER_PROFILE, response.data, CACHE_TTL.LONG);
    return response.data;
  }

  async updateProfile(data: { name: string; email: string; phone: string; avatar?: string }) {
    const response = await this.client.put('/user/profile', data);
    // Invalidate profile cache after update
    await cacheService.remove(CACHE_KEYS.USER_PROFILE);
    return response.data;
  }

  async updatePassword(data: { currentPassword: string; newPassword: string }) {
    const response = await this.client.put('/user/password', {
      current_password: data.currentPassword,
      new_password: data.newPassword,
    });
    return response.data;
  }

  async updateRiskProfile(riskProfile: 'conservative' | 'moderate' | 'aggressive') {
    const response = await this.client.put('/user/risk-profile', { risk_profile: riskProfile });
    return response.data;
  }

  // Live Trading
  async getLiveTrades(useCache: boolean = false) {
    // Live trades should not be cached by default (real-time data)
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.LIVE_TRADES);
      if (cached) {
        logger.info('Using cached live trades');
        return cached;
      }
    }

    const response = await this.client.get('/live-trades');
    if (useCache) {
      await cacheService.set(CACHE_KEYS.LIVE_TRADES, response.data, CACHE_TTL.SHORT);
    }
    return response.data;
  }

  async getLiveStats() {
    const response = await this.client.get('/live-trades/stats');
    return response.data;
  }

  async closeLiveTrade(tradeId: string) {
    const response = await this.client.post(`/live-trades/${tradeId}/close`);
    return response.data;
  }

  // Notifications
  async getNotifications(useCache: boolean = true) {
    if (useCache) {
      const cached = await cacheService.get(CACHE_KEYS.NOTIFICATIONS);
      if (cached) {
        logger.info('Using cached notifications');
        return cached;
      }
    }

    const response = await this.client.get('/notifications');
    await cacheService.set(CACHE_KEYS.NOTIFICATIONS, response.data, CACHE_TTL.SHORT);
    return response.data;
  }

  async markNotificationAsRead(id: string) {
    const response = await this.client.put(`/notifications/${id}/read`);
    // Invalidate notifications cache after marking as read
    await cacheService.remove(CACHE_KEYS.NOTIFICATIONS);
    return response.data;
  }

  async deleteNotification(id: string) {
    const response = await this.client.delete(`/notifications/${id}`);
    // Invalidate notifications cache after deletion
    await cacheService.remove(CACHE_KEYS.NOTIFICATIONS);
    return response.data;
  }

  // Cache Management
  async clearCache() {
    await cacheService.clear();
    logger.info('API cache cleared');
  }

  // Clear specific cache entry
  async clearCacheKey(key: string) {
    await cacheService.remove(key);
    logger.info(`Cache cleared for key: ${key}`);
  }
}

export const api = new ApiClient();

