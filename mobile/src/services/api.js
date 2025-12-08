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
}

export default new ApiService();

