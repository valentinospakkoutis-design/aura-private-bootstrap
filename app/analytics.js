import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function AnalyticsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [symbolPerformance, setSymbolPerformance] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('daily');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load performance metrics
      const metricsData = await api.get('/api/analytics/performance');
      setMetrics(metricsData);
      
      // Load symbol performance
      const symbolData = await api.get('/api/analytics/symbols');
      setSymbolPerformance(symbolData.symbols || []);
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const formatCurrency = (value) => {
    return `€${value.toFixed(2)}`;
  };

  const formatPercent = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  const getMetricColor = (value, isPositive = true) => {
    if (isPositive) {
      return value >= 0 ? '#4CAF50' : '#ff6b6b';
    }
    return '#fff';
  };

  if (loading && !metrics) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση Analytics...</Text>
        </View>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>📊 Analytics</Text>
        </View>

        {/* Key Metrics */}
        {metrics && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📈 Key Performance Metrics</Text>
            
            <View style={styles.metricsGrid}>
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>Total P/L</Text>
                <Text style={[styles.metricValue, { color: getMetricColor(metrics.total_pnl) }]}>
                  {formatCurrency(metrics.total_pnl)}
                </Text>
                <Text style={[styles.metricSubtext, { color: getMetricColor(metrics.total_pnl_percent) }]}>
                  {formatPercent(metrics.total_pnl_percent)}
                </Text>
              </View>
              
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>Win Rate</Text>
                <Text style={[styles.metricValue, { color: metrics.win_rate >= 50 ? '#4CAF50' : '#ff6b6b' }]}>
                  {metrics.win_rate.toFixed(1)}%
                </Text>
                <Text style={styles.metricSubtext}>
                  {metrics.winning_trades}W / {metrics.losing_trades}L
                </Text>
              </View>
              
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>ROI</Text>
                <Text style={[styles.metricValue, { color: getMetricColor(metrics.roi) }]}>
                  {formatPercent(metrics.roi)}
                </Text>
                <Text style={styles.metricSubtext}>Return</Text>
              </View>
              
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>Sharpe Ratio</Text>
                <Text style={[styles.metricValue, { color: metrics.sharpe_ratio >= 1 ? '#4CAF50' : '#FFA726' }]}>
                  {metrics.sharpe_ratio.toFixed(2)}
                </Text>
                <Text style={styles.metricSubtext}>Risk-Adjusted</Text>
              </View>
            </View>
          </View>
        )}

        {/* Detailed Metrics */}
        {metrics && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Detailed Metrics</Text>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Total Trades</Text>
              <Text style={styles.detailValue}>{metrics.total_trades}</Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Profit Factor</Text>
              <Text style={[styles.detailValue, { color: metrics.profit_factor >= 1 ? '#4CAF50' : '#ff6b6b' }]}>
                {metrics.profit_factor.toFixed(2)}
              </Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Average Win</Text>
              <Text style={[styles.detailValue, { color: '#4CAF50' }]}>
                {formatCurrency(metrics.avg_win)}
              </Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Average Loss</Text>
              <Text style={[styles.detailValue, { color: '#ff6b6b' }]}>
                {formatCurrency(metrics.avg_loss)}
              </Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Expectancy</Text>
              <Text style={[styles.detailValue, { color: getMetricColor(metrics.expectancy) }]}>
                {formatCurrency(metrics.expectancy)}
              </Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Max Drawdown</Text>
              <Text style={[styles.detailValue, { color: '#ff6b6b' }]}>
                {formatPercent(metrics.max_drawdown_percent)}
              </Text>
            </View>
            
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Avg Trade Size</Text>
              <Text style={styles.detailValue}>
                {formatCurrency(metrics.avg_trade_size)}
              </Text>
            </View>
          </View>
        )}

        {/* Insights */}
        {metrics && metrics.insights && metrics.insights.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>💡 Trading Insights</Text>
            
            {metrics.insights.map((insight, index) => (
              <View key={index} style={styles.insightItem}>
                <Text style={styles.insightText}>{insight}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Symbol Performance */}
        {symbolPerformance.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Performance by Symbol</Text>
            
            {symbolPerformance.slice(0, 10).map((symbol, index) => (
              <View key={index} style={styles.symbolItem}>
                <View style={styles.symbolHeader}>
                  <Text style={styles.symbolName}>{symbol.symbol}</Text>
                  <Text style={[styles.symbolPnl, { color: getMetricColor(symbol.total_pnl) }]}>
                    {formatCurrency(symbol.total_pnl)}
                  </Text>
                </View>
                
                <View style={styles.symbolDetails}>
                  <Text style={styles.symbolDetail}>
                    {symbol.total_trades} trades ({symbol.buy_trades}B / {symbol.sell_trades}S)
                  </Text>
                  <Text style={styles.symbolDetail}>
                    Avg: {formatCurrency(symbol.avg_pnl)}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Quick Actions */}
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push('/paper-trading')}
        >
          <Text style={styles.actionButtonText}>📊 View Trading</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            📊 Analytics - Track your trading performance
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  content: {
    padding: 20,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    color: '#999',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 30,
    marginTop: 10,
  },
  backButton: {
    marginRight: 15,
    padding: 5,
  },
  backButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  card: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricBox: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: 12,
    color: '#999',
    marginBottom: 8,
  },
  metricValue: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  metricSubtext: {
    fontSize: 11,
    color: '#666',
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  detailLabel: {
    fontSize: 14,
    color: '#999',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  insightItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
  },
  insightText: {
    fontSize: 14,
    color: '#fff',
    lineHeight: 20,
  },
  symbolItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  symbolHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  symbolName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  symbolPnl: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  symbolDetails: {
    flexDirection: 'row',
    gap: 15,
  },
  symbolDetail: {
    fontSize: 12,
    color: '#999',
  },
  actionButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  actionButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
});

