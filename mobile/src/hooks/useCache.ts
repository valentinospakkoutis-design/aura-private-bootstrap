import { useState, useCallback } from 'react';
import { cacheService } from '../services/CacheService';
import { logger } from '../utils/Logger';

export function useCache<T>(key: string, ttl: number = 3600) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Get cached data
  const get = useCallback(async (): Promise<T | null> => {
    setLoading(true);
    setError(null);
    
    try {
      const cached = await cacheService.get<T>(key);
      setData(cached);
      return cached;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to get cache');
      setError(error);
      logger.error('Cache get error:', error);
      return null;
    } finally {
      setLoading(false);
    }
  }, [key]);

  // Set cache data
  const set = useCallback(async (value: T, customTTL?: number): Promise<void> => {
    setLoading(true);
    setError(null);
    
    try {
      await cacheService.set(key, value, customTTL || ttl);
      setData(value);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to set cache');
      setError(error);
      logger.error('Cache set error:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [key, ttl]);

  // Remove cache
  const remove = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    
    try {
      await cacheService.remove(key);
      setData(null);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to remove cache');
      setError(error);
      logger.error('Cache remove error:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [key]);

  // Check if cache exists
  const has = useCallback(async (): Promise<boolean> => {
    try {
      return await cacheService.has(key);
    } catch (err) {
      logger.error('Cache has check error:', err);
      return false;
    }
  }, [key]);

  // Get remaining TTL
  const getRemainingTTL = useCallback(async (): Promise<number | null> => {
    try {
      return await cacheService.getRemainingTTL(key);
    } catch (err) {
      logger.error('Cache TTL check error:', err);
      return null;
    }
  }, [key]);

  return {
    data,
    loading,
    error,
    get,
    set,
    remove,
    has,
    getRemainingTTL,
  };
}

