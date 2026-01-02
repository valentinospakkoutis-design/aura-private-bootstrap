import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, Dimensions, TouchableOpacity } from 'react-native';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { NumberFormatter } from '../mobile/src/utils/NumberFormatter';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';

const { width } = Dimensions.get('window');

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
}

export default function AnalyticsScreen() {
  const { showToast } = useAppStore();
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const {
    loading,
    error,
    execute: fetchAnalytics,
  } = useApi(() => {
    // Placeholder - implement actual API call
    return Promise.resolve({
      totalValue: 10000,
      totalProfit: 500,
      profitPercentage: 5,
      totalTrades: 25,
      winRate: 68,
      averageProfit: 20,
      bestTrade: {
        asset: 'BTC/USDT',
        profit: 250,
        percentage: 12.5,
      },
      worstTrade: {
        asset: 'ETH/USDT',
        loss: -100,
        percentage: -5.2,
      },
      assetAllocation: [
        { asset: 'BTC/USDT', percentage: 40, value: 4000 },
        { asset: 'ETH/USDT', percentage: 30, value: 3000 },
        { asset: 'GOLD', percentage: 20, value: 2000 },
        { asset: 'SILVER', percentage: 10, value: 1000 },
      ],
      performanceHistory: [],
    } as AnalyticsData);
  }, { showLoading: false, showToast: false });

  useEffect(() => {
    loadAnalytics();
  }, [timeRange]);

  const loadAnalytics = async () => {
    try {
      const data = await fetchAnalytics();
      if (data && typeof data === 'object') {
        setAnalytics(data as AnalyticsData);
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
          
          {analytics.assetAllocation.map((asset, index) => (
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
    borderRadius: theme.borderRadius.medium,
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
    fontSize: theme.typography.sizes.lg,
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
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.large,
  },
  metricItem: {
    flex: 1,
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
    borderRadius: theme.borderRadius.large,
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
    color: theme.colors.text.primary,
  },
  assetProgressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  assetPercentage: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
    minWidth: 50,
    textAlign: 'right',
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
});

