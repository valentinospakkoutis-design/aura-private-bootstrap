import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TextInput, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { Button } from '../mobile/src/components/Button';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { NoTrades } from '../mobile/src/components/NoTrades';
import { theme } from '../mobile/src/constants/theme';
import { NumberFormatter } from '../mobile/src/utils/NumberFormatter';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';
import { Alert } from 'react-native';

interface LiveTrade {
  id: string;
  asset: string;
  action: 'buy' | 'sell';
  entryPrice: number;
  currentPrice: number;
  amount: number;
  profit: number;
  profitPercentage: number;
  timestamp: string;
  status: 'open' | 'closed';
  stopLoss?: number;
  takeProfit?: number;
}

interface LiveStats {
  totalValue: number;
  totalProfit: number;
  profitPercentage: number;
  openTrades: number;
  closedTrades: number;
  winRate: number;
  totalInvested: number;
}

export default function LiveTradingScreen() {
  const router = useRouter();
  const { user, brokers, setBrokers, showToast, showModal } = useAppStore();
  const [trades, setTrades] = useState<LiveTrade[]>([]);
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [tradingMode, setTradingMode] = useState<string>('paper');
  const [livePortfolio, setLivePortfolio] = useState<any>(null);
  const [brokerConnected, setBrokerConnected] = useState(false);
  const [liveHistory, setLiveHistory] = useState<any[]>([]);

  // Order form state
  const [symbol, setSymbol] = useState('BTCUSDC');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState('0.0001');
  const [submitting, setSubmitting] = useState(false);

  const {
    loading: closingTrade,
    execute: closeTrade,
  } = useApi((tradeId: string) => {
    return Promise.resolve({ success: true });
  }, { showLoading: false, showToast: false });

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [tradesData, brokersData, portfolioData, historyData] = await Promise.all([
        api.getLiveTrades(false).catch(() => []),
        api.getBrokers(false).catch(() => null),
        api.getLivePortfolioFull().catch(() => null),
        api.getLiveTradeHistory().catch(() => ({ trades: [] })),
      ]);

      setLiveHistory(historyData?.trades || []);

      if (Array.isArray(tradesData)) {
        setTrades(tradesData);
      }
      if (portfolioData && portfolioData.total_value !== undefined) {
        setLivePortfolio(portfolioData);
        setStats({
          totalValue: portfolioData.total_value || 0,
          totalProfit: 0,
          profitPercentage: 0,
          openTrades: (portfolioData.positions || []).filter((p: any) => p.symbol !== 'USDC' && p.symbol !== 'USDT').length,
          closedTrades: 0,
          winRate: 0,
          totalInvested: portfolioData.total_value || 0,
        });
      }

      // Check broker connection
      if (brokersData) {
        const brokerList = brokersData?.brokers ?? (Array.isArray(brokersData) ? brokersData : []);
        const mapped = brokerList.map((b: any) => ({
          id: b.broker || b.id,
          name: (b.broker || b.id || '').charAt(0).toUpperCase() + (b.broker || b.id || '').slice(1),
          connected: b.connected ?? false,
        }));
        setBrokers(mapped);
        setBrokerConnected(mapped.some((b: any) => b.connected));
      }
    } catch (err) {
      console.error('Failed to load live trading data:', err);
    } finally {
      setInitialLoading(false);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const handlePlaceOrder = useCallback(async () => {
    const qty = parseFloat(quantity);
    if (!symbol.trim()) { showToast('Εισήγαγε symbol', 'error'); return; }
    if (isNaN(qty) || qty <= 0) { showToast('Εισήγαγε έγκυρη ποσότητα', 'error'); return; }

    try {
      setSubmitting(true);
      await api.placeLiveOrder(symbol.toUpperCase().trim(), side, qty);
      showToast(`${side} ${qty} ${symbol} εκτελέστηκε!`, 'success');
      setQuantity('0.0001');
      await loadData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Αποτυχία order';
      showToast(typeof msg === 'string' ? msg : JSON.stringify(msg), 'error');
    } finally {
      setSubmitting(false);
    }
  }, [symbol, side, quantity, showToast, loadData]);

  const handleClosePosition = useCallback((assetSymbol: string, amount: number, valueUsdc: number) => {
    const tradingSymbol = `${assetSymbol}USDC`;
    Alert.alert(
      `Κλείσιμο θέσης ${assetSymbol}`,
      `Θα πουλήσεις ${amount < 1 ? amount.toFixed(6) : amount.toFixed(4)} ${assetSymbol} (~$${valueUsdc.toFixed(2)}) στην τρέχουσα τιμή.`,
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Πούλα',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.closeLivePosition(tradingSymbol, amount);
              showToast(`Sold ${amount} ${assetSymbol}`, 'success');
              await loadData();
            } catch (err: any) {
              const msg = err?.response?.data?.detail || err?.message || 'Close failed';
              showToast(typeof msg === 'string' ? msg : JSON.stringify(msg), 'error');
            }
          },
        },
      ]
    );
  }, [showToast, loadData]);

  const handleCloseTrade = useCallback((tradeId: string) => {
    showModal(
      '⚠️ Κλείσιμο Live Trade',
      'Είσαι σίγουρος ότι θέλεις να κλείσεις αυτό το πραγματικό trade; Αυτή η ενέργεια δεν μπορεί να αναιρεθεί.',
      async () => {
        try {
          await closeTrade(tradeId);
          showToast('Το trade έκλεισε επιτυχώς!', 'success');
          await loadData();
        } catch (err) {
          showToast('Αποτυχία κλεισίματος trade', 'error');
        }
      }
    );
  }, [closeTrade, showModal, showToast, loadData]);

  const handleSwitchToPaper = useCallback(() => {
    Alert.alert(
      'Επιστροφή σε Paper Trading',
      'Θέλεις να επιστρέψεις σε Paper Trading mode;',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Επιστροφή',
          onPress: () => {
            router.push({ pathname: '/paper-trading' } as any);
          },
        },
      ]
    );
  }, [router]);

  // Loading state — wait for initial data load
  if (initialLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.content}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </View>
      </View>
    );
  }

  // No broker connected — show connection prompt
  if (!brokerConnected) {
    return (
      <View style={styles.container}>
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>🔌</Text>
          <Text style={styles.emptyTitle}>Δεν Έχεις Συνδεδεμένο Broker</Text>
          <Text style={styles.emptyDescription}>
            Για να κάνεις live trading, πρέπει πρώτα να συνδέσεις ένα broker.
          </Text>
          <Button
            title="Σύνδεση Broker"
            onPress={() => router.push({ pathname: '/brokers' } as any)}
            variant="primary"
            size="large"
            fullWidth
          />
        </View>
      </View>
    );
  }

  const profitColor = (stats?.totalProfit || 0) >= 0 
    ? theme.colors.market.bullish 
    : theme.colors.market.bearish;

  return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.colors.brand.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Warning Banner */}
        <AnimatedCard delay={0} animationType="slideUp" style={styles.warningBanner}>
          <View style={styles.warningHeader}>
            <Text style={styles.warningIcon}>⚠️</Text>
            <Text style={styles.warningTitle}>Live Trading Mode</Text>
          </View>
          <Text style={styles.warningText}>
            Βρίσκεσαι σε LIVE mode. Όλα τα trades γίνονται με πραγματικά χρήματα.
          </Text>
          <Button
            title="Επιστροφή σε Paper Trading"
            onPress={handleSwitchToPaper}
            variant="secondary"
            size="small"
            fullWidth
          />
        </AnimatedCard>

        {/* Stats Card */}
        {stats && (
          <AnimatedCard delay={100} animationType="slideUp">
            <Text style={styles.statsTitle}>💰 Live Portfolio</Text>
            
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

            <View style={styles.statsGrid}>
              <View style={styles.gridItem}>
                <Text style={styles.gridValue}>{stats.openTrades || 0}</Text>
                <Text style={styles.gridLabel}>Ανοιχτά</Text>
              </View>
              <View style={styles.gridItem}>
                <Text style={styles.gridValue}>{stats.closedTrades || 0}</Text>
                <Text style={styles.gridLabel}>Κλειστά</Text>
              </View>
              <View style={styles.gridItem}>
                <Text style={styles.gridValue}>{(stats.winRate || 0).toFixed(0)}%</Text>
                <Text style={styles.gridLabel}>Win Rate</Text>
              </View>
              <View style={styles.gridItem}>
                <Text style={styles.gridValue}>
                  {NumberFormatter.toCompact(stats.totalInvested || 0)}
                </Text>
                <Text style={styles.gridLabel}>Επένδυση</Text>
              </View>
            </View>

          </AnimatedCard>
        )}

        {/* Live Positions */}
        {livePortfolio && livePortfolio.positions && livePortfolio.positions.length > 0 && (() => {
          // Compute avg buy price per asset from trade history
          const avgPrices: Record<string, number> = {};
          for (const t of liveHistory) {
            if (t.side === 'BUY' && t.price > 0) {
              const base = t.symbol?.replace('USDC', '').replace('USDT', '') || '';
              if (!avgPrices[base] || t.price > 0) avgPrices[base] = t.price;
            }
          }

          return (
            <View style={styles.orderCard}>
              <Text style={styles.statsTitle}>💼 Assets ({livePortfolio.positions.length})</Text>
              {livePortfolio.positions.map((pos: any, i: number) => {
                const isStable = ['USDC', 'USDT', 'BUSD', 'USD'].includes(pos.symbol);
                const avgBuy = avgPrices[pos.symbol] || 0;
                const currentPricePerUnit = pos.amount > 0 ? pos.value_usdc / pos.amount : 0;
                const pnl = avgBuy > 0 ? (currentPricePerUnit - avgBuy) * pos.amount : 0;
                const pnlColor = pnl >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish;

                return (
                  <View key={pos.symbol || i} style={styles.positionRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.positionSymbol}>{pos.symbol}</Text>
                      <Text style={styles.positionAmount}>
                        {pos.amount < 1 ? pos.amount.toFixed(6) : pos.amount.toFixed(4)}
                      </Text>
                      {!isStable && avgBuy > 0 && (
                        <Text style={[styles.positionAmount, { color: pnlColor }]}>
                          P/L: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                        </Text>
                      )}
                    </View>
                    <View style={{ alignItems: 'flex-end' as const, gap: 4 }}>
                      <Text style={styles.positionValue}>
                        ${pos.value_usdc.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </Text>
                      {!isStable && (
                        <TouchableOpacity
                          style={styles.closeBtn}
                          onPress={() => handleClosePosition(pos.symbol, pos.amount, pos.value_usdc)}
                        >
                          <Text style={styles.closeBtnText}>CLOSE</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                );
              })}
            </View>
          );
        })()}

        {/* Order Form */}
        <View style={styles.orderCard}>
          <Text style={styles.statsTitle}>📝 Νέο Live Order</Text>

          <View style={styles.formRow}>
            <Text style={styles.formLabel}>Symbol</Text>
            <TextInput
              style={styles.formInput}
              value={symbol}
              onChangeText={setSymbol}
              placeholder="BTCUSDC"
              placeholderTextColor="#999"
              autoCapitalize="characters"
              autoCorrect={false}
              editable={true}
              blurOnSubmit={false}
            />
          </View>

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

          <View style={styles.formRow}>
            <Text style={styles.formLabel}>Ποσότητα</Text>
            <TextInput
              style={styles.formInput}
              value={quantity}
              onChangeText={setQuantity}
              placeholder="0.0001"
              placeholderTextColor="#999"
              keyboardType="decimal-pad"
              returnKeyType="done"
              autoCorrect={false}
              editable={true}
              blurOnSubmit={false}
            />
          </View>

          <Button
            title={submitting ? 'Εκτέλεση...' : `${side} ${symbol}`}
            onPress={handlePlaceOrder}
            variant={side === 'BUY' ? 'primary' : 'secondary'}
            size="large"
            fullWidth
            disabled={submitting || !quantity.trim()}
            loading={submitting}
          />
        </View>

        {/* Live Trade History */}
        {liveHistory.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Trade History ({liveHistory.length})</Text>
            {liveHistory.map((trade: any, index: number) => {
              const isBuy = trade.side === 'BUY';
              const sideColor = isBuy ? theme.colors.market.bullish : theme.colors.market.bearish;
              return (
                <View key={trade.id || index} style={styles.historyCard}>
                  <View style={styles.historyHeader}>
                    <View>
                      <Text style={styles.historySymbol}>{trade.symbol}</Text>
                      <Text style={styles.historyTime}>
                        {trade.timestamp ? new Date(trade.timestamp).toLocaleString('el-GR', {
                          day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                        }) : ''}
                      </Text>
                    </View>
                    <View style={[styles.historyBadge, { backgroundColor: sideColor + '20' }]}>
                      <Text style={[styles.historyBadgeText, { color: sideColor }]}>
                        {isBuy ? '📈' : '📉'} {trade.side}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.historyBody}>
                    <View style={styles.historyRow}>
                      <Text style={styles.historyLabel}>Quantity</Text>
                      <Text style={styles.historyValue}>{trade.quantity}</Text>
                    </View>
                    {trade.price > 0 && (
                      <View style={styles.historyRow}>
                        <Text style={styles.historyLabel}>Price</Text>
                        <Text style={styles.historyValue}>
                          ${trade.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </Text>
                      </View>
                    )}
                  </View>
                </View>
              );
            })}
          </>
        )}

        {/* Open Positions */}
        {trades.length === 0 ? (
          <NoTrades />
        ) : (
          <>
            <Text style={styles.sectionTitle}>
              Ενεργά Trades ({trades.filter(t => t.status === 'open').length})
            </Text>
            {trades
              .filter(trade => trade.status === 'open')
              .map((trade, index) => {
            const tradeProfit = trade.profit || 0;
            const tradeProfitPercentage = trade.profitPercentage || 0;
            const isProfit = tradeProfit >= 0;
            const tradeColor = trade.action === 'buy' 
              ? theme.colors.market.bullish 
              : theme.colors.market.bearish;

            return (
              <SwipeableCard
                key={trade.id}
                onDelete={() => handleCloseTrade(trade.id)}
                deleteText="Κλείσιμο"
              >
                <View style={styles.tradeCard}>
                  {/* Header */}
                  <View style={styles.tradeHeader}>
                    <View style={styles.tradeInfo}>
                      <Text style={styles.tradeAsset}>{trade.asset}</Text>
                      <Text style={styles.tradeTimestamp}>
                        {DateFormatter.toRelativeTime(trade.timestamp)}
                      </Text>
                    </View>
                    <View style={[styles.tradeBadge, { backgroundColor: tradeColor + '20' }]}>
                      <Text style={[styles.tradeAction, { color: tradeColor }]}>
                        {trade.action.toUpperCase()}
                      </Text>
                    </View>
                  </View>

                  {/* Body */}
                  <View style={styles.tradeBody}>
                    <View style={styles.priceRow}>
                      <Text style={styles.priceLabel}>Entry:</Text>
                      <Text style={styles.priceValue}>
                        {NumberFormatter.toCurrency(trade.entryPrice)}
                      </Text>
                    </View>
                    <View style={styles.priceRow}>
                      <Text style={styles.priceLabel}>Current:</Text>
                      <Text style={styles.priceValue}>
                        {NumberFormatter.toCurrency(trade.currentPrice)}
                      </Text>
                    </View>
                    <View style={styles.priceRow}>
                      <Text style={styles.priceLabel}>Amount:</Text>
                      <Text style={styles.priceValue}>{trade.amount}</Text>
                    </View>
                  </View>

                  {/* Profit/Loss */}
                  <View style={styles.profitContainer}>
                    <View style={styles.profitRow}>
                      <Text style={styles.profitLabel}>P/L:</Text>
                      <View style={styles.profitValues}>
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
                    <AnimatedProgressBar
                      progress={Math.min(Math.abs(tradeProfitPercentage) / 100, 1)}
                      color={isProfit ? theme.colors.market.bullish : theme.colors.market.bearish}
                      height={6}
                      animated
                    />
                  </View>

                  {/* Stop Loss / Take Profit */}
                  {(trade.stopLoss || trade.takeProfit) && (
                    <View style={styles.limitsContainer}>
                      {trade.stopLoss && (
                        <View style={styles.limitItem}>
                          <Text style={styles.limitLabel}>Stop Loss:</Text>
                          <Text style={[styles.limitValue, { color: theme.colors.semantic.error }]}>
                            {NumberFormatter.toCurrency(trade.stopLoss)}
                          </Text>
                        </View>
                      )}
                      {trade.takeProfit && (
                        <View style={styles.limitItem}>
                          <Text style={styles.limitLabel}>Take Profit:</Text>
                          <Text style={[styles.limitValue, { color: theme.colors.semantic.success }]}>
                            {NumberFormatter.toCurrency(trade.takeProfit)}
                          </Text>
                        </View>
                      )}
                    </View>
                  )}
                </View>
              </SwipeableCard>
            );
          })}
          </>
        )}

        <View style={styles.bottomPadding} />
      </ScrollView>
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
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.xl,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: theme.spacing.lg,
  },
  emptyTitle: {
    fontSize: theme.typography.sizes['2xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
    textAlign: 'center',
  },
  emptyDescription: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    textAlign: 'center',
    marginBottom: theme.spacing.xl,
    lineHeight: 24,
  },
  warningBanner: {
    backgroundColor: theme.colors.semantic.warning + '15',
    borderWidth: 2,
    borderColor: theme.colors.semantic.warning,
  },
  warningHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  warningIcon: {
    fontSize: 24,
    marginRight: theme.spacing.sm,
  },
  warningTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.semantic.warning,
  },
  warningText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
    marginBottom: theme.spacing.md,
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
    marginBottom: theme.spacing.lg,
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
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.large,
  },
  gridItem: {
    alignItems: 'center',
  },
  gridValue: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  gridLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginTop: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  tradeCard: {
    gap: theme.spacing.md,
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tradeInfo: {
    flex: 1,
  },
  tradeAsset: {
    fontSize: theme.typography.sizes.lg,
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
    gap: theme.spacing.sm,
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
  profitValues: {
    alignItems: 'flex-end',
  },
  profitValue: {
    fontSize: theme.typography.sizes.lg,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
  },
  profitPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    marginTop: theme.spacing.xs,
  },
  limitsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: theme.spacing.sm,
  },
  limitItem: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.sm,
    borderRadius: theme.borderRadius.small,
  },
  limitLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  limitValue: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '600',
  },
  progressContainer: {
    marginTop: theme.spacing.sm,
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
  orderCard: {
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
  positionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  positionSymbol: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  positionAmount: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  positionValue: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  historyCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  historySymbol: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  historyTime: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginTop: 2,
  },
  historyBadge: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
  },
  historyBadgeText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
  },
  historyBody: {
    gap: theme.spacing.xs,
  },
  historyRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  historyLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  historyValue: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  closeBtn: {
    backgroundColor: theme.colors.semantic.error + '20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  closeBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: theme.colors.semantic.error,
  },
});

