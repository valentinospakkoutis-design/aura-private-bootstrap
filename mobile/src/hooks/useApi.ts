import { useState, useCallback } from 'react';
import { ErrorHandler, AppError } from '@/utils/errorHandler';
import { useAppStore } from '@/stores/appStore';

interface UseApiOptions {
  showToast?: boolean;
  showLoading?: boolean;
}

export function useApi<T = any>(
  apiFunction: (...args: any[]) => Promise<T>,
  options: UseApiOptions = {}
) {
  const { showToast = true, showLoading = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const [loading, setLoading] = useState(false);

  const { showToast: showToastGlobal, setIsLoading } = useAppStore();

  const execute = useCallback(
    async (...args: any[]) => {
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

