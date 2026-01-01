import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/apiClient';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { NoTrades } from '@/components/NoTrades';
import { Button } from '@/components/Button';
import { theme } from '@/constants/theme';
import { useAppStore } from '@/stores/appStore';

interface PaperTrade {
  id: string;
  asset: string;
  action: 'buy' | 'sell';
  amount: number;
  price: number;
  timestamp: string;
  profit?: number;
  status: 'open' | 'closed';
}

interface PortfolioStats {
  totalValue: number;
  totalProfit: number;
  profitPercentage: number;
  openTrades: number;
  closedTrades: number;
}

export default function PaperTradingScreen() {
  const { showToast } = useAppStore();
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [stats, setStats] = useState<PortfolioStats | null>(null);

  const {
    loading: loadingTrades,
    execute: fetchTrades,
  } = useApi(api.getTrades, { showLoading: false });

  const {
    loading: loadingStats,
    execute: fetchStats,
  } = useApi(api.getPortfolioStats, { showLoading: false });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [tradesData, statsData] = await Promise.all([
        fetchTrades(),
        fetchStats(),
      ]);
      setTrades(tradesData);
      setStats(statsData);
    } catch (err) {
      // Handled by useApi
    }
  };

  const handleStartPaperTrading = () => {
    showToast('Paper Trading ξεκίνησε!', 'success');
    // Navigate to setup or start trading
  };

  if (loadingTrades || loadingStats) {
    return <LoadingSpinner fullScreen message="Φόρτωση Paper Trading..." />;
  }

  if (!trades || trades.length === 0) {
    return <NoTrades />;
  }

  const profitColor = stats && stats.totalProfit >= 0 
    ? theme.colors.market.bullish 
    : theme.colors.market.bearish;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Stats Card */}
      {stats && (
        <View style={styles.statsCard}>
          <Text style={styles.statsTitle}>📊 Το Portfolio σου</Text>
          
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Συνολική Αξία</Text>
              <Text style={styles.statValue}>${stats.totalValue.toLocaleString()}</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Κέρδος/Ζημιά</Text>
              <Text style={[styles.statValue, { color: profitColor }]}>
                {stats.totalProfit >= 0 ? '+' : ''}${stats.totalProfit.toLocaleString()}
              </Text>
              <Text style={[styles.statPercentage, { color: profitColor }]}>
                ({stats.profitPercentage >= 0 ? '+' : ''}{stats.profitPercentage.toFixed(2)}%)
              </Text>
            </View>
          </View>

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Ανοιχτά Trades</Text>
              <Text style={styles.statValue}>{stats.openTrades}</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Κλειστά Trades</Text>
              <Text style={styles.statValue}>{stats.closedTrades}</Text>
            </View>
          </View>
        </View>
      )}

      {/* Trades List */}
      <Text style={styles.sectionTitle}>Πρόσφατα Trades</Text>
      {trades.map((trade) => (
        <View key={trade.id} style={styles.tradeCard}>
          <View style={styles.tradeHeader}>
            <Text style={styles.tradeAsset}>{trade.asset}</Text>
            <View style={[
              styles.tradeBadge,
              { backgroundColor: trade.action === 'buy' 
                ? theme.colors.market.bullish + '20' 
                : theme.colors.market.bearish + '20' 
              }
            ]}>
              <Text style={[
                styles.tradeAction,
                { color: trade.action === 'buy' 
                  ? theme.colors.market.bullish 
                  : theme.colors.market.bearish 
                }
              ]}>
                {trade.action === 'buy' ? 'ΑΓΟΡΑ' : 'ΠΩΛΗΣΗ'}
              </Text>
            </View>
          </View>

          <View style={styles.tradeDetails}>
            <View style={styles.tradeDetailRow}>
              <Text style={styles.tradeDetailLabel}>Ποσότητα:</Text>
              <Text style={styles.tradeDetailValue}>{trade.amount}</Text>
            </View>
            <View style={styles.tradeDetailRow}>
              <Text style={styles.tradeDetailLabel}>Τιμή:</Text>
              <Text style={styles.tradeDetailValue}>${trade.price.toLocaleString()}</Text>
            </View>
            {trade.profit !== undefined && (
              <View style={styles.tradeDetailRow}>
                <Text style={styles.tradeDetailLabel}>Κέρδος/Ζημιά:</Text>
                <Text style={[
                  styles.tradeDetailValue,
                  { color: trade.profit >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }
                ]}>
                  {trade.profit >= 0 ? '+' : ''}${trade.profit.toLocaleString()}
                </Text>
              </View>
            )}
          </View>

          <View style={styles.tradeFooter}>
            <Text style={styles.tradeTimestamp}>
              {new Date(trade.timestamp).toLocaleString('el-GR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </Text>
            <View style={[
              styles.statusBadge,
              { backgroundColor: trade.status === 'open' 
                ? theme.colors.semantic.success + '20' 
                : theme.colors.text.secondary + '20' 
              }
            ]}>
              <Text style={[
                styles.statusText,
                { color: trade.status === 'open' 
                  ? theme.colors.semantic.success 
                  : theme.colors.text.secondary 
                }
              ]}>
                {trade.status === 'open' ? 'Ανοιχτό' : 'Κλειστό'}
              </Text>
            </View>
          </View>
        </View>
      ))}

      {/* Start Trading Button */}
      <Button
        title="Ξεκίνα Paper Trading"
        onPress={handleStartPaperTrading}
        variant="primary"
        fullWidth
        style={styles.startButton}
      />
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
    gap: theme.spacing.md,
  },
  statsCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  statsTitle: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.lg,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: theme.spacing.md,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  statValue: {
    fontSize: theme.typography.sizes['2xl'],
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  statPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    marginTop: theme.spacing.xs,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
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
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  tradeAsset: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  tradeBadge: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
  },
  tradeAction: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
  },
  tradeDetails: {
    marginBottom: theme.spacing.md,
    gap: theme.spacing.xs,
  },
  tradeDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tradeDetailLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  tradeDetailValue: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  tradeFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: theme.spacing.md,
    borderTopWidth: 1,
    borderTopColor: theme.colors.ui.border,
  },
  tradeTimestamp: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  statusBadge: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.small,
  },
  statusText: {
    fontSize: theme.typography.sizes.xs,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
  },
  startButton: {
    marginTop: theme.spacing.lg,
    marginBottom: theme.spacing.xl,
  },
});

