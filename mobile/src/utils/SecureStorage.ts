import * as SecureStore from 'expo-secure-store';

export class SecureStorage {
  // Store encrypted data
  static async set(key: string, value: string): Promise<void> {
    try {
      await SecureStore.setItemAsync(key, value);
    } catch (error) {
      console.error(`Failed to store ${key}:`, error);
      throw new Error(`Failed to store ${key}`);
    }
  }

  // Retrieve encrypted data
  static async get(key: string): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(key);
    } catch (error) {
      console.error(`Failed to retrieve ${key}:`, error);
      return null;
    }
  }

  // Delete encrypted data
  static async delete(key: string): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(key);
    } catch (error) {
      console.error(`Failed to delete ${key}:`, error);
      throw new Error(`Failed to delete ${key}`);
    }
  }

  // Store object as JSON
  static async setObject(key: string, value: any): Promise<void> {
    try {
      const jsonValue = JSON.stringify(value);
      await this.set(key, jsonValue);
    } catch (error) {
      console.error(`Failed to store object ${key}:`, error);
      throw new Error(`Failed to store object ${key}`);
    }
  }

  // Retrieve object from JSON
  static async getObject<T>(key: string): Promise<T | null> {
    try {
      const jsonValue = await this.get(key);
      return jsonValue ? JSON.parse(jsonValue) : null;
    } catch (error) {
      console.error(`Failed to retrieve object ${key}:`, error);
      return null;
    }
  }

  // Clear all secure storage (use with caution!)
  static async clearAll(keys: string[]): Promise<void> {
    try {
      await Promise.all(keys.map((key) => this.delete(key)));
    } catch (error) {
      console.error('Failed to clear storage:', error);
      throw new Error('Failed to clear storage');
    }
  }

  // Check if key exists
  static async exists(key: string): Promise<boolean> {
    const value = await this.get(key);
    return value !== null;
  }
}

// Predefined keys for consistency
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  USER_DATA: 'user_data',
  BIOMETRICS_ENABLED: 'biometrics_enabled',
  PAPER_TRADING_MODE: 'paper_trading_mode',
  RISK_PROFILE: 'risk_profile',
  NOTIFICATIONS_ENABLED: 'notifications_enabled',
  PUSH_TOKEN: 'push_token',
} as const;

