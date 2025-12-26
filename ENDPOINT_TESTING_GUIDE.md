# 🧪 Endpoint Testing Guide

## 📋 Overview

Comprehensive endpoint-by-endpoint testing για production readiness.

---

## 🚀 Quick Start

### Test All Endpoints:

**Node.js:**
```bash
node scripts/test-endpoints.js
```

**PowerShell:**
```powershell
.\scripts\test-endpoints.ps1
```

**With Custom API URL:**
```bash
API_URL=https://your-api-url.com node scripts/test-endpoints.js
```

---

## 📊 Test Coverage

### Health & System (2 endpoints)
- ✅ `/health` - Health check
- ✅ `/api/system-status` - System status

### Quotes (1 endpoint)
- ✅ `/api/quote-of-day` - Daily quote

### AI Predictions (6 endpoints)
- ✅ `/api/ai/predict/{symbol}` - Single prediction
- ✅ `/api/ai/predictions` - All predictions
- ✅ `/api/ai/signal/{symbol}` - Trading signal
- ✅ `/api/ai/signals` - All signals
- ✅ `/api/ai/assets` - Available assets
- ✅ `/api/ai/status` - AI engine status

### Trading (4 endpoints)
- ✅ `/api/trading/portfolio` - Portfolio
- ✅ `/api/trading/history` - Trade history
- ✅ `/api/paper-trading/portfolio` - Paper trading portfolio
- ✅ `/api/paper-trading/statistics` - Paper trading stats

### Brokers (1 endpoint)
- ✅ `/api/brokers/status` - Broker status

### CMS (2 endpoints)
- ✅ `/api/cms/quotes` - CMS quotes
- ✅ `/api/cms/settings` - CMS settings

### Analytics (2 endpoints)
- ✅ `/api/analytics/performance` - Performance metrics
- ✅ `/api/analytics/symbols` - Symbol performance

### Notifications (2 endpoints)
- ✅ `/api/notifications` - Notifications list
- ✅ `/api/notifications/stats` - Notification stats

**Total: 20+ endpoints tested**

---

## 📋 Test Results Format

```
✅ GET  /health                                   200    45ms
✅ GET  /api/system-status                       200    52ms
✅ GET  /api/quote-of-day                         200    38ms
❌ GET  /api/ai/predict/XAUUSDT                   500    ERROR
...
📊 Results: 18/20 passed (90.0%)
```

---

## 🔍 What Gets Tested

### For Each Endpoint:
- ✅ **HTTP Status Code** (200 = success)
- ✅ **Response Time** (should be < 1000ms)
- ✅ **Response Format** (JSON validation)
- ✅ **Error Handling** (graceful failures)

---

## 🎯 Testing Scenarios

### 1. Local Testing
```bash
# Start backend locally
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# In another terminal
node scripts/test-endpoints.js
```

### 2. Staging Testing
```bash
API_URL=https://staging-api.aura.com node scripts/test-endpoints.js
```

### 3. Production Testing
```bash
API_URL=https://your-railway-url.railway.app node scripts/test-endpoints.js
```

---

## 📊 Expected Results

### All Endpoints Should:
- ✅ Return 200 status code
- ✅ Respond in < 1000ms
- ✅ Return valid JSON
- ✅ Handle errors gracefully

### Common Issues:
- ❌ **500 Error**: Backend error (check logs)
- ❌ **404 Error**: Endpoint not found (check path)
- ❌ **Timeout**: Backend not responding (check if running)
- ❌ **CORS Error**: CORS not configured (check backend)

---

## 🔧 Troubleshooting

### Issue: All endpoints fail
**Solution**: Check if backend is running and accessible

### Issue: Some endpoints fail
**Solution**: Check backend logs for specific errors

### Issue: CORS errors
**Solution**: Update backend CORS configuration

### Issue: Timeout errors
**Solution**: Check network connectivity and backend performance

---

## 📋 Pre-Production Checklist

- [ ] All endpoints return 200
- [ ] Response times < 1000ms
- [ ] No CORS errors
- [ ] Error handling works
- [ ] All AI endpoints functional
- [ ] All trading endpoints functional

---

## 🎯 Next Steps

1. ✅ Run endpoint tests
2. ✅ Fix any failures
3. ✅ Verify all endpoints work
4. ✅ Proceed to production build

---

**Status**: ✅ Testing suite ready!

*Made with 💎 in Cyprus*

