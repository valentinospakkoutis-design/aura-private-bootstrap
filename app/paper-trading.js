import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function PaperTradingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [portfolio, setPortfolio] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [history, setHistory] = useState([]);
  const [brokers, setBrokers] = useState([]);
  
  // Order placement state
  const [selectedBroker, setSelectedBroker] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [orderSide, setOrderSide] = useState('BUY');
  const [orderQuantity, setOrderQuantity] = useState('');
  const [currentPrice, setCurrentPrice] = useState(0);
  const [placingOrder, setPlacingOrder] = useState(false);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      // Load broker status
      const brokerStatus = await api.getBrokerStatus();
      setBrokers(brokerStatus.brokers || []);
      
      if (brokerStatus.brokers && brokerStatus.brokers.length > 0) {
        const firstBroker = brokerStatus.brokers[0].broker;
        setSelectedBroker(firstBroker);
        
        // Load portfolio
        const portfolioData = await api.get('/api/trading/portfolio');
        setPortfolio(portfolioData);
        
        // Load statistics
        const stats = await api.get('/api/paper-trading/statistics');
        setStatistics(stats);
        
        // Load history
        const historyData = await api.get('/api/trading/history?limit=20');
        setHistory(historyData.trades || []);
        
        // Load current price
        if (selectedSymbol) {
          try {
            const priceData = await api.getMarketPrice(firstBroker, selectedSymbol);
            setCurrentPrice(priceData.price || 0);
          } catch (e) {
            console.error('Error loading price:', e);
          }
        }
      }
    } catch (error) {
      console.error('Error loading data:', error);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handlePlaceOrder = async () => {
    if (!selectedBroker) {
      Alert.alert('Σφάλμα', 'Παρακαλώ συνδέστε πρώτα ένα broker');
      return;
    }

    if (!orderQuantity || parseFloat(orderQuantity) <= 0) {
      Alert.alert('Σφάλμα', 'Παρακαλώ εισάγετε έγκυρη ποσότητα');
      return;
    }

    setPlacingOrder(true);
    try {
      const result = await api.placeOrder(
        selectedBroker,
        selectedSymbol,
        orderSide,
        parseFloat(orderQuantity),
        'MARKET'
      );

      if (result.error) {
        Alert.alert('Σφάλμα', result.error);
      } else {
        Alert.alert('Επιτυχία', `Order executed: ${orderSide} ${orderQuantity} ${selectedSymbol}`);
        setOrderQuantity('');
        loadData();
      }
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία εκτέλεσης order');
    } finally {
      setPlacingOrder(false);
    }
  };

  const handleReset = () => {
    Alert.alert(
      'Επαναφορά Account',
      'Είστε σίγουροι ότι θέλετε να επαναφέρετε το paper trading account; Όλα τα trades θα διαγραφούν.',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Επαναφορά',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post('/api/paper-trading/reset', {});
              Alert.alert('Επιτυχία', 'Το account επαναφέρθηκε');
              loadData();
            } catch (error) {
              Alert.alert('Σφάλμα', 'Αποτυχία επαναφοράς');
            }
          }
        }
      ]
    );
  };

  const formatCurrency = (value) => {
    return `€${value.toFixed(2)}`;
  };

  const formatPercent = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  const getPnlColor = (value) => {
    if (value > 0) return '#4CAF50';
    if (value < 0) return '#ff6b6b';
    return '#999';
  };

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
          <Text style={styles.title}>📊 Paper Trading</Text>
        </View>

        {/* Portfolio Summary */}
        {portfolio && (
          <View style={styles.portfolioCard}>
            <Text style={styles.portfolioTitle}>💼 Portfolio</Text>
            
            <View style={styles.balanceRow}>
              <Text style={styles.balanceLabel}>Συνολική Αξία</Text>
              <Text style={styles.balanceValue}>
                {formatCurrency(portfolio.total_value)}
              </Text>
            </View>

            <View style={styles.balanceRow}>
              <Text style={styles.balanceLabel}>Μετρητά</Text>
              <Text style={styles.balanceValue}>
                {formatCurrency(portfolio.cash)}
              </Text>
            </View>

            <View style={styles.balanceRow}>
              <Text style={styles.balanceLabel}>Αξία Portfolio</Text>
              <Text style={styles.balanceValue}>
                {formatCurrency(portfolio.portfolio_value)}
              </Text>
            </View>

            <View style={styles.pnlRow}>
              <Text style={styles.pnlLabel}>Συνολικό P/L</Text>
              <Text style={[styles.pnlValue, { color: getPnlColor(portfolio.total_pnl) }]}>
                {formatCurrency(portfolio.total_pnl)} ({formatPercent(portfolio.total_pnl_percent)})
              </Text>
            </View>
          </View>
        )}

        {/* Statistics */}
        {statistics && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📈 Στατιστικά</Text>
            <View style={styles.statsGrid}>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{statistics.total_trades}</Text>
                <Text style={styles.statLabel}>Συνολικά Trades</Text>
              </View>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{statistics.active_positions}</Text>
                <Text style={styles.statLabel}>Ενεργές Θέσεις</Text>
              </View>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{statistics.buy_trades}</Text>
                <Text style={styles.statLabel}>Αγορές</Text>
              </View>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{statistics.sell_trades}</Text>
                <Text style={styles.statLabel}>Πωλήσεις</Text>
              </View>
            </View>
          </View>
        )}

        {/* Active Positions */}
        {portfolio && portfolio.positions && portfolio.positions.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Ενεργές Θέσεις</Text>
            {portfolio.positions.map((position, index) => (
              <View key={index} style={styles.positionItem}>
                <View style={styles.positionHeader}>
                  <Text style={styles.positionSymbol}>{position.symbol}</Text>
                  <Text style={[styles.positionPnl, { color: getPnlColor(position.pnl) }]}>
                    {formatCurrency(position.pnl)} ({formatPercent(position.pnl_percent)})
                  </Text>
                </View>
                <View style={styles.positionDetails}>
                  <Text style={styles.positionDetail}>
                    Ποσότητα: {position.quantity.toFixed(4)}
                  </Text>
                  <Text style={styles.positionDetail}>
                    Τιμή: {formatCurrency(position.current_price)}
                  </Text>
                  <Text style={styles.positionDetail}>
                    Αξία: {formatCurrency(position.value)}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Order Placement */}
        {brokers.length > 0 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>💰 Τοποθέτηση Order</Text>

            {/* Symbol Selection */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Symbol</Text>
              <TextInput
                style={styles.input}
                value={selectedSymbol}
                onChangeText={setSelectedSymbol}
                placeholder="BTCUSDT"
                placeholderTextColor="#666"
                autoCapitalize="characters"
              />
            </View>

            {/* Side Selection */}
            <View style={styles.sideSelector}>
              <TouchableOpacity
                style={[styles.sideButton, orderSide === 'BUY' && styles.sideButtonActive]}
                onPress={() => setOrderSide('BUY')}
              >
                <Text style={[styles.sideButtonText, orderSide === 'BUY' && styles.sideButtonTextActive]}>
                  🔵 BUY
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.sideButton, orderSide === 'SELL' && styles.sideButtonActive]}
                onPress={() => setOrderSide('SELL')}
              >
                <Text style={[styles.sideButtonText, orderSide === 'SELL' && styles.sideButtonTextActive]}>
                  🔴 SELL
                </Text>
              </TouchableOpacity>
            </View>

            {/* Quantity Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Ποσότητα</Text>
              <TextInput
                style={styles.input}
                value={orderQuantity}
                onChangeText={setOrderQuantity}
                placeholder="0.001"
                placeholderTextColor="#666"
                keyboardType="decimal-pad"
              />
            </View>

            {/* Current Price */}
            {currentPrice > 0 && (
              <View style={styles.priceInfo}>
                <Text style={styles.priceLabel}>Τρέχουσα Τιμή:</Text>
                <Text style={styles.priceValue}>{formatCurrency(currentPrice)}</Text>
              </View>
            )}

            {/* Place Order Button */}
            <TouchableOpacity
              style={[styles.orderButton, placingOrder && styles.orderButtonDisabled]}
              onPress={handlePlaceOrder}
              disabled={placingOrder}
            >
              {placingOrder ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.orderButtonText}>
                  {orderSide === 'BUY' ? '🛒 Αγορά' : '💰 Πώληση'}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>⚠️ Χρειάζεται Broker</Text>
            <Text style={styles.cardText}>
              Για να ξεκινήσετε paper trading, πρέπει πρώτα να συνδέσετε ένα broker.
            </Text>
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={() => router.push('/brokers')}
            >
              <Text style={styles.secondaryButtonText}>Σύνδεση Broker</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Trade History */}
        {history.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📜 Ιστορικό Trades</Text>
            {history.slice(0, 10).map((trade, index) => (
              <View key={index} style={styles.tradeItem}>
                <View style={styles.tradeHeader}>
                  <Text style={styles.tradeSymbol}>{trade.symbol}</Text>
                  <Text style={[
                    styles.tradeSide,
                    trade.side === 'BUY' ? styles.tradeSideBuy : styles.tradeSideSell
                  ]}>
                    {trade.side}
                  </Text>
                </View>
                <View style={styles.tradeDetails}>
                  <Text style={styles.tradeDetail}>
                    {trade.quantity.toFixed(4)} @ {formatCurrency(trade.price)}
                  </Text>
                  <Text style={styles.tradeTime}>
                    {new Date(trade.executed_at).toLocaleString('el-GR')}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Actions */}
        <TouchableOpacity
          style={styles.resetButton}
          onPress={handleReset}
        >
          <Text style={styles.resetButtonText}>🔄 Επαναφορά Account</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => router.push('/settings')}
        >
          <Text style={styles.secondaryButtonText}>⚙️ Ρυθμίσεις</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            💡 Paper Trading: Όλες οι συναλλαγές είναι προσομοιωμένες
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
  portfolioCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  portfolioTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  balanceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  balanceLabel: {
    fontSize: 14,
    color: '#999',
  },
  balanceValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  pnlRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 15,
    paddingTop: 15,
    borderTopWidth: 1,
    borderTopColor: '#2a2a2a',
  },
  pnlLabel: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  pnlValue: {
    fontSize: 16,
    fontWeight: 'bold',
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
  cardText: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  statItem: {
    width: '48%',
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
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
  positionItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  positionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  positionSymbol: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  positionPnl: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  positionDetails: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  positionDetail: {
    fontSize: 12,
    color: '#999',
    marginRight: 15,
  },
  inputGroup: {
    marginBottom: 15,
  },
  inputLabel: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 14,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#3a3a3a',
  },
  sideSelector: {
    flexDirection: 'row',
    marginBottom: 15,
    gap: 10,
  },
  sideButton: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 15,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3a3a3a',
  },
  sideButtonActive: {
    backgroundColor: '#4CAF50',
    borderColor: '#4CAF50',
  },
  sideButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#999',
  },
  sideButtonTextActive: {
    color: '#fff',
  },
  priceInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 12,
    marginBottom: 15,
  },
  priceLabel: {
    fontSize: 14,
    color: '#999',
  },
  priceValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  orderButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
  },
  orderButtonDisabled: {
    opacity: 0.5,
  },
  orderButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  tradeItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  tradeSymbol: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  tradeSide: {
    fontSize: 12,
    fontWeight: 'bold',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  tradeSideBuy: {
    backgroundColor: '#4CAF50',
    color: '#fff',
  },
  tradeSideSell: {
    backgroundColor: '#ff6b6b',
    color: '#fff',
  },
  tradeDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  tradeDetail: {
    fontSize: 12,
    color: '#999',
  },
  tradeTime: {
    fontSize: 12,
    color: '#666',
  },
  resetButton: {
    backgroundColor: '#3a1a1a',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#5a2a2a',
  },
  resetButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ff6b6b',
  },
  secondaryButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  secondaryButtonText: {
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
