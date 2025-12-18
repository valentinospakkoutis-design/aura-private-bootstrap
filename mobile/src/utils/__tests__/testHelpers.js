// Test Helpers and Utilities
// Common utilities for testing

/**
 * Mock API response helper
 */
export function mockApiResponse(data, delay = 0) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(data), delay);
  });
}

/**
 * Mock API error helper
 */
export function mockApiError(message, status = 500, delay = 0) {
  return new Promise((_, reject) => {
    setTimeout(() => {
      const error = new Error(message);
      error.status = status;
      reject(error);
    }, delay);
  });
}

/**
 * Wait utility for async tests
 */
export function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Create mock navigation object
 */
export function createMockNavigation() {
  return {
    navigate: jest.fn(),
    goBack: jest.fn(),
    push: jest.fn(),
    replace: jest.fn(),
    pop: jest.fn(),
    popToTop: jest.fn(),
    setParams: jest.fn(),
    addListener: jest.fn(),
    removeListener: jest.fn(),
    canGoBack: jest.fn(() => true),
    isFocused: jest.fn(() => true),
  };
}

/**
 * Create mock route object
 */
export function createMockRoute(params = {}) {
  return {
    key: 'test-route',
    name: 'TestScreen',
    params,
    path: '/test',
  };
}

/**
 * Mock SecureStore
 */
export const mockSecureStore = {
  items: new Map(),
  
  async getItemAsync(key) {
    return this.items.get(key) || null;
  },
  
  async setItemAsync(key, value) {
    this.items.set(key, value);
  },
  
  async deleteItemAsync(key) {
    this.items.delete(key);
  },
  
  clear() {
    this.items.clear();
  }
};

/**
 * Mock Crypto
 */
export const mockCrypto = {
  async getRandomBytesAsync(length) {
    const bytes = new Uint8Array(length);
    for (let i = 0; i < length; i++) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
    return bytes;
  },
  
  async digestStringAsync(algorithm, data) {
    // Simple mock hash
    return `hash_${data.substring(0, 10)}`;
  }
};

/**
 * Test data generators
 */
export const testData = {
  user: {
    id: 1,
    email: 'test@example.com',
    username: 'testuser',
  },
  
  portfolio: {
    total_value: 10000,
    cash: 5000,
    positions: [
      { symbol: 'BTCUSDT', quantity: 0.5, value: 20000 },
      { symbol: 'ETHUSDT', quantity: 10, value: 30000 },
    ],
  },
  
  notification: {
    id: 1,
    type: 'trade_executed',
    title: 'Trade Executed',
    message: 'Your order has been filled',
    read: false,
    created_at: new Date().toISOString(),
  },
  
  prediction: {
    symbol: 'XAUUSDT',
    current_price: 2000,
    predicted_price: 2050,
    confidence: 0.85,
    days: 7,
  },
};

