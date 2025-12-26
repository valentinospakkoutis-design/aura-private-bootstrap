// Endpoint Testing Suite
// Tests all API endpoints for production readiness

const BASE_URL = process.env.API_URL || 'http://localhost:8000';

const ENDPOINTS = {
  // Health & System
  health: { method: 'GET', path: '/health', auth: false },
  systemStatus: { method: 'GET', path: '/api/system-status', auth: false },
  
  // Quotes
  quoteOfDay: { method: 'GET', path: '/api/quote-of-day', auth: false },
  
  // AI Predictions
  aiPredict: { method: 'GET', path: '/api/ai/predict/XAUUSDT', auth: false },
  aiPredictions: { method: 'GET', path: '/api/ai/predictions', auth: false },
  aiSignal: { method: 'GET', path: '/api/ai/signal/XAUUSDT', auth: false },
  aiSignals: { method: 'GET', path: '/api/ai/signals', auth: false },
  aiAssets: { method: 'GET', path: '/api/ai/assets', auth: false },
  aiStatus: { method: 'GET', path: '/api/ai/status', auth: false },
  
  // Trading
  portfolio: { method: 'GET', path: '/api/trading/portfolio', auth: false },
  tradingHistory: { method: 'GET', path: '/api/trading/history', auth: false },
  paperTradingPortfolio: { method: 'GET', path: '/api/paper-trading/portfolio', auth: false },
  paperTradingStats: { method: 'GET', path: '/api/paper-trading/statistics', auth: false },
  
  // Brokers
  brokerStatus: { method: 'GET', path: '/api/brokers/status', auth: false },
  
  // CMS
  quotes: { method: 'GET', path: '/api/cms/quotes', auth: false },
  cmsSettings: { method: 'GET', path: '/api/cms/settings', auth: false },
  
  // Analytics
  analyticsPerformance: { method: 'GET', path: '/api/analytics/performance', auth: false },
  analyticsSymbols: { method: 'GET', path: '/api/analytics/symbols', auth: false },
  
  // Notifications
  notifications: { method: 'GET', path: '/api/notifications', auth: false },
  notificationStats: { method: 'GET', path: '/api/notifications/stats', auth: false },
};

async function testEndpoint(name, config) {
  const url = `${BASE_URL}${config.path}`;
  const options = {
    method: config.method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  try {
    const startTime = Date.now();
    const response = await fetch(url, options);
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    let data;
    try {
      data = await response.json();
    } catch {
      data = { text: await response.text() };
    }

    const success = response.ok;
    const status = {
      name,
      path: config.path,
      method: config.method,
      status: response.status,
      success,
      duration: `${duration}ms`,
      data: success ? '✓' : JSON.stringify(data).substring(0, 100),
    };

    return status;
  } catch (error) {
    return {
      name,
      path: config.path,
      method: config.method,
      status: 'ERROR',
      success: false,
      duration: 'N/A',
      data: error.message,
    };
  }
}

async function runTests() {
  console.log('🧪 Testing API Endpoints...\n');
  console.log(`Base URL: ${BASE_URL}\n`);
  console.log('─'.repeat(80));

  const results = [];
  
  for (const [name, config] of Object.entries(ENDPOINTS)) {
    const result = await testEndpoint(name, config);
    results.push(result);
    
    const icon = result.success ? '✅' : '❌';
    console.log(`${icon} ${result.method.padEnd(4)} ${result.path.padEnd(40)} ${result.status.toString().padStart(3)} ${result.duration.padStart(8)}`);
    
    // Small delay to avoid rate limiting
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  console.log('─'.repeat(80));
  
  const successCount = results.filter(r => r.success).length;
  const totalCount = results.length;
  const successRate = ((successCount / totalCount) * 100).toFixed(1);
  
  console.log(`\n📊 Results: ${successCount}/${totalCount} passed (${successRate}%)`);
  
  const failures = results.filter(r => !r.success);
  if (failures.length > 0) {
    console.log('\n❌ Failed Endpoints:');
    failures.forEach(f => {
      console.log(`   ${f.method} ${f.path} - ${f.status} - ${f.data}`);
    });
  }
  
  return { success: failures.length === 0, results };
}

// Run if called directly
if (require.main === module) {
  runTests().then(({ success }) => {
    process.exit(success ? 0 : 1);
  });
}

module.exports = { runTests, ENDPOINTS };

