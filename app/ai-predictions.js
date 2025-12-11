import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function AIPredictionsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [predictions, setPredictions] = useState({});
  const [signals, setSignals] = useState({});
  const [aiStatus, setAiStatus] = useState(null);
  const [selectedMetal, setSelectedMetal] = useState('XAUUSDT');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load AI status
      const status = await api.get('/api/ai/status');
      setAiStatus(status);
      
      // Load all predictions
      const predictionsData = await api.get('/api/ai/predictions?days=7');
      setPredictions(predictionsData.predictions || {});
      
      // Load all signals
      const signalsData = await api.get('/api/ai/signals');
      setSignals(signalsData.signals || {});
    } catch (error) {
      console.error('Error loading AI data:', error);
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

  const getTrendColor = (trend) => {
    if (trend === 'BULLISH') return '#4CAF50';
    if (trend === 'BEARISH') return '#ff6b6b';
    return '#FFA726';
  };

  const getSignalColor = (signal) => {
    if (signal === 'BUY') return '#4CAF50';
    if (signal === 'SELL') return '#ff6b6b';
    return '#999';
  };

  const getStrengthColor = (strength) => {
    if (strength === 'STRONG') return '#4CAF50';
    if (strength === 'MODERATE') return '#FFA726';
    return '#999';
  };

  const metals = [
    { symbol: 'XAUUSDT', name: 'Χρυσός', icon: '🥇' },
    { symbol: 'XAGUSDT', name: 'Άργυρος', icon: '🥈' },
    { symbol: 'XPTUSDT', name: 'Πλατίνα', icon: '💎' },
    { symbol: 'XPDUSDT', name: 'Παλλάδιο', icon: '✨' },
  ];

  if (loading && !predictions) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση AI Predictions...</Text>
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
          <Text style={styles.title}>🤖 AI Predictions</Text>
        </View>

        {/* AI Status */}
        {aiStatus && (
          <View style={styles.statusCard}>
            <View style={styles.statusHeader}>
              <Text style={styles.statusTitle}>AI Engine Status</Text>
              <View style={styles.statusBadge}>
                <Text style={styles.statusBadgeText}>ACTIVE</Text>
              </View>
            </View>
            <Text style={styles.statusText}>
              Model: {aiStatus.model_version} | Accuracy: {aiStatus.accuracy_estimate}
            </Text>
          </View>
        )}

        {/* Trading Signals Overview */}
        {signals && Object.keys(signals).length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Trading Signals</Text>
            {metals.map((metal) => {
              const signal = signals[metal.symbol];
              if (!signal || signal.error) return null;
              
              return (
                <TouchableOpacity
                  key={metal.symbol}
                  style={styles.signalCard}
                  onPress={() => setSelectedMetal(metal.symbol)}
                >
                  <View style={styles.signalHeader}>
                    <Text style={styles.signalIcon}>{metal.icon}</Text>
                    <View style={styles.signalInfo}>
                      <Text style={styles.signalName}>{metal.name}</Text>
                      <Text style={styles.signalSymbol}>{metal.symbol}</Text>
                    </View>
                    <View style={[styles.signalBadge, { backgroundColor: getSignalColor(signal.signal) }]}>
                      <Text style={styles.signalBadgeText}>{signal.signal}</Text>
                    </View>
                  </View>
                  <View style={styles.signalDetails}>
                    <Text style={styles.signalDetail}>
                      Strength: <Text style={{ color: getStrengthColor(signal.strength) }}>
                        {signal.strength}
                      </Text>
                    </Text>
                    <Text style={styles.signalDetail}>
                      Confidence: {signal.confidence}%
                    </Text>
                    <Text style={styles.signalDetail}>
                      Expected: {formatPercent(signal.expected_return_pct)}
                    </Text>
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Detailed Prediction for Selected Metal */}
        {predictions[selectedMetal] && !predictions[selectedMetal].error && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              📈 Detailed Prediction: {predictions[selectedMetal].metal_name}
            </Text>

            {/* Current vs Predicted */}
            <View style={styles.predictionRow}>
              <View style={styles.priceBox}>
                <Text style={styles.priceLabel}>Τρέχουσα Τιμή</Text>
                <Text style={styles.priceValue}>
                  {formatCurrency(predictions[selectedMetal].current_price)}
                </Text>
              </View>
              <View style={styles.priceBox}>
                <Text style={styles.priceLabel}>Προβλεπόμενη (7d)</Text>
                <Text style={[styles.priceValue, { color: getTrendColor(predictions[selectedMetal].trend) }]}>
                  {formatCurrency(predictions[selectedMetal].predicted_price)}
                </Text>
              </View>
            </View>

            {/* Change */}
            <View style={styles.changeRow}>
              <Text style={styles.changeLabel}>Αλλαγή</Text>
              <Text style={[styles.changeValue, { color: getTrendColor(predictions[selectedMetal].trend) }]}>
                {formatCurrency(predictions[selectedMetal].price_change)} ({formatPercent(predictions[selectedMetal].price_change_percent)})
              </Text>
            </View>

            {/* Trend & Confidence */}
            <View style={styles.metricsRow}>
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>Trend</Text>
                <Text style={[styles.metricValue, { color: getTrendColor(predictions[selectedMetal].trend) }]}>
                  {predictions[selectedMetal].trend}
                </Text>
              </View>
              <View style={styles.metricBox}>
                <Text style={styles.metricLabel}>Confidence</Text>
                <Text style={styles.metricValue}>
                  {predictions[selectedMetal].confidence}%
                </Text>
              </View>
            </View>

            {/* Recommendation */}
            <View style={styles.recommendationBox}>
              <Text style={styles.recommendationLabel}>AI Recommendation</Text>
              <View style={styles.recommendationRow}>
                <Text style={[styles.recommendationSignal, { color: getSignalColor(predictions[selectedMetal].recommendation) }]}>
                  {predictions[selectedMetal].recommendation}
                </Text>
                <Text style={[styles.recommendationStrength, { color: getStrengthColor(predictions[selectedMetal].recommendation_strength) }]}>
                  {predictions[selectedMetal].recommendation_strength}
                </Text>
              </View>
            </View>

            {/* Price Path */}
            {predictions[selectedMetal].price_path && (
              <View style={styles.pricePathBox}>
                <Text style={styles.pricePathTitle}>Price Path (7 days)</Text>
                <View style={styles.pricePathContainer}>
                  {predictions[selectedMetal].price_path.map((point, index) => (
                    <View key={index} style={styles.pricePathPoint}>
                      <Text style={styles.pricePathValue}>
                        {formatCurrency(point.price)}
                      </Text>
                      <Text style={styles.pricePathDay}>Day {point.day}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
          </View>
        )}

        {/* Metal Selection */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🔍 Επιλογή Metal</Text>
          <View style={styles.metalSelector}>
            {metals.map((metal) => (
              <TouchableOpacity
                key={metal.symbol}
                style={[
                  styles.metalOption,
                  selectedMetal === metal.symbol && styles.metalOptionActive
                ]}
                onPress={() => setSelectedMetal(metal.symbol)}
              >
                <Text style={styles.metalIcon}>{metal.icon}</Text>
                <Text style={[
                  styles.metalName,
                  selectedMetal === metal.symbol && styles.metalNameActive
                ]}>
                  {metal.name}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Quick Actions */}
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push('/paper-trading')}
        >
          <Text style={styles.actionButtonText}>📊 Paper Trading</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            ⚠️ AI Predictions are for informational purposes only. Not financial advice.
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
  statusCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  statusHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  statusTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  statusBadge: {
    backgroundColor: '#4CAF50',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  statusText: {
    fontSize: 14,
    color: '#999',
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
  signalCard: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  signalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  signalIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  signalInfo: {
    flex: 1,
  },
  signalName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  signalSymbol: {
    fontSize: 12,
    color: '#999',
  },
  signalBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  signalBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  signalDetails: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  signalDetail: {
    fontSize: 12,
    color: '#999',
    marginRight: 15,
  },
  predictionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 15,
    gap: 10,
  },
  priceBox: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    alignItems: 'center',
  },
  priceLabel: {
    fontSize: 12,
    color: '#999',
    marginBottom: 8,
  },
  priceValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  changeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  changeLabel: {
    fontSize: 14,
    color: '#999',
  },
  changeValue: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 15,
    gap: 10,
  },
  metricBox: {
    flex: 1,
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
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  recommendationBox: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
  },
  recommendationLabel: {
    fontSize: 12,
    color: '#999',
    marginBottom: 10,
  },
  recommendationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  recommendationSignal: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  recommendationStrength: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  pricePathBox: {
    marginTop: 15,
  },
  pricePathTitle: {
    fontSize: 14,
    color: '#999',
    marginBottom: 10,
  },
  pricePathContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  pricePathPoint: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 10,
    minWidth: 80,
    alignItems: 'center',
  },
  pricePathValue: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 4,
  },
  pricePathDay: {
    fontSize: 10,
    color: '#999',
  },
  metalSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metalOption: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  metalOptionActive: {
    borderColor: '#4CAF50',
    backgroundColor: '#2a3a2a',
  },
  metalIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  metalName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#999',
  },
  metalNameActive: {
    color: '#4CAF50',
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
    fontStyle: 'italic',
  },
});

