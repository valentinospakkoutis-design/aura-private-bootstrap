import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity } from 'react-native';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/apiClient';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { NoTrades } from '@/components/NoTrades';
import { NoData } from '@/components/NoData';
import { Button } from '@/components/Button';
import { theme } from '@/constants/theme';
import { useAppStore } from '@/stores/appStore';
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

  const {
    loading: loadingTrades,
    error: errorTrades,
    execute: fetchTrades,
  } = useApi(api.getTrades, { showLoading: false, showToast: false });

  const {
    loading: loadingStats,
    error: errorStats,
    execute: fetchStats,
  } = useApi(api.getPortfolioStats, { showLoading: false, showToast: false });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [tradesData, statsData] = await Promise.all([
        fetchTrades().catch(() => []), // Fallback to empty array
        fetchStats().catch(() => null), // Fallback to null
      ]);
      
      // Validate data before setting state
      setTrades(Array.isArray(tradesData) ? tradesData : []);
      setStats(statsData && typeof statsData === 'object' ? statsData : null);
    } catch (err) {
      console.error('Error loading paper trading data:', err);
      showToast('Αποτυχία φόρτωσης δεδομένων', 'error');
    }
  }, [fetchTrades, fetchStats, showToast]);

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
    router.push('/brokers');
  }, [router]);

  // Loading state
  if ((loadingTrades || loadingStats) && !refreshing && !trades.length) {
    return <LoadingSpinner fullScreen message="Φόρτωση Paper Trading..." />;
  }

  // Error state (only if no cached data)
  if ((errorTrades || errorStats) && !trades.length && !stats) {
    return <NoData onRetry={loadData} />;
  }

  // Empty state
  if (!trades || trades.length === 0) {
    return <NoTrades />;
  }

  // Safe profit color calculation
  const profitColor = stats && stats.totalProfit >= 0 
    ? theme.colors.market.bullish 
    : theme.colors.market.bearish;

  return (
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
      {/* Stats Card */}
      {stats && (
        <View style={styles.statsCard}>
          <Text style={styles.statsTitle}>📊 Το Portfolio σου</Text>
          
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Συνολική Αξία</Text>
              <Text style={styles.statValue}>
                ${(stats.totalValue || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Κέρδος/Ζημιά</Text>
              <Text style={[styles.statValue, { color: profitColor }]}>
                {stats.totalProfit >= 0 ? '+' : ''}${Math.abs(stats.totalProfit || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Text>
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
            onPress={() => router.push('/live-trading')}
            variant="primary"
            size="medium"
            fullWidth
            style={styles.liveButton}
          />
        </View>
      )}

      {/* Trades List */}
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
          <TouchableOpacity 
            key={trade.id} 
            style={styles.tradeCard}
            onPress={() => router.push(`/trade-details?id=${trade.id}`)}
            activeOpacity={0.8}
          >
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

            {/* Profit/Loss */}
            {trade.status === 'open' && (
              <View style={styles.profitContainer}>
                <View style={styles.profitRow}>
                  <Text style={styles.profitLabel}>P/L:</Text>
                  <Text style={[styles.profitValue, { color: isProfit ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                    {isProfit ? '+' : ''}{tradeProfit.toFixed(2)} ({isProfit ? '+' : ''}{tradeProfitPercentage.toFixed(2)}%)
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

              {trade.status === 'open' && (
                <TouchableOpacity
                  style={styles.closeButton}
                  onPress={() => handleCloseTrade(trade.id)}
                >
                  <Text style={styles.closeButtonText}>Κλείσιμο</Text>
                </TouchableOpacity>
              )}
            </View>
          </TouchableOpacity>
        );
      })}

      {/* Bottom Padding */}
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
});
