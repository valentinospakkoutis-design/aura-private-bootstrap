import { useState, useCallback, useEffect } from 'react';
import { ErrorHandler, AppError } from '../utils/errorHandler';
import { useAppStore } from '../stores/appStore';

interface UseApiOptions {
  showToast?: boolean;
  showLoading?: boolean;
}

export function useApi<T = unknown, TArgs extends unknown[] = unknown[]>(
  apiFunction: (...args: TArgs) => Promise<T>,
  options: UseApiOptions = {}
) {
  const { showToast = true, showLoading = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const [loading, setLoading] = useState(false);

  const { showToast: showToastGlobal, setIsLoading } = useAppStore();

  const execute = useCallback(
    async (...args: TArgs) => {
      try {
        setLoading(true);
        if (showLoading) setIsLoading(true);
        setError(null);

        const result = await apiFunction(...args);
        setData(result);
        return result;
      } catch (err) {
        const appError = ErrorHandler.handle(err);
        setError(appError);

        if (showToast) {
          showToastGlobal(appError.message, 'error');
        }

        throw appError;
      } finally {
        setLoading(false);
        if (showLoading) setIsLoading(false);
      }
    },
    [apiFunction, showToast, showLoading, showToastGlobal, setIsLoading]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    data,
    error,
    loading,
    execute,
    reset,
  };
}

// Legacy hook used by DailyQuote component (auto-fetches on mount)
export function useQuoteOfDay() {
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const { getApiBaseUrl } = require('../config/environment');
    const baseUrl = getApiBaseUrl();
    fetch(`${baseUrl}/api/quote-of-day`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setData(d))
      .catch(e => setError(e))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error, refetch: () => {} };
}

