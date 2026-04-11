import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity, Share } from 'react-native';

import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { useAppStore } from '../mobile/src/stores/appStore';
import { theme } from '../mobile/src/constants/theme';

interface WeeklyStats {
  pnl_pct: number;
  total_trades: number;
  win_rate: number;
  ai_accuracy: number;
  best_trade: string;
  worst_trade: string;
  onchain_summary?: {
    market_sentiment?: 'bullish' | 'bearish' | 'neutral' | string;
    average_score?: number;
    tracked_assets?: number;
    strongest_bullish?: {
      symbol?: string;
      average_score?: number;
    } | null;
    strongest_bearish?: {
      symbol?: string;
      average_score?: number;
    } | null;
  } | null;
}

interface WeeklyReportItem {
  week_start: string;
  stats: WeeklyStats;
  report_text: string;
  created_at?: string;
}

export default function WeeklyReportScreen() {
  const { t, language } = useLanguage();
  const { showToast } = useAppStore();

  const [latest, setLatest] = useState<WeeklyReportItem | null>(null);
  const [history, setHistory] = useState<WeeklyReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [latestRes, historyRes] = await Promise.all([
        api.getLatestWeeklyReport().catch(() => null),
        api.getWeeklyReports().catch(() => ({ reports: [] })),
      ]);

      const latestItem = latestRes && latestRes.week_start
        ? {
            week_start: latestRes.week_start,
            stats: latestRes.stats || {
              pnl_pct: 0,
              total_trades: 0,
              win_rate: 0,
              ai_accuracy: 0,
              best_trade: 'N/A',
              worst_trade: 'N/A',
            },
            report_text: latestRes.report_text || '',
            created_at: latestRes.created_at,
          }
        : null;

      setLatest(latestItem);
      setHistory(Array.isArray(historyRes?.reports) ? historyRes.reports : []);
    } catch {
      showToast(t('error'), 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const stats = latest?.stats;
  const pnlColor = (stats?.pnl_pct || 0) >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish;

  const onchainSentimentLabel = useCallback((sentiment?: string | null) => {
    if (sentiment === 'bullish') return t('onchainBullish');
    if (sentiment === 'bearish') return t('onchainBearish');
    return t('onchainNeutral');
  }, [t]);

  const shareText = useMemo(() => {
    if (!stats) return '';
    return (
      `📈 AURA Performance:\n` +
      `${stats.pnl_pct >= 0 ? '+' : ''}${stats.pnl_pct.toFixed(1)}% ${t('thisWeek')}\n` +
      `Win Rate: ${stats.win_rate.toFixed(0)}% | Trades: ${stats.total_trades}\n` +
      `#AURA #AITrading`
    );
  }, [stats, t]);

  const handleShare = useCallback(async () => {
    if (!shareText) return;
    try {
      await Share.share({ message: shareText });
    } catch {
      showToast(t('error'), 'error');
    }
  }, [shareText, showToast, t]);

  const fmtDate = (isoDate: string) => {
    try {
      return new Date(isoDate).toLocaleDateString(language === 'el' ? 'el-GR' : 'en-US');
    } catch {
      return isoDate;
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.header}>{t('weeklyReportTitle')}</Text>

      {loading ? (
        <Text style={styles.subtle}>{t('loading')}</Text>
      ) : !latest ? (
        <Text style={styles.subtle}>{t('weeklyReportEmpty')}</Text>
      ) : (
        <>
          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>{t('weeklyPnl')}</Text>
              <Text style={[styles.statValue, { color: pnlColor }]}>{stats?.pnl_pct?.toFixed(2)}%</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>{t('totalTrades')}</Text>
              <Text style={styles.statValue}>{stats?.total_trades ?? 0}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>{t('winRate')}</Text>
              <Text style={styles.statValue}>{stats?.win_rate?.toFixed(1)}%</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>{t('aiAccuracy')}</Text>
              <Text style={styles.statValue}>{stats?.ai_accuracy?.toFixed(1)}%</Text>
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('weeklyAiReport')}</Text>
            <Text style={styles.cardText}>{latest.report_text || t('weeklyReportEmpty')}</Text>
          </View>

          {!!stats?.onchain_summary && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{t('weeklyOnchainOverview')}</Text>
              <View style={styles.historyRow}>
                <Text style={styles.historyDate}>{t('onchainMarketSentiment')}</Text>
                <Text style={styles.historyPnl}>{onchainSentimentLabel(stats.onchain_summary.market_sentiment)}</Text>
              </View>
              <View style={styles.historyRow}>
                <Text style={styles.historyDate}>{t('onchainAverageScore')}</Text>
                <Text style={styles.historyPnl}>{(((stats.onchain_summary.average_score ?? 0.5) * 100)).toFixed(0)}%</Text>
              </View>
              <View style={styles.historyRow}>
                <Text style={styles.historyDate}>{t('onchainTrackedAssets')}</Text>
                <Text style={styles.historyPnl}>{stats.onchain_summary.tracked_assets ?? 0}</Text>
              </View>
              <Text style={styles.cardText}>
                {t('onchainStrongestBullish')}: {stats.onchain_summary.strongest_bullish?.symbol || 'N/A'}
              </Text>
              <Text style={styles.cardText}>
                {t('onchainStrongestBearish')}: {stats.onchain_summary.strongest_bearish?.symbol || 'N/A'}
              </Text>
            </View>
          )}

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('bestWorstTrades')}</Text>
            <Text style={styles.cardText}>✅ {t('bestTrade')}: {stats?.best_trade || 'N/A'}</Text>
            <Text style={styles.cardText}>⚠️ {t('worstTrade')}: {stats?.worst_trade || 'N/A'}</Text>
          </View>

          <TouchableOpacity style={styles.shareButton} onPress={handleShare}>
            <Text style={styles.shareText}>{t('shareWeeklyReport')}</Text>
          </TouchableOpacity>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('weeklyHistory')}</Text>
            {history.slice(0, 4).map((item) => (
              <View key={`${item.week_start}-${item.created_at || ''}`} style={styles.historyRow}>
                <Text style={styles.historyDate}>{fmtDate(item.week_start)}</Text>
                <Text style={[styles.historyPnl, { color: (item.stats?.pnl_pct || 0) >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                  {(item.stats?.pnl_pct || 0) >= 0 ? '+' : ''}{(item.stats?.pnl_pct || 0).toFixed(2)}%
                </Text>
              </View>
            ))}
          </View>
        </>
      )}
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
    paddingBottom: theme.spacing.xl,
    gap: theme.spacing.md,
  },
  header: {
    fontSize: 24,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  subtle: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.md,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: theme.spacing.sm,
  },
  statCard: {
    width: '48%',
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    padding: theme.spacing.md,
  },
  statLabel: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.xs,
    marginBottom: 4,
  },
  statValue: {
    color: theme.colors.text.primary,
    fontWeight: '700',
    fontSize: theme.typography.sizes.lg,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    padding: theme.spacing.md,
  },
  cardTitle: {
    color: theme.colors.text.primary,
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    marginBottom: theme.spacing.xs,
  },
  cardText: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
    lineHeight: 20,
  },
  shareButton: {
    backgroundColor: theme.colors.brand.primary,
    borderRadius: theme.borderRadius.md,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  shareText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: theme.typography.sizes.sm,
  },
  historyRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: theme.spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  historyDate: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
  },
  historyPnl: {
    fontWeight: '700',
    fontSize: theme.typography.sizes.sm,
  },
});
