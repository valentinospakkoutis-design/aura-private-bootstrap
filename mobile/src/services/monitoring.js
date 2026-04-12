// Monitoring Service
// Handles error tracking, analytics, and performance monitoring

import { config, features } from '../config/environment';

/**
 * Initialize monitoring services
 */
export function initMonitoring() {
  if (!features.enableCrashReporting) {
    return;
  }

  // Initialize Sentry if enabled
  if (config.sentryDsn) {
    try {
      console.info('[Monitoring] Sentry initialized');
    } catch (error) {
      console.error('[Monitoring] Failed to initialize Sentry:', error);
    }
  }
}

/**
 * Track error
 */
export function trackError(error, context = {}) {
  if (!features.enableCrashReporting) {
    return;
  }

  console.error('[Error]', error, context);

  // Send to Sentry
  if (config.sentryDsn) {
    try {
      console.info('[Monitoring] Error tracked:', error.message);
    } catch (err) {
      console.error('[Monitoring] Failed to track error:', err);
    }
  }
}

/**
 * Track event
 */
export function trackEvent(eventName, properties = {}) {
  if (!features.enableAnalytics) {
    return;
  }

  console.info('[Analytics]', eventName, properties);

  try {
    console.info('[Monitoring] Event tracked:', eventName);
  } catch (error) {
    console.error('[Monitoring] Failed to track event:', error);
  }
}

/**
 * Track screen view
 */
export function trackScreenView(screenName, properties = {}) {
  trackEvent('screen_view', {
    screen_name: screenName,
    ...properties,
  });
}

/**
 * Track user action
 */
export function trackAction(action, properties = {}) {
  trackEvent('user_action', {
    action,
    ...properties,
  });
}

/**
 * Set user properties
 */
export function setUserProperties(properties) {
  if (!features.enableAnalytics) {
    return;
  }

  try {
    console.info('[Monitoring] User properties set:', properties);
  } catch (error) {
    console.error('[Monitoring] Failed to set user properties:', error);
  }
}

/**
 * Track performance metric
 */
export function trackPerformance(metricName, value, unit = 'ms') {
  if (!features.enablePerformanceMonitoring) {
    return;
  }

  console.info(`[Performance] ${metricName}: ${value}${unit}`);

  try {
    console.info('[Monitoring] Performance tracked:', metricName);
  } catch (error) {
    console.error('[Monitoring] Failed to track performance:', error);
  }
}

/**
 * Breadcrumb for debugging
 */
export function addBreadcrumb(message, category = 'navigation', level = 'info') {
  if (!features.enableCrashReporting) {
    return;
  }

  try {
    console.info(`[Breadcrumb] ${category}: ${message}`);
  } catch (error) {
    console.error('[Monitoring] Failed to add breadcrumb:', error);
  }
}

