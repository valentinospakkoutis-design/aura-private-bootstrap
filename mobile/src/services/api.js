// AURA API Service
// Handles all communication with backend

// Smart API URL detection
// For web: use localhost, for mobile device: use local IP
const getApiBaseUrl = () => {
  if (!__DEV__) {
    return 'https://your-production-url.com';  // Production
  }
  
  // Check if running on web (browser)
  if (typeof window !== 'undefined' && window.location) {
    return 'http://localhost:8000';  // Web browser
  }
  
  // For mobile device, use local IP (update this if your IP changes)
  // Find your IP with: ipconfig (Windows) or ifconfig (Mac/Linux)
  return 'http://192.168.178.97:8000';  // Mobile device on same WiFi
};

const API_BASE_URL = getApiBaseUrl();

class ApiService {
  constructor() {
    this.baseUrl = API_BASE_URL;
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
      throw error;
    }
  }

  async get(endpoint) {
    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API GET Error [${endpoint}]:`, error);
      throw error;
    }
  }

  async post(endpoint, data) {
    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API POST Error [${endpoint}]:`, error);
      throw error;
    }
  }

  async delete(endpoint) {
    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API DELETE Error [${endpoint}]:`, error);
      throw error;
    }
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

