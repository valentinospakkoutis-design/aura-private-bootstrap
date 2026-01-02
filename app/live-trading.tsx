import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { Button } from '../mobile/src/components/Button';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { NoTrades } from '../mobile/src/components/NoTrades';
import { NoData } from '../mobile/src/components/NoData';
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
  const { user, brokers, showToast, showModal } = useAppStore();
  const [trades, setTrades] = useState<LiveTrade[]>([]);
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const {
    loading: loadingTrades,
    error: tradesError,
    execute: fetchTrades,
  } = useApi(() => api.getTrades(50), { showLoading: false, showToast: false });

  const {
    loading: loadingStats,
    execute: fetchStats,
  } = useApi(() => api.getPortfolioStats(), { showLoading: false, showToast: false });

  const {
    loading: closingTrade,
    execute: closeTrade,
  } = useApi((tradeId: string) => {
    // Placeholder - implement actual API call
    return Promise.resolve({ success: true });
  }, { showLoading: false, showToast: false });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [tradesData, statsData] = await Promise.all([
        fetchTrades().catch(() => []),
        fetchStats().catch(() => null),
      ]);

      if (Array.isArray(tradesData)) {
        setTrades(tradesData);
      }
      if (statsData && typeof statsData === 'object') {
        setStats(statsData as LiveStats);
      }
    } catch (err) {
      console.error('Failed to load live trading data:', err);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

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
            router.push('/paper-trading');
          },
        },
      ]
    );
  }, [router]);

  // Check if user has connected brokers
  const hasConnectedBrokers = brokers && brokers.some((b) => b.connected);

  if (!hasConnectedBrokers) {
    return (
      <PageTransition type="fade">
        <View style={styles.container}>
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>🔌</Text>
            <Text style={styles.emptyTitle}>Δεν Έχεις Συνδεδεμένο Broker</Text>
            <Text style={styles.emptyDescription}>
              Για να κάνεις live trading, πρέπει πρώτα να συνδέσεις ένα broker.
            </Text>
            <AnimatedButton
              title="Σύνδεση Broker"
              onPress={() => router.push('/brokers')}
              variant="primary"
              size="large"
              fullWidth
            />
          </View>
        </View>
      </PageTransition>
    );
  }

  if ((loadingTrades || loadingStats) && !refreshing && !trades.length) {
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

  if (tradesError && !trades.length) {
    return (
      <PageTransition type="fade">
        <NoData onRetry={loadData} />
      </PageTransition>
    );
  }

  if (!trades || trades.length === 0) {
    return (
      <PageTransition type="fade">
        <NoTrades />
      </PageTransition>
    );
  }

  const profitColor = (stats?.totalProfit || 0) >= 0 
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

        {/* Trades List */}
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: theme.spacing.md,
    gap: theme.spacing.md,
  },
  gridItem: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    alignItems: 'center',
  },
  gridValue: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  gridLabel: {
    fontSize: theme.typography.sizes.sm,
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
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing.md,
  },
  tradeInfo: {
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
    marginBottom: theme.spacing.sm,
  },
  profitLabel: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  profitValues: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.xs,
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
  },
  limitsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: theme.spacing.md,
    gap: theme.spacing.md,
  },
  limitItem: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.sm,
    borderRadius: theme.borderRadius.medium,
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
});

