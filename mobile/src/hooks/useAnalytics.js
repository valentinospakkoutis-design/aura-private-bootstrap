// Analytics Hook
// Provides easy access to analytics functions

import { useEffect } from 'react';
import { trackScreenView, trackEvent, trackAction } from '../services/monitoring';

/**
 * Hook to track screen views automatically
 */
export function useScreenTracking(screenName, properties = {}) {
  useEffect(() => {
    trackScreenView(screenName, properties);
  }, [screenName]);
}

/**
 * Hook for tracking user interactions
 */
export function useAnalytics() {
  return {
    trackEvent,
    trackAction,
    trackScreenView,
  };
}

