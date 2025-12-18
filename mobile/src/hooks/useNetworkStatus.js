// Network Status Hook
// Monitors network connectivity and provides offline/online status

import { useState, useEffect } from 'react';
import api from '../services/api';

/**
 * Custom hook to monitor network connectivity
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.checkInterval - Interval to check network status (ms, default: 5000)
 * @param {boolean} options.enabled - Whether to enable monitoring (default: true)
 * 
 * @returns {Object} { isOnline, isChecking, lastChecked, checkConnection }
 */
export function useNetworkStatus(options = {}) {
  const {
    checkInterval = 5000,
    enabled = true
  } = options;

  const [isOnline, setIsOnline] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);

  const checkConnection = async () => {
    setIsChecking(true);
    try {
      const online = await api.isOnline();
      setIsOnline(online);
      setLastChecked(new Date());
    } catch (error) {
      setIsOnline(false);
      setLastChecked(new Date());
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    if (!enabled) return;

    // Initial check
    checkConnection();

    // Periodic checks
    const interval = setInterval(checkConnection, checkInterval);

    return () => clearInterval(interval);
  }, [enabled, checkInterval]);

  return {
    isOnline,
    isChecking,
    lastChecked,
    checkConnection
  };
}

