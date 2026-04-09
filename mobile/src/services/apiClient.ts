import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getToken, saveToken, deleteToken, getRefreshToken, saveRefreshToken, deleteRefreshToken } from '../utils/tokenStorage';
import { getApiBaseUrl } from '../config/environment';
import { logger } from '../utils/Logger';
import { cacheService, CACHE_KEYS, CACHE_TTL } from './CacheService';

// Base URL - uses environment configuration
const BASE_URL = getApiBaseUrl();

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing: boolean = false;
  private refreshQueue: Array<{ resolve: (token: string) => void; reject: (err: any) => void }> = [];

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token + logging
    this.client.interceptors.request.use(
      async (config) => {
        try {
          const token = await getToken();
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

    // Response interceptor - handle 401 with token refresh
    this.client.interceptors.response.use(
      (response) => {
        logger.debug('API Response:', response.status, response.data);
        return response;
      },
      async (error: AxiosError) => {
        logger.error('API Error:', error.response?.status, error.message);
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (
          error.response?.status === 401 &&
          originalRequest &&
          !originalRequest._retry &&
          originalRequest.headers?.Authorization &&
          !originalRequest.url?.includes('/auth/refresh') &&
          !originalRequest.url?.includes('/auth/login')
        ) {
          // Authenticated request got 401 — try refreshing
          if (this.isRefreshing) {
            // Another refresh is in progress — queue this request
            return new Promise((resolve, reject) => {
              this.refreshQueue.push({
                resolve: (newToken: string) => {
                  originalRequest._retry = true;
                  originalRequest.headers.Authorization = `Bearer ${newToken}`;
                  resolve(this.client(originalRequest));
                },
                reject,
              });
            });
          }

          this.isRefreshing = true;
          originalRequest._retry = true;

          try {
            const refreshToken = await getRefreshToken();
            if (!refreshToken) {
              throw new Error('No refresh token available');
            }

            console.log('[apiClient] Refreshing access token...');
            const response = await this.client.post('/api/v1/auth/refresh', {
              refresh_token: refreshToken,
            });

            const { access_token, refresh_token: newRefreshToken } = response.data;
            await saveToken(access_token);
            if (newRefreshToken) {
              await saveRefreshToken(newRefreshToken);
            }

            console.log('[apiClient] Token refreshed successfully');

            // Retry queued requests with new token
            this.refreshQueue.forEach((pending) => pending.resolve(access_token));
            this.refreshQueue = [];

            // Retry the original request
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            console.log('[apiClient] Token refresh failed, logging out');
            // Reject all queued requests
            this.refreshQueue.forEach((pending) => pending.reject(refreshError));
            this.refreshQueue = [];

            // Clear auth state
            await this.forceLogout();
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private async forceLogout() {
    try { await deleteToken(); } catch (e) { logger.warn('Error deleting token:', e); }
    try { await deleteRefreshToken(); } catch (e) { logger.warn('Error deleting refresh token:', e); }
    try {
      const { useAppStore } = require('../stores/appStore');
      useAppStore.getState().setUser(null);
    } catch (e) { logger.warn('Error clearing user state:', e); }
  }

  // Auth
  async login(email: string, password: string) {
    const response = await this.client.post('/api/v1/auth/login', { email, password });
    const { access_token, refresh_token } = response.data;
    await saveToken(access_token);
    if (refresh_token) {
      await saveRefreshToken(refresh_token);
    }
    // Fetch user profile from /auth/me
    try {
      const meResponse = await this.client.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      const me = meResponse.data;
      return {
        id: String(me.id || '1'),
        name: me.full_name || email.split('@')[0],
        email: me.email || email,
        voiceCloned: false,
        riskProfile: 'moderate',
      };
    } catch {
      return { id: '1', name: email.split('@')[0], email, voiceCloned: false, riskProfile: 'moderate' };
    }
  }

  async register(email: string, password: string) {
    const response = await this.client.post('/api/v1/auth/register', { email, password });
    return response.data;
  }

  async changePassword(currentPassword: string, newPassword: string) {
    const response = await this.client.put('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  async logout() {
    try {
      await deleteToken();
      await deleteRefreshToken();
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

    const response = await this.client.get('/api/ai/predictions', { timeout: 60000 });
    // Backend returns {predictions: {...}} - convert to array
    const data = response.data;
    let predictionsArray;
    if (data && data.predictions && typeof data.predictions === 'object') {
      // Convert object to array
      predictionsArray = Object.values(data.predictions);
    } else if (Array.isArray(data)) {
      predictionsArray = data;
    } else {
      predictionsArray = [];
    }
    await cacheService.set(CACHE_KEYS.PREDICTIONS, predictionsArray, 300); // 5 minutes
    return predictionsArray;
  }

  async getModelPerformance() {
    const response = await this.client.get('/api/v1/training/model-performance');
    return response.data;
  }

  async triggerFullPipeline() {
    const response = await this.client.post('/api/v1/training/full-pipeline');
    return response.data;
  }

  async getRLBatchPredictions() {
    try {
      const response = await this.client.get('/api/v1/rl/predictions/batch');
      return response.data;
    } catch {
      return { predictions: {}, trained_symbols: [], pending_symbols: [], trained_count: 0, total_count: 33, is_training: false };
    }
  }

  async getRLStatus() {
    try {
      const response = await this.client.get('/api/v1/rl/status');
      return response.data;
    } catch {
      return { models: [], count: 0 };
    }
  }

  async trainAllRL() {
    const response = await this.client.post('/api/v1/rl/train-all');
    return response.data;
  }

  async getBacktestResults() {
    const response = await this.client.get('/api/v1/backtest/results');
    return response.data;
  }

  async getBacktestSummary() {
    const response = await this.client.get('/api/v1/backtest/summary');
    return response.data;
  }

  async runBacktestAll() {
    const response = await this.client.post('/api/v1/backtest/run-all');
    return response.data;
  }

  async getMarketMovers() {
    const response = await this.client.get('/api/v1/market/movers', { timeout: 60000 });
    return response.data;
  }

  async getPredictionById(id: string) {
    const response = await this.client.get(`/api/ai/predictions/${id}`);
    return response.data;
  }

  async getPredictionBySymbol(symbol: string, days: number = 7) {
    const response = await this.client.get(`/api/ai/predict/${symbol}?days=${days}`);
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

    const response = await this.client.get('/api/brokers/status');
    await cacheService.set(CACHE_KEYS.BROKERS, response.data, CACHE_TTL.LONG);
    return response.data;
  }

  async connectBroker(brokerName: string, apiKey: string, apiSecret: string, testnet: boolean = false) {
    const response = await this.client.post('/api/brokers/connect', {
      broker: brokerName,  // Fixed: backend expects 'broker' not 'broker_name'
      api_key: apiKey,
      api_secret: apiSecret,
      testnet: testnet,
    });
    // Invalidate brokers cache after connecting
    await cacheService.remove(CACHE_KEYS.BROKERS);
    return response.data;
  }

  async disconnectBroker(brokerId: string) {
    const response = await this.client.delete(`/api/brokers/${brokerId}/disconnect`);
    // Invalidate brokers cache after disconnecting
    await cacheService.remove(CACHE_KEYS.BROKERS);
    return response.data;
  }

  // Trades
  async getTrades(limit: number = 50) {
    const response = await this.client.get(`/api/trading/positions`);
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

    // Get portfolio and history
    const [portfolioResponse, historyResponse] = await Promise.all([
      this.client.get('/api/paper-trading/portfolio').catch(() => ({ data: { positions: [], total_value: 0 } })),
      this.client.get('/api/paper-trading/history').catch(() => ({ data: { trades: [] } }))
    ]);
    
    // Combine portfolio positions with history
    const portfolio = portfolioResponse.data || {};
    const history = historyResponse.data || {};
    const rawTrades = history.trades || portfolio.positions || [];

    // Map backend fields to frontend PaperTrade interface
    const trades = rawTrades.map((t: any) => ({
      id: t.order_id || t.id || `trade_${Date.now()}`,
      asset: t.symbol || t.asset || 'Unknown',
      action: (t.side || t.action || 'buy').toLowerCase(),
      amount: t.quantity || t.amount || 0,
      price: t.price || t.avg_price || 0,
      currentPrice: t.current_price || t.currentPrice || t.price || 0,
      timestamp: t.executed_at || t.timestamp || new Date().toISOString(),
      profit: t.pnl || t.profit || 0,
      profitPercentage: t.pnl_percent || t.profitPercentage || 0,
      status: (t.side || '').toUpperCase() === 'SELL' ? 'closed' : 'open',
    }));

    await cacheService.set(CACHE_KEYS.PAPER_TRADES, trades, CACHE_TTL.SHORT);
    return trades;
  }

  async executeTrade(asset: string, action: 'buy' | 'sell', amount: number) {
    const response = await this.client.post('/api/brokers/order', {
      asset,
      action,
      amount,
    });
    // Invalidate trades cache after executing trade
    await cacheService.remove(CACHE_KEYS.PAPER_TRADES);
    await cacheService.remove(CACHE_KEYS.LIVE_TRADES);
    return response.data;
  }

  async placePaperOrder(symbol: string, side: 'BUY' | 'SELL', quantity: number) {
    const response = await this.client.post('/api/trading/order', {
      symbol,
      side,
      quantity,
    });
    await cacheService.remove(CACHE_KEYS.PAPER_TRADES);
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

    const response = await this.client.post('/api/voice/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getVoiceBriefing() {
    const response = await this.client.get('/api/voice/briefing');
    const data = response.data;
    // Backend returns briefing object with sections, but app expects url
    // Return the data as-is, component will handle it
    return data;
  }

  // Analytics
  async getPortfolioStats() {
    // Try paper trading statistics first, then analytics
    try {
      const response = await this.client.get('/api/paper-trading/statistics');
      const d = response.data || {};
      // Map backend fields to frontend PortfolioStats interface
      return {
        totalValue: Number(d.total_value ?? d.current_balance ?? d.totalValue ?? 0),
        totalProfit: d.total_pnl ?? d.totalProfit ?? 0,
        profitPercentage: d.total_pnl_percent ?? d.profitPercentage ?? 0,
        openTrades: d.active_positions ?? d.openTrades ?? 0,
        closedTrades: (d.total_trades ?? 0) - (d.active_positions ?? 0),
        winRate: d.win_rate ?? d.winRate ?? 0,
        mode: d.mode ?? 'paper',
      };
    } catch {
      // Fallback to analytics performance
      const response = await this.client.get('/api/analytics/performance');
      return response.data;
    }
  }

  async getPerformance(period: 'day' | 'week' | 'month' | 'year') {
    const response = await this.client.get(`/api/analytics/performance?period=${period}`);
    return response.data;
  }

  async getAnalyticsSummary(period: '7d' | '30d' | '90d' | 'all' = 'all') {
    const response = await this.client.get(`/api/analytics/summary?period=${period}`);
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

    const response = await this.client.get('/api/user/profile');
    await cacheService.set(CACHE_KEYS.USER_PROFILE, response.data, CACHE_TTL.LONG);
    return response.data;
  }

  async updateProfile(data: { name: string; email: string; phone: string; avatar?: string }) {
    const response = await this.client.put('/api/user/profile', data);
    // Invalidate profile cache after update
    await cacheService.remove(CACHE_KEYS.USER_PROFILE);
    return response.data;
  }

  async updatePassword(data: { currentPassword: string; newPassword: string }) {
    return this.changePassword(data.currentPassword, data.newPassword);
  }

  async updateRiskProfile(riskProfile: 'conservative' | 'moderate' | 'aggressive') {
    const response = await this.client.put('/api/user/risk-profile', { risk_profile: riskProfile });
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

    const response = await this.client.get('/api/trading/positions');
    if (useCache) {
      await cacheService.set(CACHE_KEYS.LIVE_TRADES, response.data, CACHE_TTL.SHORT);
    }
    return response.data;
  }

  async getLiveStats() {
    const response = await this.client.get('/api/trading/portfolio');
    return response.data;
  }

  async closeLiveTrade(tradeId: string) {
    const response = await this.client.post(`/api/live-trades/${tradeId}/close`);
    return response.data;
  }

  // ── Live Trading (real Binance) ────────────────────────────
  async getLivePortfolio() {
    const response = await this.client.get('/api/live-trading/portfolio');
    return response.data;
  }

  async getLivePortfolioFull() {
    const response = await this.client.get('/api/live-trading/portfolio/full');
    return response.data;
  }

  async getLiveTradeHistory() {
    const response = await this.client.get('/api/live-trading/history');
    return response.data;
  }

  async closeLivePosition(symbol: string, quantity: number) {
    const response = await this.client.post('/api/live-trading/close', { symbol, quantity });
    return response.data;
  }

  async getLivePositions() {
    const response = await this.client.get('/api/live-trading/positions');
    return response.data;
  }

  async placeLiveOrder(symbol: string, side: 'BUY' | 'SELL', quantity: number) {
    const response = await this.client.post('/api/live-trading/order', {
      symbol, side, quantity,
    });
    return response.data;
  }

  async placeLiveOrderWithSLTP(
    symbol: string, side: 'BUY' | 'SELL', quantity: number,
    price: number, stop_loss?: number, take_profit?: number
  ) {
    const response = await this.client.post('/api/live-trading/order/limit', {
      symbol, side, quantity, price, stop_loss, take_profit,
    });
    return response.data;
  }

  async cancelLiveOrder(symbol: string, orderId: number) {
    const response = await this.client.delete(`/api/live-trading/order/${symbol}/${orderId}`);
    return response.data;
  }

  // ── Futures ────────────────────────────────────────────────
  async getFuturesBalance() {
    const response = await this.client.get('/api/futures/balance');
    return response.data;
  }

  async getFuturesPositions() {
    const response = await this.client.get('/api/futures/positions');
    return response.data;
  }

  async placeFuturesOrder(symbol: string, side: 'LONG' | 'SHORT', quantity: number, leverage: number = 1) {
    const response = await this.client.post('/api/futures/order', {
      symbol, side, quantity, leverage,
    });
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

    const response = await this.client.get('/api/notifications');
    await cacheService.set(CACHE_KEYS.NOTIFICATIONS, response.data, CACHE_TTL.SHORT);
    return response.data;
  }

  async markNotificationAsRead(id: string) {
    const response = await this.client.put(`/api/notifications/${id}/read`);
    // Invalidate notifications cache after marking as read
    await cacheService.remove(CACHE_KEYS.NOTIFICATIONS);
    return response.data;
  }

  async deleteNotification(id: string) {
    const response = await this.client.delete(`/api/notifications/${id}`);
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

  // ── Auto Trading ───────────────────────────────────────────
  async getAutoTradingStatus() {
    const response = await this.client.get('/api/auto-trading/status');
    return response.data;
  }

  async enableAutoTrading() {
    const response = await this.client.post('/api/auto-trading/enable');
    return response.data;
  }

  async disableAutoTrading() {
    const response = await this.client.post('/api/auto-trading/disable');
    return response.data;
  }

  async updateAutoTradingConfig(config: {
    confidence_threshold?: number;
    fixed_order_value_usd?: number;
    stop_loss_pct?: number;
    max_positions?: number;
    max_order_value_usd?: number;
  }) {
    const response = await this.client.put('/api/auto-trading/config', config);
    return response.data;
  }

  async getAutoTradingPositions() {
    const response = await this.client.get('/api/auto-trading/positions');
    return response.data;
  }
}

export const api = new ApiClient();

