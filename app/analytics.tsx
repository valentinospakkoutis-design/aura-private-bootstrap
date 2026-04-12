import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { NumberFormatter } from '../mobile/src/utils/NumberFormatter';

interface AnalyticsData {
  totalValue: number;
  totalProfit: number;
  profitPercentage: number;
  totalTrades: number;
  winRate: number;
  averageProfit: number;
  bestTrade: {
    asset: string;
    profit: number;
    percentage: number;
  };
  worstTrade: {
    asset: string;
    loss: number;
    percentage: number;
  };
  assetAllocation: {
    asset: string;
    percentage: number;
    value: number;
  }[];
  performanceHistory: {
    date: string;
    value: number;
  }[];
  hasData?: boolean;
}

export default function AnalyticsScreen() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const {
    loading,
    error,
    execute: fetchAnalytics,
  } = useApi(() => api.getAnalyticsSummary(timeRange), { showLoading: false, showToast: false });

  useEffect(() => {
    loadAnalytics();
  }, [timeRange]);

  const loadAnalytics = async () => {
    try {
      const data = await fetchAnalytics();
      if (data && typeof data === 'object') {
        const totalProfit = (data.final_capital || data.total_value || 0)
          - (data.initial_capital || data.starting_balance || 10000);
        setAnalytics({
          totalValue: data.total_value || 0,
          totalProfit,
          profitPercentage: data.pnl_percent || 0,
          totalTrades: data.total_trades || 0,
          winRate: data.win_rate || 0,
          averageProfit: data.avg_profit || 0,
          bestTrade: data.best_trade
            ? { asset: data.best_trade.symbol, profit: data.best_trade.profit, percentage: data.best_trade.percent }
            : { asset: '-', profit: 0, percentage: 0 },
          worstTrade: data.worst_trade
            ? { asset: data.worst_trade.symbol, loss: data.worst_trade.profit, percentage: data.worst_trade.percent }
            : { asset: '-', loss: 0, percentage: 0 },
          assetAllocation: data.asset_allocation || [],
          performanceHistory: [],
          hasData: data.has_data ?? false,
        });
      }
    } catch (err) {
      console.error('Failed to load analytics:', err);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadAnalytics();
    setRefreshing(false);
  }, [loadAnalytics]);

  if (loading && !refreshing && !analytics) {
    return (
      <PageTransition type="fade">
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.brand.primary} />
          <Text style={styles.loadingText}>Φόρτωση analytics...</Text>
        </View>
      </PageTransition>
    );
  }

  if (error && !analytics) {
    return (
      <PageTransition type="fade">
        <NoData onRetry={loadAnalytics} />
      </PageTransition>
    );
  }

  if (!analytics) {
    return null;
  }

  if (!analytics.hasData) {
    return (
      <PageTransition type="fade">
        <View style={styles.loadingContainer}>
          <Text style={{ fontSize: 48, marginBottom: 16 }}>📊</Text>
          <Text style={styles.emptyTitle}>Δεν υπάρχουν δεδομένα ακόμα</Text>
          <Text style={styles.emptySubtitle}>Κάνε το πρώτο σου trade για να δεις analytics</Text>
        </View>
      </PageTransition>
    );
  }

  const profitColor = analytics.totalProfit >= 0 
    ? theme.colors.market.bullish 
    : theme.colors.market.bearish;

  return (
    <PageTransition type="fade">
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
        {/* Time Range Selector */}
        <View style={styles.timeRangeContainer}>
          {(['7d', '30d', '90d', 'all'] as const).map((range) => (
            <TouchableOpacity
              key={range}
              style={[
                styles.timeRangeButton,
                timeRange === range && styles.timeRangeButtonActive,
              ]}
              onPress={() => setTimeRange(range)}
            >
              <Text
                style={[
                  styles.timeRangeText,
                  timeRange === range && styles.timeRangeTextActive,
                ]}
              >
                {range === 'all' ? 'Όλα' : range}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Portfolio Overview */}
        <AnimatedCard delay={0} animationType="slideUp">
          <Text style={styles.cardTitle}>📊 Portfolio Overview</Text>
          
          <View style={styles.overviewRow}>
            <View style={styles.overviewItem}>
              <Text style={styles.overviewLabel}>Συνολική Αξία</Text>
              <AnimatedCounter
                value={analytics.totalValue}
                decimals={2}
                prefix="$"
                duration={1500}
                style={styles.overviewValue}
              />
            </View>
            <View style={styles.overviewItem}>
              <Text style={styles.overviewLabel}>Κέρδος/Ζημιά</Text>
              <AnimatedCounter
                value={Math.abs(analytics.totalProfit)}
                decimals={2}
                prefix={analytics.totalProfit >= 0 ? '+$' : '-$'}
                duration={1500}
                style={[styles.overviewValue, { color: profitColor }]}
              />
              <Text style={[styles.overviewPercentage, { color: profitColor }]}>
                ({analytics.profitPercentage >= 0 ? '+' : ''}{analytics.profitPercentage.toFixed(2)}%)
              </Text>
            </View>
          </View>
        </AnimatedCard>

        {/* Performance Metrics */}
        <AnimatedCard delay={100} animationType="slideUp">
          <Text style={styles.cardTitle}>📈 Performance Metrics</Text>
          
          <View style={styles.metricsGrid}>
            <View style={styles.metricItem}>
              <Text style={styles.metricValue}>{analytics.totalTrades}</Text>
              <Text style={styles.metricLabel}>Σύνολο Trades</Text>
            </View>
            <View style={styles.metricItem}>
              <Text style={[styles.metricValue, { color: theme.colors.semantic.success }]}>
                {analytics.winRate.toFixed(0)}%
              </Text>
              <Text style={styles.metricLabel}>Win Rate</Text>
            </View>
            <View style={styles.metricItem}>
              <Text style={styles.metricValue}>
                {NumberFormatter.toCurrency(analytics.averageProfit)}
              </Text>
              <Text style={styles.metricLabel}>Μέσο Κέρδος</Text>
            </View>
          </View>
        </AnimatedCard>

        {/* Best & Worst Trades */}
        <AnimatedCard delay={200} animationType="slideUp">
          <Text style={styles.cardTitle}>🏆 Best & Worst Trades</Text>
          
          {/* Best Trade */}
          <View style={[styles.tradeHighlight, { backgroundColor: theme.colors.semantic.success + '15' }]}>
            <View style={styles.tradeHighlightHeader}>
              <Text style={styles.tradeHighlightIcon}>🚀</Text>
              <Text style={styles.tradeHighlightTitle}>Best Trade</Text>
            </View>
            <Text style={styles.tradeHighlightAsset}>{analytics.bestTrade.asset}</Text>
            <Text style={[styles.tradeHighlightProfit, { color: theme.colors.semantic.success }]}>
              +{NumberFormatter.toCurrency(analytics.bestTrade.profit)} (+{analytics.bestTrade.percentage.toFixed(2)}%)
            </Text>
          </View>

          {/* Worst Trade */}
          <View style={[styles.tradeHighlight, { backgroundColor: theme.colors.semantic.error + '15' }]}>
            <View style={styles.tradeHighlightHeader}>
              <Text style={styles.tradeHighlightIcon}>📉</Text>
              <Text style={styles.tradeHighlightTitle}>Worst Trade</Text>
            </View>
            <Text style={styles.tradeHighlightAsset}>{analytics.worstTrade.asset}</Text>
            <Text style={[styles.tradeHighlightProfit, { color: theme.colors.semantic.error }]}>
              -{NumberFormatter.toCurrency(Math.abs(analytics.worstTrade.loss))} ({analytics.worstTrade.percentage.toFixed(2)}%)
            </Text>
          </View>
        </AnimatedCard>

        {/* Asset Allocation */}
        <AnimatedCard delay={300} animationType="slideUp">
          <Text style={styles.cardTitle}>💼 Asset Allocation</Text>
          
          {analytics.assetAllocation.map((asset) => (
            <View key={asset.asset} style={styles.assetItem}>
              <View style={styles.assetHeader}>
                <Text style={styles.assetName}>{asset.asset}</Text>
                <Text style={styles.assetValue}>
                  {NumberFormatter.toCurrency(asset.value)}
                </Text>
              </View>
              <View style={styles.assetProgressContainer}>
                <AnimatedProgressBar
                  progress={asset.percentage / 100}
                  color={theme.colors.brand.primary}
                  height={8}
                  animated
                />
                <Text style={styles.assetPercentage}>{asset.percentage.toFixed(1)}%</Text>
              </View>
            </View>
          ))}
        </AnimatedCard>

        <View style={styles.bottomPadding} />
      </ScrollView>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.xl,
  },
  loadingText: {
    marginTop: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  emptyTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    textAlign: 'center',
    marginBottom: theme.spacing.sm,
  },
  emptySubtitle: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  timeRangeContainer: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.md,
  },
  timeRangeButton: {
    flex: 1,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  timeRangeButtonActive: {
    backgroundColor: theme.colors.brand.primary,
    borderColor: theme.colors.brand.primary,
  },
  timeRangeText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  timeRangeTextActive: {
    color: '#FFFFFF',
  },
  cardTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  overviewRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: theme.spacing.md,
  },
  overviewItem: {
    flex: 1,
  },
  overviewLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  overviewValue: {
    fontSize: theme.typography.sizes['2xl'],
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  overviewPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    marginTop: theme.spacing.xs,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: theme.spacing.sm,
  },
  metricItem: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.md,
    alignItems: 'center',
  },
  metricValue: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  metricLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
  tradeHighlight: {
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.lg,
    marginBottom: theme.spacing.md,
  },
  tradeHighlightHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  tradeHighlightIcon: {
    fontSize: 20,
    marginRight: theme.spacing.xs,
  },
  tradeHighlightTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  tradeHighlightAsset: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  tradeHighlightProfit: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
  },
  assetItem: {
    marginBottom: theme.spacing.md,
  },
  assetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.xs,
  },
  assetName: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  assetValue: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  assetProgressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  assetPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    minWidth: 45,
    textAlign: 'right',
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
});


