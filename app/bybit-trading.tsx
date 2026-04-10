import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TextInput, TouchableOpacity } from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { Button } from '../mobile/src/components/Button';
import { theme } from '../mobile/src/constants/theme';
import { useAppStore } from '../mobile/src/stores/appStore';

const LEVERAGE_OPTIONS = [1, 2, 5, 10];

export default function BybitTradingScreen() {
  const { showToast } = useAppStore();
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [side, setSide] = useState<'Buy' | 'Sell'>('Buy');
  const [quantity, setQuantity] = useState('0.001');
  const [leverage, setLeverage] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  const [balance, setBalance] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [bal, pos] = await Promise.all([
        api.getBybitBalance().catch(() => null),
        api.getBybitPositions().catch(() => ({ positions: [] })),
      ]);
      setBalance(bal);
      setPositions(pos?.positions || []);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '';
      if (msg.includes('not connected') || msg.includes('400')) {
        setError('Bybit not connected. Go to Brokers to connect.');
      } else {
        setError(msg || 'Failed to load Bybit data');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const handlePlaceOrder = useCallback(async () => {
    const qty = parseFloat(quantity);
    if (!symbol.trim()) { showToast('Enter symbol', 'error'); return; }
    if (isNaN(qty) || qty <= 0) { showToast('Enter valid quantity', 'error'); return; }

    try {
      setSubmitting(true);
      await api.placeBybitOrder(symbol.toUpperCase().trim(), side, qty, leverage);
      showToast(`${side} ${qty} ${symbol} @ ${leverage}x executed!`, 'success');
      setQuantity('0.001');
      await loadData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Order failed';
      showToast(typeof msg === 'string' ? msg : JSON.stringify(msg), 'error');
    } finally {
      setSubmitting(false);
    }
  }, [symbol, side, quantity, leverage, showToast, loadData]);

  if (loading) {
    return (
      <View style={s.container}>
        <View style={s.center}><Text style={s.loadingText}>Loading Bybit...</Text></View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={s.container}>
        <View style={s.center}>
          <Text style={{ fontSize: 48, marginBottom: 16 }}>🔗</Text>
          <Text style={s.errorText}>{error}</Text>
          <Button title="Retry" onPress={loadData} variant="primary" size="medium" style={{ marginTop: 16 }} />
        </View>
      </View>
    );
  }

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={s.content}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />}
    >
      {/* Balance */}
      {balance && (
        <View style={s.card}>
          <Text style={s.cardTitle}>Bybit Wallet</Text>
          <View style={s.row}>
            <View style={s.statItem}>
              <Text style={s.statLabel}>Total Equity</Text>
              <Text style={s.statValue}>${(balance.total_equity || 0).toFixed(2)}</Text>
            </View>
            {balance.coins?.slice(0, 3).map((c: any) => (
              <View key={c.symbol} style={s.statItem}>
                <Text style={s.statLabel}>{c.symbol}</Text>
                <Text style={s.statValue}>${(c.usd_value || 0).toFixed(2)}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Order Form */}
      <View style={s.card}>
        <Text style={s.cardTitle}>New Bybit Order</Text>

        <View style={s.formRow}>
          <Text style={s.formLabel}>Symbol</Text>
          <TextInput style={s.input} value={symbol} onChangeText={setSymbol}
            placeholder="BTCUSDT" placeholderTextColor="#999"
            autoCapitalize="characters" autoCorrect={false} editable={true} />
        </View>

        <View style={s.formRow}>
          <Text style={s.formLabel}>Side</Text>
          <View style={s.toggleRow}>
            <TouchableOpacity style={[s.toggleBtn, side === 'Buy' && s.buyActive]} onPress={() => setSide('Buy')}>
              <Text style={[s.toggleText, side === 'Buy' && s.toggleTextActive]}>BUY</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.toggleBtn, side === 'Sell' && s.sellActive]} onPress={() => setSide('Sell')}>
              <Text style={[s.toggleText, side === 'Sell' && s.toggleTextActive]}>SELL</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={s.formRow}>
          <Text style={s.formLabel}>Quantity</Text>
          <TextInput style={s.input} value={quantity} onChangeText={setQuantity}
            placeholder="0.001" placeholderTextColor="#999"
            keyboardType="decimal-pad" returnKeyType="done" autoCorrect={false} editable={true} />
        </View>

        <View style={s.formRow}>
          <Text style={s.formLabel}>Leverage</Text>
          <View style={s.toggleRow}>
            {LEVERAGE_OPTIONS.map((lev) => (
              <TouchableOpacity key={lev} style={[s.levBtn, leverage === lev && s.levActive]} onPress={() => setLeverage(lev)}>
                <Text style={[s.levText, leverage === lev && s.levTextActive]}>{lev}x</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <Button
          title={submitting ? 'Executing...' : `${side.toUpperCase()} ${symbol} @ ${leverage}x`}
          onPress={handlePlaceOrder}
          variant={side === 'Buy' ? 'primary' : 'secondary'}
          size="large" fullWidth
          disabled={submitting || !quantity.trim()}
          loading={submitting}
        />
      </View>

      {/* Positions */}
      <Text style={s.sectionTitle}>Open Positions ({positions.length})</Text>
      {positions.length === 0 ? (
        <View style={s.emptyCard}>
          <Text style={{ fontSize: 32, marginBottom: 8 }}>📊</Text>
          <Text style={s.emptyText}>No open Bybit positions</Text>
        </View>
      ) : (
        positions.map((pos: any, i: number) => {
          const pnl = pos.unrealised_pnl || 0;
          return (
            <View key={i} style={s.card}>
              <View style={s.posHeader}>
                <Text style={s.posSymbol}>{pos.symbol}</Text>
                <View style={[s.posBadge, { backgroundColor: pos.side === 'Buy' ? theme.colors.market.bullish + '20' : theme.colors.market.bearish + '20' }]}>
                  <Text style={{ color: pos.side === 'Buy' ? theme.colors.market.bullish : theme.colors.market.bearish, fontWeight: '700', fontSize: 12 }}>
                    {pos.side === 'Buy' ? 'LONG' : 'SHORT'}
                  </Text>
                </View>
              </View>
              <View style={s.row}>
                <View style={s.statItem}>
                  <Text style={s.statLabel}>Size</Text>
                  <Text style={s.statValue}>{pos.size}</Text>
                </View>
                <View style={s.statItem}>
                  <Text style={s.statLabel}>Entry</Text>
                  <Text style={s.statValue}>${pos.entry_price?.toFixed(2)}</Text>
                </View>
                <View style={s.statItem}>
                  <Text style={s.statLabel}>P/L</Text>
                  <Text style={[s.statValue, { color: pnl >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                    {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                  </Text>
                </View>
              </View>
              <Text style={s.statLabel}>Leverage: {pos.leverage}x | Mark: ${pos.mark_price?.toFixed(2)}</Text>
            </View>
          );
        })
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  content: { padding: theme.spacing.md },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  loadingText: { fontSize: 16, color: theme.colors.text.secondary },
  errorText: { fontSize: 16, color: theme.colors.text.secondary, textAlign: 'center' },
  card: {
    backgroundColor: theme.colors.ui.cardBackground, borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg, marginBottom: theme.spacing.md,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8, elevation: 3,
  },
  cardTitle: { fontSize: 18, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.md },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  statItem: { flex: 1 },
  statLabel: { fontSize: 12, color: theme.colors.text.secondary, marginBottom: 4 },
  statValue: { fontSize: 16, fontWeight: '700', color: theme.colors.text.primary, fontFamily: theme.typography.fontFamily.mono },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.md, marginTop: theme.spacing.sm },
  emptyCard: { alignItems: 'center', padding: theme.spacing.xl, backgroundColor: theme.colors.ui.cardBackground, borderRadius: theme.borderRadius.xlarge },
  emptyText: { fontSize: 14, color: theme.colors.text.secondary },
  formRow: { marginBottom: theme.spacing.md },
  formLabel: { fontSize: 13, fontWeight: '600', color: theme.colors.text.primary, marginBottom: 6 },
  input: {
    backgroundColor: theme.colors.ui.background, borderWidth: 1, borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md, padding: theme.spacing.md, fontSize: 16,
    color: theme.colors.text.primary, fontFamily: theme.typography.fontFamily.mono,
  },
  toggleRow: { flexDirection: 'row', gap: theme.spacing.sm },
  toggleBtn: {
    flex: 1, paddingVertical: theme.spacing.md, borderRadius: theme.borderRadius.md,
    borderWidth: 2, borderColor: theme.colors.ui.border, alignItems: 'center',
  },
  toggleText: { fontSize: 15, fontWeight: '700', color: theme.colors.text.secondary },
  toggleTextActive: { color: '#fff' },
  buyActive: { borderColor: theme.colors.market.bullish, backgroundColor: theme.colors.market.bullish },
  sellActive: { borderColor: theme.colors.market.bearish, backgroundColor: theme.colors.market.bearish },
  levBtn: {
    flex: 1, paddingVertical: 10, borderRadius: theme.borderRadius.md,
    borderWidth: 1, borderColor: theme.colors.ui.border, alignItems: 'center',
  },
  levActive: { borderColor: theme.colors.brand.primary, backgroundColor: theme.colors.brand.primary + '20' },
  levText: { fontSize: 14, fontWeight: '600', color: theme.colors.text.secondary },
  levTextActive: { color: theme.colors.brand.primary },
  posHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.sm },
  posSymbol: { fontSize: 18, fontWeight: '700', color: theme.colors.text.primary },
  posBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
});

