import { useState, useEffect } from 'react';
import api from '../services/api';

/**
 * Custom hook για API calls με automatic loading και error handling
 */
export function useApi(apiFunction, dependencies = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await apiFunction();
        
        if (mounted) {
          setData(result);
        }
      } catch (err) {
        if (mounted) {
          setError(err.message || 'Σφάλμα σύνδεσης');
          console.error('API Error:', err);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      mounted = false;
    };
  }, dependencies);

  const refetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFunction();
      setData(result);
    } catch (err) {
      setError(err.message || 'Σφάλμα σύνδεσης');
    } finally {
      setLoading(false);
    }
  };

  return { data, loading, error, refetch };
}

/**
 * Hook για System Status
 */
export function useSystemStatus() {
  return useApi(() => api.getSystemStatus());
}

/**
 * Hook για Trading Stats
 */
export function useStats() {
  return useApi(() => api.getStats());
}

/**
 * Hook για Quote of Day
 */
export function useQuoteOfDay() {
  return useApi(() => api.getQuoteOfDay());
}

