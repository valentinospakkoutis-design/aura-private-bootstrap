# 📊 AURA Monitoring & Analytics Setup

**Last Updated**: December 2025

---

## 📋 Overview

This guide covers setting up monitoring, error tracking, and analytics for the AURA application.

---

## 🔧 Sentry Setup (Error Tracking)

### Installation

1. **Install Sentry**:
   ```bash
   npm install @sentry/react-native
   ```

2. **Configure in `app.config.js`**:
   ```javascript
   extra: {
     sentryDsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
   }
   ```

3. **Add to `.env`**:
   ```env
   EXPO_PUBLIC_SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
   ```

4. **Initialize in `app/_layout.js`**:
   ```javascript
   import * as Sentry from '@sentry/react-native';
   import { config } from '../mobile/src/config/environment';
   
   if (config.sentryDsn && !__DEV__) {
     Sentry.init({
       dsn: config.sentryDsn,
       environment: config.environment,
       enableAutoSessionTracking: true,
     });
   }
   ```

### Usage

```javascript
import { trackError } from '../services/monitoring';

try {
  // Your code
} catch (error) {
  trackError(error, { context: 'User action', userId: user.id });
}
```

---

## 📈 Analytics Setup

### Firebase Analytics (Optional)

1. **Install Firebase**:
   ```bash
   npm install @react-native-firebase/analytics
   ```

2. **Configure Firebase**:
   - Add `google-services.json` (Android)
   - Add `GoogleService-Info.plist` (iOS)

3. **Initialize**:
   ```javascript
   import analytics from '@react-native-firebase/analytics';
   
   // Track event
   await analytics().logEvent('screen_view', {
     screen_name: 'Home',
   });
   ```

### Custom Analytics

The app includes a monitoring service that can be extended:

```javascript
import { trackEvent, trackScreenView } from '../services/monitoring';

// Track screen view
trackScreenView('Home');

// Track custom event
trackEvent('button_click', {
  button_name: 'Buy',
  screen: 'Trading',
});
```

---

## 🎯 Event Tracking

### Screen Views

```javascript
import { useScreenTracking } from '../hooks/useAnalytics';

function MyScreen() {
  useScreenTracking('MyScreen');
  // ...
}
```

### User Actions

```javascript
import { trackAction } from '../services/monitoring';

const handleBuy = () => {
  trackAction('buy_order', {
    symbol: 'BTCUSDT',
    quantity: 0.1,
  });
  // ...
};
```

### Performance Metrics

```javascript
import { trackPerformance } from '../services/monitoring';

const startTime = Date.now();
// ... operation
const duration = Date.now() - startTime;
trackPerformance('api_call', duration, 'ms');
```

---

## 📊 Recommended Events

### Trading Events
- `buy_order` - User places buy order
- `sell_order` - User places sell order
- `order_cancelled` - User cancels order
- `broker_connected` - User connects broker

### Navigation Events
- `screen_view` - Screen viewed
- `button_click` - Button clicked
- `menu_opened` - Menu opened

### AI Events
- `prediction_viewed` - User views prediction
- `signal_received` - AI signal received
- `prediction_accuracy` - Prediction accuracy tracked

### Error Events
- `api_error` - API error occurred
- `network_error` - Network error
- `validation_error` - Form validation error

---

## 🔍 Monitoring Dashboard

### Key Metrics to Track

1. **User Engagement**:
   - Daily active users
   - Session duration
   - Screen views per session

2. **Trading Activity**:
   - Orders placed
   - Trades executed
   - Portfolio value

3. **AI Performance**:
   - Prediction accuracy
   - Signal generation rate
   - User trust in predictions

4. **Error Rates**:
   - Crash rate
   - API error rate
   - Network error rate

5. **Performance**:
   - App load time
   - API response time
   - Screen render time

---

## 🛠️ Configuration

### Environment Variables

```env
# Monitoring
EXPO_PUBLIC_SENTRY_DSN=your-sentry-dsn
EXPO_PUBLIC_ENABLE_ANALYTICS=true
EXPO_PUBLIC_ENABLE_CRASH_REPORTING=true
EXPO_PUBLIC_ENABLE_PERFORMANCE_MONITORING=true
```

### Feature Flags

```javascript
import { features } from '../config/environment';

if (features.enableAnalytics) {
  trackEvent('event_name', {});
}
```

---

## 📝 Best Practices

1. **Privacy**: Don't track sensitive data (API keys, passwords)
2. **Performance**: Use async tracking to avoid blocking UI
3. **Error Handling**: Always wrap tracking in try-catch
4. **Testing**: Disable in development or use test environment
5. **Compliance**: Follow GDPR/privacy regulations

---

## 🚨 Error Tracking

### Automatic Error Tracking

Errors are automatically tracked via:
- ErrorBoundary component
- API service error handling
- Network error handler

### Manual Error Tracking

```javascript
import { trackError } from '../services/monitoring';

try {
  // Risky operation
} catch (error) {
  trackError(error, {
    context: 'User action',
    userId: user.id,
    additionalData: { /* ... */ },
  });
}
```

---

## 📊 Analytics Providers

### Recommended Services

1. **Sentry**: Error tracking and performance
2. **Firebase Analytics**: User analytics
3. **Mixpanel**: Advanced analytics
4. **Amplitude**: Product analytics

### Custom Implementation

The monitoring service can be extended to support any analytics provider.

---

## ✅ Checklist

- [ ] Sentry configured
- [ ] Analytics service configured
- [ ] Screen tracking implemented
- [ ] Event tracking implemented
- [ ] Error tracking working
- [ ] Performance monitoring enabled
- [ ] Privacy compliance verified
- [ ] Dashboard configured

---

**Status**: ✅ Monitoring Setup Complete  
**Last Updated**: December 2025

*Made with 💎 in Cyprus*

