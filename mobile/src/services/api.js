// AURA API Service
// Handles all communication with backend
// Enhanced with retry logic, error handling, and caching

import { API_BASE_URL, config } from '../config/environment';

// Simple in-memory cache
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Greek error messages
const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Δεν υπάρχει σύνδεση στο διαδίκτυο. Ελέγξτε τη σύνδεσή σας.',
  TIMEOUT: 'Η αίτηση ξεπέρασε το χρονικό όριο. Δοκιμάστε ξανά.',
  SERVER_ERROR: 'Σφάλμα διακομιστή. Παρακαλώ δοκιμάστε αργότερα.',
  NOT_FOUND: 'Δεν βρέθηκε το αντικείμενο.',
  UNAUTHORIZED: 'Δεν έχετε εξουσιοδότηση. Παρακαλώ συνδεθείτε ξανά.',
  FORBIDDEN: 'Δεν έχετε πρόσβαση σε αυτόν τον πόρο.',
  BAD_REQUEST: 'Μη έγκυρη αίτηση. Ελέγξτε τα δεδομένα σας.',
  UNKNOWN: 'Συνέβη ένα σφάλμα. Παρακαλώ δοκιμάστε ξανά.'
};

class ApiService {
  constructor() {
    this.baseUrl = API_BASE_URL;
    this.defaultRetries = 3;
    this.defaultRetryDelay = 1000; // 1 second
  }

  /**
   * Check if device is online
   */
  async isOnline() {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'HEAD',
        cache: 'no-cache',
        signal: AbortSignal.timeout(3000)
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Get user-friendly error message
   */
  getErrorMessage(error, defaultMessage = ERROR_MESSAGES.UNKNOWN) {
    if (!error) return defaultMessage;
    
    // Network errors
    if (error.name === 'AbortError' || error.message?.includes('timeout')) {
      return ERROR_MESSAGES.TIMEOUT;
    }
    
    if (error.message?.includes('Failed to fetch') || error.message?.includes('Network')) {
      return ERROR_MESSAGES.NETWORK_ERROR;
    }
    
    // HTTP status codes
    if (error.message?.includes('status: 401')) {
      return ERROR_MESSAGES.UNAUTHORIZED;
    }
    
    if (error.message?.includes('status: 403')) {
      return ERROR_MESSAGES.FORBIDDEN;
    }
    
    if (error.message?.includes('status: 404')) {
      return ERROR_MESSAGES.NOT_FOUND;
    }
    
    if (error.message?.includes('status: 400')) {
      return ERROR_MESSAGES.BAD_REQUEST;
    }
    
    if (error.message?.includes('status: 5')) {
      return ERROR_MESSAGES.SERVER_ERROR;
    }
    
    // Try to extract message from error response
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    
    if (error.message && error.message !== 'HTTP error!') {
      return error.message;
    }
    
    return defaultMessage;
  }

  /**
   * Sleep utility for retry delays
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Retry wrapper for API calls
   */
  async withRetry(fn, retries = this.defaultRetries, delay = this.defaultRetryDelay) {
    let lastError;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        // Don't retry on 4xx errors (client errors)
        if (error.message?.includes('status: 4')) {
          throw error;
        }
        
        // Don't retry on last attempt
        if (attempt === retries) {
          break;
        }
        
        // Exponential backoff
        const backoffDelay = delay * Math.pow(2, attempt);
        await this.sleep(backoffDelay);
      }
    }
    
