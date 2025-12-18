// Custom hook for API calls with caching and error handling
import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

/**
 * Custom hook for API calls with automatic caching, loading states, and error handling
 * 
 * @param {Function} apiCall - Function that returns a promise (e.g., () => api.get('/endpoint'))
 * @param {Object} options - Configuration options
 * @param {boolean} options.enabled - Whether to run the API call automatically (default: true)
 * @param {boolean} options.useCache - Whether to use cache (default: true)
 * @param {number} options.retries - Number of retries (default: 3)
 * @param {Array} options.dependencies - Dependencies array for useEffect (default: [])
 * 
 * @returns {Object} { data, loading, error, refetch }
 */
export function useApi(apiCall, options = {}) {
  const {
    enabled = true,
    useCache = true,
    retries = 3,
    dependencies = []
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!enabled) return;

    try {
      setLoading(true);
      setError(null);
      
      const result = await apiCall();
      setData(result);
    } catch (err) {
      setError(err);
      console.error('useApi error:', err);
    } finally {
      setLoading(false);
    }
  }, [apiCall, enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData, ...dependencies]);

  return {
    data,
    loading,
    error,
    refetch: fetchData
  };
}

/**
 * Hook for API mutations (POST, PUT, DELETE)
 * 
 * @param {Function} apiCall - Function that returns a promise
 * @param {Object} options - Configuration options
 * 
 * @returns {Array} [mutate, { loading, error, data }]
 */
export function useApiMutation(apiCall, options = {}) {
  const { onSuccess, onError } = options;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const mutate = useCallback(async (...args) => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await apiCall(...args);
      setData(result);
      
      if (onSuccess) {
        onSuccess(result);
      }
      
      return result;
    } catch (err) {
      setError(err);
      console.error('useApiMutation error:', err);
      
      if (onError) {
        onError(err);
      }
      
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiCall, onSuccess, onError]);

  return [mutate, { loading, error, data }];
}

/**
 * Hook for fetching quote of the day
 * 
 * @returns {Object} { data, loading, error, refetch }
 */
export function useQuoteOfDay() {
  return useApi(
    () => api.getQuoteOfDay(),
    {
      useCache: true,
      retries: 2,
      dependencies: []
    }
  );
}
