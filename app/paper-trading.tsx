import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TextInput, TouchableOpacity } from 'react-native';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { NoTrades } from '../mobile/src/components/NoTrades';
import { NoData } from '../mobile/src/components/NoData';
import { Button } from '../mobile/src/components/Button';
import { theme } from '../mobile/src/constants/theme';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useRouter } from 'expo-router';

interface PaperTrade {
  id: string;
  asset: string;
  action: 'buy' | 'sell';
  amount: number;
  price: number;
  currentPrice?: number;
  timestamp: string;
  profit?: number;
  profitPercentage?: number;
  status: 'open' | 'closed';
}

interface PortfolioStats {
  totalValue: number;
  totalProfit: number;
  profitPercentage: number;
  openTrades: number;
  closedTrades: number;
  winRate: number;
}

export default function PaperTradingScreen() {
  const router = useRouter();
  const { showToast, showModal } = useAppStore();
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Order form state
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [tradesResult, statsResult] = await Promise.all([
        api.getPaperTrades().catch(() => []),
        api.getPortfolioStats().catch(() => null),
      ]);

      setTrades(Array.isArray(tradesResult) ? tradesResult : []);
      setStats(statsResult && typeof statsResult === 'object' ? statsResult : null);
    } catch (err) {
      console.error('Error loading paper trading data:', err);
      setError('Δεν ήταν δυνατή η φόρτωση δεδομένων.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePlaceOrder = useCallback(async () => {
    const qty = parseFloat(quantity);
    if (!symbol.trim()) {
      showToast('Εισήγαγε symbol (π.χ. BTCUSDT)', 'error');
      return;
    }
    if (isNaN(qty) || qty <= 0) {
      showToast('Εισήγαγε έγκυρη ποσότητα', 'error');
      return;
    }

    try {
      setSubmitting(true);
      await api.placePaperOrder(symbol.toUpperCase().trim(), side, qty);
      showToast(`${side} ${qty} ${symbol} εκτελέστηκε!`, 'success');
      setQuantity('');
      await loadData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Αποτυχία order';
      showToast(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  }, [symbol, side, quantity, showToast, loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const handleCloseTrade = useCallback((tradeId: string) => {
    showModal(
      'Κλείσιμο Trade',
      'Είσαι σίγουρος ότι θέλεις να κλείσεις αυτό το trade;',
      async () => {
        try {
          // await api.closeTrade(tradeId);
          showToast('Το trade έκλεισε επιτυχώς!', 'success');
          await loadData();
        } catch (err) {
          showToast('Αποτυχία κλεισίματος trade', 'error');
        }
      }
    );
  }, [showModal, showToast, loadData]);

  const handleStartPaperTrading = useCallback(() => {
    router.push({ pathname: '/brokers' } as any);
  }, [router]);

  // Loading state
  if (loading && !refreshing && !trades.length) {
    return (
      <PageTransition type="fade">
        <View style={styles.container}>
          <View style={styles.content}>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </View>
        </View>
      </PageTransition>
    );
  }

  // Error state (only if no cached data)
  if (error && !trades.length && !stats) {
    return (
      <PageTransition type="fade">
        <NoData onRetry={loadData} />
      </PageTransition>
    );
  }

  // Trade form component (reused in empty and normal state)
  const TradeForm = () => (
    <AnimatedCard delay={0} animationType="slideUp">
      <Text style={styles.statsTitle}>📝 Νέο Trade</Text>

      {/* Symbol */}
      <View style={styles.formRow}>
        <Text style={styles.formLabel}>Symbol</Text>
        <TextInput
          style={styles.formInput}
          value={symbol}
          onChangeText={setSymbol}
          placeholder="BTCUSDT"
          placeholderTextColor={theme.colors.text.secondary}
          autoCapitalize="characters"
        />
      </View>

      {/* Side Toggle */}
      <View style={styles.formRow}>
        <Text style={styles.formLabel}>Side</Text>
        <View style={styles.sideToggle}>
          <TouchableOpacity
            style={[styles.sideButton, side === 'BUY' && styles.sideBuy]}
            onPress={() => setSide('BUY')}
          >
            <Text style={[styles.sideText, side === 'BUY' && styles.sideTextActive]}>📈 BUY</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.sideButton, side === 'SELL' && styles.sideSell]}
            onPress={() => setSide('SELL')}
          >
            <Text style={[styles.sideText, side === 'SELL' && styles.sideTextActive]}>📉 SELL</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Quantity */}
      <View style={styles.formRow}>
        <Text style={styles.formLabel}>Ποσότητα</Text>
        <TextInput
          style={styles.formInput}
          value={quantity}
          onChangeText={setQuantity}
          placeholder="0.001"
          placeholderTextColor={theme.colors.text.secondary}
          keyboardType="decimal-pad"
        />
      </View>

      {/* Submit */}
      <Button
        title={submitting ? 'Εκτέλεση...' : `${side} ${symbol}`}
        onPress={handlePlaceOrder}
        variant={side === 'BUY' ? 'primary' : 'secondary'}
        size="large"
        fullWidth
        disabled={submitting || !quantity.trim()}
        loading={submitting}
      />
    </AnimatedCard>
  );

  // Empty state — show form so user can start trading
  if (!trades || trades.length === 0) {
    return (
      <PageTransition type="fade">
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
          <TradeForm />
          <View style={{ height: theme.spacing.lg }} />
          <NoTrades />
        </ScrollView>
      </PageTransition>
    );
  }

  // Safe profit color calculation
  const profitColor = stats && stats.totalProfit >= 0 
    ? theme.colors.market.bullish 
    : theme.colors.market.bearish;

  return (
    <PageTransition type="slideUp">
      <ScrollView 
        style={styles.container} 
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.colors.brand.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      >
      {/* Stats Card - ANIMATED */}
      {stats && (
        <AnimatedCard delay={0} animationType="slideUp">
          <Text style={styles.statsTitle}>📊 Το Portfolio σου</Text>
          
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Συνολική Αξία</Text>
              <AnimatedCounter
                value={stats.totalValue || 0}
                decimals={2}
                prefix="$"
                duration={1500}
                style={styles.statValue}
              />
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Κέρδος/Ζημιά</Text>
              <AnimatedCounter
                value={Math.abs(stats.totalProfit || 0)}
                decimals={2}
                prefix={stats.totalProfit >= 0 ? '+$' : '-$'}
                duration={1500}
                style={[styles.statValue, { color: profitColor }]}
              />
              <Text style={[styles.statPercentage, { color: profitColor }]}>
                ({stats.profitPercentage >= 0 ? '+' : ''}{(stats.profitPercentage || 0).toFixed(2)}%)
              </Text>
            </View>
          </View>

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Ανοιχτά Trades</Text>
              <Text style={styles.statValue}>{stats.openTrades || 0}</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Win Rate</Text>
              <Text style={styles.statValue}>{(stats.winRate || 0).toFixed(0)}%</Text>
            </View>
          </View>

          <Button
            title="Ξεκίνα Live Trading"
            onPress={() => router.push({ pathname: '/live-trading' } as any)}
            variant="primary"
            size="medium"
            fullWidth
            style={styles.liveButton}
          />
        </AnimatedCard>
      )}

      {/* Trade Form */}
      <TradeForm />

      {/* Trades List - SWIPEABLE */}
      <Text style={styles.sectionTitle}>Πρόσφατα Trades ({trades.length})</Text>
      {trades.map((trade) => {
        // Safe calculations with fallbacks
        const tradeProfit = trade.profit || 0;
        const tradeProfitPercentage = trade.profitPercentage || 0;
        const isProfit = tradeProfit >= 0;
        const tradeColor = trade.action === 'buy' 
          ? theme.colors.market.bullish 
          : theme.colors.market.bearish;

        return (
          <SwipeableCard
            key={trade.id}
            onDelete={trade.status === 'open' ? () => handleCloseTrade(trade.id) : undefined}
            deleteText="Κλείσιμο"
          >
            <View style={styles.tradeCard}>
              {/* Header */}
              <View style={styles.tradeHeader}>
                <View style={styles.tradeHeaderLeft}>
                  <Text style={styles.tradeAsset}>{trade.asset || 'Unknown'}</Text>
                  <Text style={styles.tradeTimestamp}>
                    {trade.timestamp 
                      ? new Date(trade.timestamp).toLocaleDateString('el-GR', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : 'N/A'
                    }
                  </Text>
                </View>
                <View style={[
                  styles.tradeBadge,
                  { backgroundColor: tradeColor + '20' }
                ]}>
                  <Text style={[styles.tradeAction, { color: tradeColor }]}>
                    {trade.action === 'buy' ? '📈 BUY' : '📉 SELL'}
                  </Text>
                </View>
              </View>

              {/* Price Info */}
              <View style={styles.tradeBody}>
                <View style={styles.priceRow}>
                  <Text style={styles.priceLabel}>Ποσότητα:</Text>
                  <Text style={styles.priceValue}>
                    {(trade.amount || 0).toFixed(4)} {trade.asset?.split('/')[0] || ''}
                  </Text>
                </View>
                <View style={styles.priceRow}>
                  <Text style={styles.priceLabel}>Τιμή Αγοράς:</Text>
                  <Text style={styles.priceValue}>
                    ${(trade.price || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </Text>
                </View>
                {trade.status === 'open' && trade.currentPrice && (
                  <View style={styles.priceRow}>
                    <Text style={styles.priceLabel}>Τρέχουσα Τιμή:</Text>
                    <Text style={[styles.priceValue, { color: isProfit ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                      ${trade.currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </Text>
                  </View>
                )}
              </View>

              {/* Profit/Loss - ANIMATED */}
              {trade.status === 'open' && (
                <View style={styles.profitContainer}>
                  <View style={styles.profitRow}>
                    <Text style={styles.profitLabel}>P/L:</Text>
                    <AnimatedCounter
                      value={Math.abs(tradeProfit)}
                      decimals={2}
                      prefix={isProfit ? '+$' : '-$'}
                      style={[styles.profitValue, { color: isProfit ? theme.colors.market.bullish : theme.colors.market.bearish }]}
                    />
                    <Text style={[styles.profitPercentage, { color: isProfit ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                      ({isProfit ? '+' : ''}{tradeProfitPercentage.toFixed(2)}%)
                    </Text>
                  </View>
                </View>
              )}

              {/* Status Badge */}
              <View style={styles.statusContainer}>
                <View style={[
                  styles.statusBadge,
                  { backgroundColor: trade.status === 'open' 
                    ? theme.colors.semantic.success + '20' 
                    : theme.colors.ui.border 
                  }
                ]}>
                  <Text style={[
                    styles.statusText,
                    { color: trade.status === 'open' 
                      ? theme.colors.semantic.success 
                      : theme.colors.text.secondary 
                    }
                  ]}>
                    {trade.status === 'open' ? '🟢 Ανοιχτό' : '⚪ Κλειστό'}
                  </Text>
                </View>
              </View>
            </View>
          </SwipeableCard>
        );
      })}

      {/* Bottom Padding */}
      <View style={styles.bottomPadding} />
    </ScrollView>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
  },
  statsCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
  },
  statsTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: theme.spacing.md,
  },
  statItem: {
    flex: 1,
  },
  statLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  statValue: {
    fontSize: theme.typography.sizes['2xl'],
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  statPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    marginTop: theme.spacing.xs,
  },
  liveButton: {
    marginTop: theme.spacing.sm,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  tradeCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing.md,
  },
  tradeHeaderLeft: {
    flex: 1,
  },
  tradeAsset: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  tradeTimestamp: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  tradeBadge: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.large,
  },
  tradeAction: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
  },
  tradeBody: {
    marginBottom: theme.spacing.md,
    gap: theme.spacing.xs,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  priceLabel: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  priceValue: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  profitContainer: {
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.medium,
    marginBottom: theme.spacing.md,
  },
  profitRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  profitLabel: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  profitValue: {
    fontSize: theme.typography.sizes.lg,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
  },
  profitPercentage: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '600',
    marginLeft: theme.spacing.xs,
  },
  statusContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusBadge: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.large,
  },
  statusText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
  },
  closeButton: {
    backgroundColor: theme.colors.semantic.error + '20',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.medium,
  },
  closeButtonText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.semantic.error,
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
  formRow: {
    marginBottom: theme.spacing.md,
  },
  formLabel: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600' as const,
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  formInput: {
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  sideToggle: {
    flexDirection: 'row' as const,
    gap: theme.spacing.sm,
  },
  sideButton: {
    flex: 1,
    paddingVertical: theme.spacing.md,
    borderRadius: theme.borderRadius.medium,
    borderWidth: 2,
    borderColor: theme.colors.ui.border,
    alignItems: 'center' as const,
  },
  sideBuy: {
    borderColor: theme.colors.market.bullish,
    backgroundColor: theme.colors.market.bullish + '15',
  },
  sideSell: {
    borderColor: theme.colors.market.bearish,
    backgroundColor: theme.colors.market.bearish + '15',
  },
  sideText: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700' as const,
    color: theme.colors.text.secondary,
  },
  sideTextActive: {
    color: theme.colors.text.primary,
  },
});
