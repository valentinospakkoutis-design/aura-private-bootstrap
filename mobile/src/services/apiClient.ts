import axios, { AxiosInstance, AxiosError } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { getApiBaseUrl } from '../config/environment';
import { logger } from '../utils/Logger';

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
    } catch (error) {
      console.warn('Error deleting auth token:', error);
    }
  }

  // Predictions
  async getPredictions() {
    const response = await this.client.get('/predictions');
    return response.data;
  }

  async getPredictionById(id: string) {
    const response = await this.client.get(`/predictions/${id}`);
    return response.data;
  }

  // Brokers
  async getBrokers() {
    const response = await this.client.get('/brokers');
    return response.data;
  }

  async connectBroker(brokerName: string, apiKey: string, apiSecret: string) {
    const response = await this.client.post('/brokers/connect', {
      broker_name: brokerName,
      api_key: apiKey,
      api_secret: apiSecret,
    });
    return response.data;
  }

  async disconnectBroker(brokerId: string) {
    const response = await this.client.delete(`/brokers/${brokerId}`);
    return response.data;
  }

  // Trades
  async getTrades(limit: number = 50) {
    const response = await this.client.get(`/trades?limit=${limit}`);
    return response.data;
  }

  async executeTrade(asset: string, action: 'buy' | 'sell', amount: number) {
    const response = await this.client.post('/trades/execute', {
      asset,
      action,
      amount,
    });
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

  // User
  async getProfile() {
    const response = await this.client.get('/user/profile');
    return response.data;
  }

  async updateProfile(data: any) {
    const response = await this.client.put('/user/profile', data);
    return response.data;
  }

  async updateRiskProfile(riskProfile: 'conservative' | 'moderate' | 'aggressive') {
    const response = await this.client.put('/user/risk-profile', { risk_profile: riskProfile });
    return response.data;
  }
}

export const api = new ApiClient();

