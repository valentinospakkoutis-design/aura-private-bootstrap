import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, ActivityIndicator, RefreshControl, Switch } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function LiveTradingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tradingMode, setTradingMode] = useState('paper');
  const [riskSettings, setRiskSettings] = useState(null);
  const [riskSummary, setRiskSummary] = useState(null);
  const [switchingMode, setSwitchingMode] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load trading mode
      const modeData = await api.get('/api/trading/mode');
      setTradingMode(modeData.mode);
      
      // Load risk settings
      const riskData = await api.get('/api/trading/risk-settings');
      setRiskSettings(riskData.risk_settings);
      
      // Load risk summary
      const summary = await api.get('/api/trading/risk-summary');
      setRiskSummary(summary);
    } catch (error) {
      console.error('Error loading trading data:', error);
      Alert.alert('Σφάλμα', 'Αποτυχία φόρτωσης δεδομένων');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleModeSwitch = async (newMode) => {
    if (newMode === 'live') {
      Alert.alert(
        '⚠️ Live Trading',
        'Είστε σίγουροι ότι θέλετε να ενεργοποιήσετε το Live Trading;\n\n' +
        'Αυτό θα εκτελέσει πραγματικές συναλλαγές με πραγματικά χρήματα.\n\n' +
        'Βεβαιωθείτε ότι:\n' +
        '• Έχετε ρυθμίσει risk management\n' +
        '• Έχετε δοκιμάσει Paper Trading\n' +
        '• Κατανοείτε τους κινδύνους',
        [
          { text: 'Ακύρωση', style: 'cancel' },
          {
            text: 'Ενεργοποίηση',
            style: 'destructive',
            onPress: async () => {
              await switchMode(newMode);
            }
          }
        ]
      );
    } else {
      await switchMode(newMode);
    }
  };

  const switchMode = async (mode) => {
    try {
      setSwitchingMode(true);
      const result = await api.post('/api/trading/mode', { mode });
      setTradingMode(mode);
      Alert.alert('Επιτυχία', result.message || `Trading mode set to ${mode}`);
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία αλλαγής mode');
    } finally {
      setSwitchingMode(false);
    }
  };

  const formatCurrency = (value) => {
    return `€${value.toFixed(2)}`;
  };

  const formatPercent = (value) => {
    return `${value.toFixed(2)}%`;
  };

  if (loading && !tradingMode) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση Live Trading...</Text>
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
          <Text style={styles.title}>💰 Live Trading</Text>
        </View>

        {/* Trading Mode Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🎯 Trading Mode</Text>
          
          <View style={styles.modeSelector}>
            <TouchableOpacity
              style={[
                styles.modeButton,
                tradingMode === 'paper' && styles.modeButtonActive
              ]}
              onPress={() => handleModeSwitch('paper')}
              disabled={switchingMode}
            >
              <Text style={[
                styles.modeButtonText,
                tradingMode === 'paper' && styles.modeButtonTextActive
              ]}>
                📝 Paper Trading
              </Text>
              <Text style={styles.modeButtonSubtext}>Simulated</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[
                styles.modeButton,
                tradingMode === 'live' && styles.modeButtonActive,
                tradingMode === 'live' && styles.modeButtonLive
              ]}
              onPress={() => handleModeSwitch('live')}
              disabled={switchingMode}
            >
              <Text style={[
                styles.modeButtonText,
                tradingMode === 'live' && styles.modeButtonTextActive
              ]}>
                ⚡ Live Trading
              </Text>
              <Text style={styles.modeButtonSubtext}>Real Money</Text>
            </TouchableOpacity>
          </View>

          {switchingMode && (
            <View style={styles.switchingIndicator}>
              <ActivityIndicator size="small" color="#4CAF50" />
              <Text style={styles.switchingText}>Switching mode...</Text>
            </View>
          )}

          {tradingMode === 'live' && (
            <View style={styles.warningBox}>
              <Text style={styles.warningText}>
                ⚠️ LIVE TRADING ACTIVE - Real money at risk!
              </Text>
            </View>
          )}
        </View>

        {/* Risk Summary */}
        {riskSummary && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Risk Summary</Text>
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Portfolio Value</Text>
              <Text style={styles.summaryValue}>
                {formatCurrency(riskSummary.portfolio_value)}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Max Position Size</Text>
              <Text style={styles.summaryValue}>
                {formatCurrency(riskSummary.max_position_value)}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Max Daily Loss</Text>
              <Text style={[styles.summaryValue, { color: '#ff6b6b' }]}>
                {formatCurrency(riskSummary.max_daily_loss)}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Available Risk</Text>
              <Text style={[
                styles.summaryValue,
                { color: riskSummary.available_risk ? '#4CAF50' : '#ff6b6b' }
              ]}>
                {riskSummary.available_risk ? '✅ Available' : '❌ Limit Reached'}
              </Text>
            </View>
          </View>
        )}

        {/* Risk Settings */}
        {riskSettings && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>⚙️ Risk Management Settings</Text>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Max Position Size</Text>
              <Text style={styles.settingValue}>
                {formatPercent(riskSettings.max_position_size_percent)}
              </Text>
            </View>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Max Daily Loss</Text>
              <Text style={styles.settingValue}>
                {formatPercent(riskSettings.max_daily_loss_percent)}
              </Text>
            </View>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Stop Loss</Text>
              <Text style={styles.settingValue}>
                {formatPercent(riskSettings.stop_loss_percent)}
              </Text>
            </View>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Take Profit</Text>
              <Text style={styles.settingValue}>
                {formatPercent(riskSettings.take_profit_percent)}
              </Text>
            </View>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Max Open Positions</Text>
              <Text style={styles.settingValue}>
                {riskSettings.max_open_positions}
              </Text>
            </View>
            
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Require Confirmation</Text>
              <Text style={styles.settingValue}>
                {riskSettings.require_confirmation ? '✅ Yes' : '❌ No'}
              </Text>
            </View>

            <TouchableOpacity
              style={styles.editButton}
              onPress={() => Alert.alert('Info', 'Risk settings editing coming soon')}
            >
              <Text style={styles.editButtonText}>✏️ Edit Settings</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Daily Stats */}
        {riskSummary && riskSummary.daily_stats && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📈 Daily Statistics</Text>
            
            <View style={styles.statsGrid}>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>
                  {riskSummary.daily_stats.total_trades}
                </Text>
                <Text style={styles.statLabel}>Total Trades</Text>
              </View>
              
              <View style={styles.statBox}>
                <Text style={[styles.statValue, { color: '#4CAF50' }]}>
                  {riskSummary.daily_stats.winning_trades}
                </Text>
                <Text style={styles.statLabel}>Wins</Text>
              </View>
              
              <View style={styles.statBox}>
                <Text style={[styles.statValue, { color: '#ff6b6b' }]}>
                  {riskSummary.daily_stats.losing_trades}
                </Text>
                <Text style={styles.statLabel}>Losses</Text>
              </View>
              
              <View style={styles.statBox}>
                <Text style={[
                  styles.statValue,
                  { color: riskSummary.daily_stats.total_pnl >= 0 ? '#4CAF50' : '#ff6b6b' }
                ]}>
                  {formatCurrency(riskSummary.daily_stats.total_pnl)}
                </Text>
                <Text style={styles.statLabel}>P/L</Text>
              </View>
            </View>
          </View>
        )}

        {/* Safety Info */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>🛡️ Safety Features</Text>
          <Text style={styles.infoText}>
            Το Live Trading περιλαμβάνει:
          </Text>
          <Text style={styles.infoText}>• Automatic position sizing</Text>
          <Text style={styles.infoText}>• Stop loss & take profit</Text>
          <Text style={styles.infoText}>• Daily loss limits</Text>
          <Text style={styles.infoText}>• Order validation</Text>
          <Text style={styles.infoText}>• Confirmation requirements</Text>
        </View>

        {/* Quick Actions */}
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push('/paper-trading')}
        >
          <Text style={styles.actionButtonText}>📊 Go to Trading</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            ⚠️ Live Trading involves real financial risk. Trade responsibly.
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
  modeSelector: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 15,
  },
  modeButton: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  modeButtonActive: {
    borderColor: '#4CAF50',
    backgroundColor: '#2a3a2a',
  },
  modeButtonLive: {
    borderColor: '#ff6b6b',
  },
  modeButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#999',
    marginBottom: 5,
  },
  modeButtonTextActive: {
    color: '#fff',
  },
  modeButtonSubtext: {
    fontSize: 12,
    color: '#666',
  },
  switchingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    gap: 10,
  },
  switchingText: {
    fontSize: 12,
    color: '#999',
  },
  warningBox: {
    backgroundColor: '#3a1a1a',
    borderRadius: 8,
    padding: 12,
    marginTop: 15,
    borderWidth: 1,
    borderColor: '#ff6b6b',
  },
  warningText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#ff6b6b',
    textAlign: 'center',
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  summaryLabel: {
    fontSize: 14,
    color: '#999',
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  settingLabel: {
    fontSize: 14,
    color: '#999',
  },
  settingValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  editButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginTop: 15,
  },
  editButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statBox: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  statLabel: {
    fontSize: 12,
    color: '#999',
  },
  infoCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
  },
  infoText: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
    marginBottom: 5,
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

