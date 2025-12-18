# 🧪 AURA Testing Guide

**Last Updated**: December 2025

---

## 📋 Table of Contents

1. [Real-World Testing](#real-world-testing)
2. [Binance Testnet Integration](#binance-testnet-integration)
3. [AI Predictions Validation](#ai-predictions-validation)
4. [Risk Management Testing](#risk-management-testing)
5. [Notification System Testing](#notification-system-testing)

---

## 🔗 Real-World Testing

### Overview

Real-world testing involves using actual market data and testnet environments to validate the application's functionality before production deployment.

### Prerequisites

- Backend server running
- Binance testnet account
- Test API keys configured
- Paper trading enabled

---

## 🪙 Binance Testnet Integration

### Setup

1. **Create Binance Testnet Account**:
   - Visit: https://testnet.binance.vision/
   - Create account and get testnet API keys

2. **Configure API Keys**:
   ```javascript
   // In brokers screen
   Broker: Binance
   API Key: [testnet-api-key]
   API Secret: [testnet-api-secret]
   Testnet: ✅ Enabled
   ```

3. **Test Connection**:
   ```bash
   # Test API connection
   curl https://testnet.binance.vision/api/v3/ping
   ```

### Testing Checklist

- [ ] Connect to Binance testnet
- [ ] Fetch account balance
- [ ] Get market prices
- [ ] Place test order (BUY)
- [ ] Place test order (SELL)
- [ ] Check order status
- [ ] View trade history
- [ ] Test error handling (invalid orders)
- [ ] Test rate limiting
- [ ] Test connection recovery

### Test Scenarios

**Scenario 1: Basic Trading**
1. Connect to Binance testnet
2. Check available balance
3. Place BUY order for BTCUSDT
4. Verify order execution
5. Check updated balance
6. Place SELL order
7. Verify profit/loss

**Scenario 2: Error Handling**
1. Place order with insufficient balance
2. Verify error message
3. Place order with invalid symbol
4. Verify error handling
5. Test network disconnection
6. Verify reconnection

**Scenario 3: Risk Management**
1. Set risk limits (max 10% per trade)
2. Place large order
3. Verify order rejection
4. Adjust risk settings
5. Verify order acceptance

---

## 🤖 AI Predictions Validation

### Accuracy Testing

1. **Collect Historical Predictions**:
   ```javascript
   // Get predictions for past 7 days
   const predictions = await api.getAllPredictions(days=7);
   ```

2. **Compare with Actual Prices**:
   ```javascript
   // Get actual prices
   const actualPrices = await api.getHistoricalPrices(symbol, days=7);
   
   // Calculate accuracy
   const accuracy = calculateAccuracy(predictions, actualPrices);
   ```

3. **Track Accuracy Over Time**:
   - Daily accuracy reports
   - Weekly accuracy trends
   - Asset-specific accuracy

### Testing Checklist

- [ ] Predictions generated for all assets
- [ ] Predictions include confidence scores
- [ ] Predictions are within reasonable range
- [ ] Accuracy tracked correctly
- [ ] Sentiment analysis working
- [ ] News integration working

### Test Scenarios

**Scenario 1: Prediction Generation**
1. Request prediction for XAUUSDT
2. Verify prediction includes:
   - Current price
   - Predicted price
   - Confidence score
   - Time horizon
3. Verify prediction is reasonable

**Scenario 2: Accuracy Tracking**
1. Generate predictions
2. Wait for actual prices
3. Calculate accuracy
4. Verify accuracy tracking
5. Check accuracy dashboard

---

## ⚠️ Risk Management Testing

### Stress Testing

1. **Maximum Position Size**:
   - Test with 100% portfolio allocation
   - Verify risk limits enforced
   - Test with multiple positions

2. **Stop Loss Testing**:
   - Set stop loss at 5%
   - Simulate price drop
   - Verify stop loss triggers

3. **Leverage Testing** (if applicable):
   - Test with different leverage ratios
   - Verify margin requirements
   - Test margin calls

### Testing Checklist

- [ ] Risk limits enforced
- [ ] Position size validation
- [ ] Stop loss triggers correctly
- [ ] Take profit triggers correctly
- [ ] Maximum drawdown limits
- [ ] Daily loss limits
- [ ] Risk warnings displayed

### Test Scenarios

**Scenario 1: Position Size Limits**
1. Set max position size to 10%
2. Try to place order for 20%
3. Verify order rejected
4. Adjust order to 8%
5. Verify order accepted

**Scenario 2: Stop Loss**
1. Place order with 5% stop loss
2. Simulate 6% price drop
3. Verify stop loss triggered
4. Check position closed
5. Verify loss calculated correctly

---

## 🔔 Notification System Testing

### Testing All Notification Types

1. **Trade Executed**:
   - Place order
   - Verify notification received
   - Check notification content

2. **Price Alert**:
   - Set price alert
   - Wait for price to reach target
   - Verify notification

3. **AI Signal**:
   - Generate AI signal
   - Verify notification
   - Check signal details

4. **Risk Alert**:
   - Trigger risk condition
   - Verify alert notification
   - Check alert priority

### Testing Checklist

- [ ] All notification types working
- [ ] Notifications delivered on time
- [ ] Notification content correct
- [ ] Unread count updates
- [ ] Mark as read works
- [ ] Delete notifications works
- [ ] Notification filters work
- [ ] Push notifications (if enabled)

### Test Scenarios

**Scenario 1: Trade Notifications**
1. Place order
2. Verify "Trade Executed" notification
3. Check notification details
4. Mark as read
5. Verify unread count decreases

**Scenario 2: Price Alerts**
1. Set price alert for BTCUSDT at $50,000
2. Wait for price to reach target
3. Verify alert notification
4. Check notification priority
5. Test multiple alerts

---

## 📊 Testing Tools

### Manual Testing

- **Postman/Thunder Client**: API endpoint testing
- **React Native Debugger**: App debugging
- **Expo Dev Tools**: Development tools

### Automated Testing

- **Jest**: Unit tests
- **React Native Testing Library**: Component tests
- **Detox**: E2E tests (optional)

### Monitoring

- **Sentry**: Error tracking
- **Analytics**: User behavior
- **Performance Monitoring**: App performance

---

## 📝 Test Reports

### Daily Testing

- Run smoke tests
- Check critical paths
- Verify API connectivity
- Test error scenarios

### Weekly Testing

- Full feature testing
- Performance testing
- Security testing
- User acceptance testing

### Monthly Testing

- Complete regression testing
- Load testing
- Stress testing
- Security audit

---

## 🐛 Bug Reporting

### Bug Report Template

```
**Title**: [Brief description]

**Environment**:
- Device: [iOS/Android/Web]
- OS Version: [Version]
- App Version: [Version]

**Steps to Reproduce**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior**:
[What should happen]

**Actual Behavior**:
[What actually happens]

**Screenshots**:
[If applicable]

**Logs**:
[Error logs if available]
```

---

## ✅ Testing Checklist

### Pre-Production

- [ ] All features tested
- [ ] Error handling verified
- [ ] Performance acceptable
- [ ] Security validated
- [ ] User acceptance testing complete
- [ ] Documentation updated
- [ ] Known issues documented

---

**Status**: ✅ Testing Guide Complete  
**Last Updated**: December 2025

*Made with 💎 in Cyprus*

