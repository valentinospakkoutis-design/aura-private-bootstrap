import { useState, useEffect } from 'react';
import { useNetworkStatus } from './useNetworkStatus';
import { cacheService } from '../services/CacheService';
import { useAppStore } from '../stores/appStore';
import { logger } from '../utils/Logger';

export function useOfflineMode() {
  const { isOnline } = useNetworkStatus();
  const { showToast } = useAppStore();
  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [cacheStats, setCacheStats] = useState({ count: 0, size: 0 });

  useEffect(() => {
    if (!isOnline && !isOfflineMode) {
      setIsOfflineMode(true);
      showToast('Offline mode - Using cached data', 'warning');
      logger.info('Switched to offline mode');
    } else if (isOnline && isOfflineMode) {
      setIsOfflineMode(false);
      showToast('Back online!', 'success');
      logger.info('Switched to online mode');
    }
  }, [isOnline, isOfflineMode, showToast]);

  useEffect(() => {
    loadCacheStats();
  }, []);

  const loadCacheStats = async () => {
    try {
      const stats = await cacheService.getStats();
      setCacheStats(stats);
    } catch (error) {
      logger.error('Failed to load cache stats:', error);
    }
  };

  const clearCache = async () => {
    try {
      await cacheService.clear();
      await loadCacheStats();
      showToast('Cache cleared', 'success');
      logger.info('Cache cleared by user');
    } catch (error) {
      logger.error('Failed to clear cache:', error);
      showToast('Failed to clear cache', 'error');
    }
  };

  const formatCacheSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return {
    isOfflineMode,
    isOnline,
    cacheStats,
    cacheSize: formatCacheSize(cacheStats.size),
    clearCache,
    refreshCacheStats: loadCacheStats,
  };
}