    throw lastError;
  }

  async fetchWithTimeout(url, options = {}, timeout = 10000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(id);
      return response;
    } catch (error) {
      clearTimeout(id);
      // Enhance error with more context
      const enhancedError = new Error(error.message || 'Network request failed');
      enhancedError.name = error.name;
      enhancedError.originalError = error;
      throw enhancedError;
    }
  }

  /**
   * Get cached data if available and not expired
   */
  getCached(key) {
    const cached = cache.get(key);
    if (!cached) return null;
    
    if (Date.now() - cached.timestamp > CACHE_TTL) {
      cache.delete(key);
      return null;
    }
    
    return cached.data;
  }

  /**
   * Set cache data
   */
  setCache(key, data) {
    cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * Clear cache
   */
  clearCache(key = null) {
    if (key) {
      cache.delete(key);
    } else {
      cache.clear();
    }
  }

  async get(endpoint, options = {}) {
    const { useCache = true, retries = this.defaultRetries } = options;
    const cacheKey = `GET:${endpoint}`;
    
    // Check cache first
    if (useCache) {
      const cached = this.getCached(cacheKey);
      if (cached !== null) {
        return cached;
      }
    }
    
    return this.withRetry(async () => {
      try {
        const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`);
        
        if (!response.ok) {
          const error = new Error(`HTTP error! status: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        
        const data = await response.json();
        
        // Cache successful responses
        if (useCache) {
          this.setCache(cacheKey, data);
        }
        
        return data;
      } catch (error) {
        console.error(`API GET Error [${endpoint}]:`, error);
        error.endpoint = endpoint;
        error.userMessage = this.getErrorMessage(error);
        throw error;
      }
    }, retries);
  }

  async post(endpoint, data, options = {}) {
    const { retries = this.defaultRetries, clearCacheOnSuccess = false } = options;
    
    return this.withRetry(async () => {
      try {
        const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data),
        });
        
        if (!response.ok) {
          const error = new Error(`HTTP error! status: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        
        const result = await response.json();
        
        // Clear cache if needed (e.g., after creating/updating data)
        if (clearCacheOnSuccess) {
          this.clearCache();
        }
        
        return result;
      } catch (error) {
        console.error(`API POST Error [${endpoint}]:`, error);
        error.endpoint = endpoint;
        error.userMessage = this.getErrorMessage(error);
        throw error;
      }
    }, retries);
  }

  async put(endpoint, data, options = {}) {
    const { retries = this.defaultRetries, clearCacheOnSuccess = false } = options;
    
    return this.withRetry(async () => {
      try {
        const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data),
        });
        
        if (!response.ok) {
          const error = new Error(`HTTP error! status: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        
        const result = await response.json();
        
        if (clearCacheOnSuccess) {
          this.clearCache();
        }
        
        return result;
      } catch (error) {
        console.error(`API PUT Error [${endpoint}]:`, error);
        error.endpoint = endpoint;
        error.userMessage = this.getErrorMessage(error);
        throw error;
      }
    }, retries);
  }

  async delete(endpoint, options = {}) {
    const { retries = this.defaultRetries, clearCacheOnSuccess = false } = options;
    
    return this.withRetry(async () => {
      try {
        const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          const error = new Error(`HTTP error! status: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        
        const result = await response.json();
        
        if (clearCacheOnSuccess) {
          this.clearCache();
        }
        
        return result;
      } catch (error) {
        console.error(`API DELETE Error [${endpoint}]:`, error);
        error.endpoint = endpoint;
        error.userMessage = this.getErrorMessage(error);
        throw error;
      }
    }, retries);
  }

  // Health Check
  async checkHealth() {
    return await this.get('/health');
  }

  // Quote of the Day
  async getQuoteOfDay() {
    return await this.get('/api/quote-of-day');
  }

  // Trading Stats
  async getStats() {
    return await this.get('/api/stats');
  }

  // System Status
  async getSystemStatus() {
    return await this.get('/api/system-status');
  }

  // Broker Management
  async connectBroker(broker, apiKey, apiSecret, testnet = true) {
    return await this.post('/api/brokers/connect', {
      broker,
      api_key: apiKey,
      api_secret: apiSecret,
      testnet
    });
  }

  async getBrokerStatus() {
    return await this.get('/api/brokers/status');
  }

  async getBrokerBalance(brokerName) {
    return await this.get(`/api/brokers/${brokerName}/balance`);
  }

  async getMarketPrice(brokerName, symbol) {
    return await this.get(`/api/brokers/${brokerName}/price/${symbol}`);
  }

  async getSupportedSymbols(brokerName) {
    return await this.get(`/api/brokers/${brokerName}/symbols`);
  }

  async placeOrder(broker, symbol, side, quantity, orderType = 'MARKET') {
    return await this.post('/api/brokers/order', {
      broker,
      symbol,
      side,
      quantity,
      order_type: orderType
    });
  }

  async disconnectBroker(brokerName) {
    return await this.delete(`/api/brokers/${brokerName}/disconnect`);
  }

  // Paper Trading
  async getPortfolio() {
    return await this.get('/api/trading/portfolio');
  }

  async getTradeHistory(limit = 50) {
    return await this.get(`/api/trading/history?limit=${limit}`);
  }

  async getTradingStatistics() {
    return await this.get('/api/paper-trading/statistics');
  }

  async resetPaperTrading() {
    return await this.post('/api/paper-trading/reset', {});
  }

  // AI Engine
  async getAIPrediction(symbol, days = 7) {
    return await this.get(`/api/ai/predict/${symbol}?days=${days}`);
  }

  async getAllPredictions(days = 7) {
    return await this.get(`/api/ai/predictions?days=${days}`);
  }

  async getTradingSignal(symbol) {
    return await this.get(`/api/ai/signal/${symbol}`);
  }

  async getAllSignals() {
    return await this.get('/api/ai/signals');
  }

  async getAIStatus() {
    return await this.get('/api/ai/status');
  }

  // CMS
  async getQuotes() {
    return await this.get('/api/cms/quotes');
  }

  async getQuote(quoteId) {
    return await this.get(`/api/cms/quotes/${quoteId}`);
  }

  async createQuote(quote) {
    return await this.post('/api/cms/quotes', quote);
  }

  async updateQuote(quoteId, quote) {
    return await this.put(`/api/cms/quotes/${quoteId}`, quote);
  }

  async deleteQuote(quoteId) {
    return await this.delete(`/api/cms/quotes/${quoteId}`);
  }

  async getCMSSettings() {
    return await this.get('/api/cms/settings');
  }

  async updateCMSSettings(settings) {
    return await this.put('/api/cms/settings', settings);
  }

  // Voice Briefing
  async getMorningBriefing(includeNews = true, includePredictions = true, includePortfolio = true, maxDuration = 90) {
    return await this.get(
      `/api/voice/briefing?include_news=${includeNews}&include_predictions=${includePredictions}&include_portfolio=${includePortfolio}&max_duration=${maxDuration}`
    );
  }

  async getBriefingHistory(days = 7) {
    return await this.get(`/api/voice/briefing/history?days=${days}`);
  }

  // On-Device ML
  async getMLStatus() {
    return await this.get('/api/ml/status');
  }

  async getMLModels() {
    return await this.get('/api/ml/models');
  }

  async getMLModel(modelId) {
    return await this.get(`/api/ml/models/${modelId}`);
  }

  async prepareModelDeployment(modelId, platform) {
    return await this.get(`/api/ml/models/${modelId}/deploy/${platform}`);
  }

  async getTrainingConfigs() {
    return await this.get('/api/ml/training/configs');
  }

  async getDatasetInfo(datasetType) {
    return await this.get(`/api/ml/training/dataset/${datasetType}`);
  }

  // Live Trading
  async getTradingMode() {
    return await this.get('/api/trading/mode');
  }

  async setTradingMode(mode) {
    return await this.post('/api/trading/mode', { mode });
  }

  async getRiskSettings() {
    return await this.get('/api/trading/risk-settings');
  }

  async updateRiskSettings(settings) {
    return await this.put('/api/trading/risk-settings', settings);
  }

  async validateOrder(symbol, side, quantity, price) {
    return await this.post('/api/trading/validate-order', {
      symbol,
      side,
      quantity,
      price
    });
  }

  async calculatePositionSize(symbol, side, price, riskPercent) {
    return await this.get(
      `/api/trading/calculate-position?symbol=${symbol}&side=${side}&price=${price}&risk_percent=${riskPercent || ''}`
    );
  }

  async getRiskSummary() {
    return await this.get('/api/trading/risk-summary');
  }

  // Analytics
  async getPerformanceMetrics() {
    return await this.get('/api/analytics/performance');
  }

  async getPerformanceByPeriod(period) {
    return await this.get(`/api/analytics/performance/${period}`);
  }

  async getSymbolPerformance() {
    return await this.get('/api/analytics/symbols');
  }

  // Scheduler
  async getSchedules(scheduleType) {
    return await this.get(`/api/scheduler/schedules${scheduleType ? `?schedule_type=${scheduleType}` : ''}`);
  }

  async getSchedule(scheduleId) {
    return await this.get(`/api/scheduler/schedules/${scheduleId}`);
  }

  async createSchedule(schedule) {
    return await this.post('/api/scheduler/schedules', schedule);
  }

  async updateSchedule(scheduleId, schedule) {
    return await this.put(`/api/scheduler/schedules/${scheduleId}`, schedule);
  }

  async deleteSchedule(scheduleId) {
    return await this.delete(`/api/scheduler/schedules/${scheduleId}`);
  }

  async getUpcomingSchedules(limit = 10) {
    return await this.get(`/api/scheduler/upcoming?limit=${limit}`);
  }

  // Notifications
  async getNotifications(unreadOnly = false, notificationType = null, limit = 50) {
    return await this.get(
      `/api/notifications?unread_only=${unreadOnly}&notification_type=${notificationType || ''}&limit=${limit}`
    );
  }

  async getNotification(notificationId) {
    return await this.get(`/api/notifications/${notificationId}`);
  }

  async createNotification(notification) {
    return await this.post('/api/notifications', notification);
  }

  async markNotificationRead(notificationId) {
    return await this.put(`/api/notifications/${notificationId}/read`);
  }

  async markAllNotificationsRead() {
    return await this.put('/api/notifications/read-all');
  }

  async deleteNotification(notificationId) {
    return await this.delete(`/api/notifications/${notificationId}`);
  }

  async deleteAllReadNotifications() {
    return await this.delete('/api/notifications/read');
  }

  async getNotificationStats() {
    return await this.get('/api/notifications/stats');
  }
}

export default new ApiService();

