import AsyncStorage from '@react-native-async-storage/async-storage';
import { logger } from '../utils/Logger';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
}

export class CacheService {
  private prefix = '@aura_cache_';

  // Set cache with TTL (time to live in seconds)
  async set<T>(key: string, data: T, ttl: number = 3600): Promise<void> {
    try {
      const entry: CacheEntry<T> = {
        data,
        timestamp: Date.now(),
        expiresAt: Date.now() + ttl * 1000,
      };

      await AsyncStorage.setItem(
        this.prefix + key,
        JSON.stringify(entry)
      );

      logger.debug(`Cache set: ${key} (TTL: ${ttl}s)`);
    } catch (error) {
      logger.error('Failed to set cache:', error);
      throw error;
    }
  }

  // Get cache (returns null if expired or not found)
  async get<T>(key: string): Promise<T | null> {
    try {
      const raw = await AsyncStorage.getItem(this.prefix + key);
      
      if (!raw) {
        logger.debug(`Cache miss: ${key}`);
        return null;
      }

      const entry: CacheEntry<T> = JSON.parse(raw);

      // Check if expired
      if (Date.now() > entry.expiresAt) {
        logger.debug(`Cache expired: ${key}`);
        // Remove expired entry
        await this.remove(key);
        return null;
      }

      logger.debug(`Cache hit: ${key}`);
      return entry.data;
    } catch (error) {
      logger.error('Failed to get cache:', error);
      return null;
    }
  }

  // Get cache without expiration check (for manual expiration handling)
  async getRaw<T>(key: string): Promise<CacheEntry<T> | null> {
    try {
      const raw = await AsyncStorage.getItem(this.prefix + key);
      
      if (!raw) {
        return null;
      }

      return JSON.parse(raw) as CacheEntry<T>;
    } catch (error) {
      logger.error('Failed to get raw cache:', error);
      return null;
    }
  }

  // Remove cache entry
  async remove(key: string): Promise<void> {
    try {
      await AsyncStorage.removeItem(this.prefix + key);
      logger.debug(`Cache removed: ${key}`);
    } catch (error) {
      logger.error('Failed to remove cache:', error);
    }
  }

  // Clear all cache
  async clear(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys.filter((key) => key.startsWith(this.prefix));
      await AsyncStorage.multiRemove(cacheKeys);
      logger.info(`Cleared ${cacheKeys.length} cache entries`);
    } catch (error) {
      logger.error('Failed to clear cache:', error);
    }
  }

  // Check if cache exists and is valid
  async has(key: string): Promise<boolean> {
    const data = await this.get(key);
    return data !== null;
  }

  // Get expiration time for a cache entry
  async getExpirationTime(key: string): Promise<number | null> {
    try {
      const entry = await this.getRaw(key);
      return entry ? entry.expiresAt : null;
    } catch (error) {
      logger.error('Failed to get expiration time:', error);
      return null;
    }
  }

  // Get remaining TTL in seconds
  async getRemainingTTL(key: string): Promise<number | null> {
    try {
      const entry = await this.getRaw(key);
      
      if (!entry) {
        return null;
      }

      const remaining = Math.max(0, Math.floor((entry.expiresAt - Date.now()) / 1000));
      return remaining;
    } catch (error) {
      logger.error('Failed to get remaining TTL:', error);
      return null;
    }
  }

  // Get cache age in seconds
  async getAge(key: string): Promise<number | null> {
    try {
      const raw = await AsyncStorage.getItem(this.prefix + key);
      
      if (!raw) {
        return null;
      }

      const entry: CacheEntry<any> = JSON.parse(raw);
      return Math.floor((Date.now() - entry.timestamp) / 1000);
    } catch (error) {
      logger.error('Failed to get cache age:', error);
      return null;
    }
  }

  // Get all cache keys
  async getAllKeys(): Promise<string[]> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys
        .filter(key => key.startsWith(this.prefix))
        .map(key => key.replace(this.prefix, ''));
      
      return cacheKeys;
    } catch (error) {
      logger.error('Failed to get cache keys:', error);
      return [];
    }
  }

  // Get cache size (number of entries)
  async getSize(): Promise<number> {
    try {
      const keys = await this.getAllKeys();
      return keys.length;
    } catch (error) {
      logger.error('Failed to get cache size:', error);
      return 0;
    }
  }

  // Get cache stats
  async getStats(): Promise<{ count: number; size: number }> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys.filter((key) => key.startsWith(this.prefix));
      
      let totalSize = 0;
      for (const key of cacheKeys) {
        const value = await AsyncStorage.getItem(key);
        if (value) {
          totalSize += value.length;
        }
      }

      return {
        count: cacheKeys.length,
        size: totalSize,
      };
    } catch (error) {
      logger.error('Failed to get cache stats:', error);
      return { count: 0, size: 0 };
    }
  }

  // Clean expired entries
  async cleanExpired(): Promise<number> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys.filter(key => key.startsWith(this.prefix));
      let cleaned = 0;

      for (const key of cacheKeys) {
        const raw = await AsyncStorage.getItem(key);
        if (raw) {
          try {
            const entry: CacheEntry<any> = JSON.parse(raw);
            if (Date.now() > entry.expiresAt) {
              await AsyncStorage.removeItem(key);
              cleaned++;
            }
          } catch (error) {
            // Invalid entry, remove it
            await AsyncStorage.removeItem(key);
            cleaned++;
          }
        }
      }

      if (cleaned > 0) {
        logger.info(`Cleaned ${cleaned} expired cache entries`);
      }

      return cleaned;
    } catch (error) {
      logger.error('Failed to clean expired cache:', error);
      return 0;
    }
  }

  // Set cache with custom expiration time (timestamp)
  async setWithExpiration<T>(key: string, data: T, expirationTimestamp: number): Promise<void> {
    try {
      const entry: CacheEntry<T> = {
        data,
        timestamp: Date.now(),
        expiresAt: expirationTimestamp,
      };

      await AsyncStorage.setItem(
        this.prefix + key,
        JSON.stringify(entry)
      );

      logger.debug(`Cache set: ${key} (expires at: ${new Date(expirationTimestamp).toISOString()})`);
    } catch (error) {
      logger.error('Failed to set cache with expiration:', error);
      throw error;
    }
  }

  // Update TTL for existing cache entry
  async updateTTL(key: string, ttl: number): Promise<boolean> {
    try {
      const entry = await this.getRaw(key);
      
      if (!entry) {
        return false;
      }

      entry.expiresAt = Date.now() + ttl * 1000;
      
      await AsyncStorage.setItem(
        this.prefix + key,
        JSON.stringify(entry)
      );

      logger.debug(`Cache TTL updated: ${key} (new TTL: ${ttl}s)`);
      return true;
    } catch (error) {
      logger.error('Failed to update TTL:', error);
      return false;
    }
  }
}

// Create singleton instance
export const cacheService = new CacheService();

// Cache keys constants
export const CACHE_KEYS = {
  PREDICTIONS: 'predictions',
  PAPER_TRADES: 'paper_trades',
  LIVE_TRADES: 'live_trades',
  ANALYTICS: 'analytics',
  NOTIFICATIONS: 'notifications',
  USER_PROFILE: 'user_profile',
  BROKERS: 'brokers',
} as const;

// Cache TTL constants (in seconds)
export const CACHE_TTL = {
  SHORT: 300, // 5 minutes
  MEDIUM: 1800, // 30 minutes
  LONG: 3600, // 1 hour
  VERY_LONG: 86400, // 24 hours
} as const;

