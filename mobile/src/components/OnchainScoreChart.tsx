import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, ScrollView } from 'react-native';
import { theme } from '../constants/theme';
import { useLanguage } from '../hooks/useLanguage';
import { api } from '../services/apiClient';

interface OnchainHistoryPoint {
  timestamp: string;
  score: number;
  sentiment: string;
  symbol: string;
}

interface OnchainScoreChartProps {
  symbol: string;
  days?: number;
}

/**
 * On-chain Score History Chart Component
 * Displays historical on-chain signal scores for a crypto asset
 */
export const OnchainScoreChart: React.FC<OnchainScoreChartProps> = ({ symbol, days = 30 }) => {
  const { t } = useLanguage();
  const [data, setData] = useState<OnchainHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    avg: 0,
    min: 0,
    max: 0,
    current: 0,
  });

  useEffect(() => {
    loadOnchainHistory();
  }, [symbol, days]);

  const loadOnchainHistory = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch on-chain history
      const response = await api.getOnchainHistory(symbol, days);
      
      if (response?.history) {
        const history = response.history;
        setData(history);

        // Calculate stats
        if (history.length > 0) {
          const scores = history.map((h: OnchainHistoryPoint) => h.score);
          const avg = scores.reduce((a: number, b: number) => a + b, 0) / scores.length;
          const min = Math.min(...scores);
          const max = Math.max(...scores);
          const current = history[history.length - 1]?.score || 0;

          setStats({
            avg: parseFloat(avg.toFixed(3)),
            min: parseFloat(min.toFixed(3)),
            max: parseFloat(max.toFixed(3)),
            current: parseFloat(current.toFixed(3)),
          });
        }
      }
    } catch (err: any) {
      console.error('Failed to load on-chain history:', err);
      setError(err?.message || 'Failed to load on-chain data');
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (sentiment: string): string => {
    switch (sentiment?.toLowerCase()) {
      case 'bullish':
        return theme.colors.market.bullish;
      case 'bearish':
        return theme.colors.market.bearish;
      case 'neutral':
      default:
        return theme.colors.market.neutral;
    }
  };

  const getSentimentEmoji = (sentiment: string): string => {
    switch (sentiment?.toLowerCase()) {
      case 'bullish':
        return '🟢';
      case 'bearish':
        return '🔴';
      case 'neutral':
      default:
        return '🟡';
    }
  };

  const getScoreQuality = (score: number): string => {
    if (score >= 0.75) return t('onchainVeryStrong') || 'Very Strong';
    if (score >= 0.5) return t('onchainStrong') || 'Strong';
    if (score >= 0.25) return t('onchainModerate') || 'Moderate';
    return t('onchainWeak') || 'Weak';
  };

  if (loading) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>{t('onchainScoreHistory') || 'On-chain Score History'}</Text>
        <ActivityIndicator size="large" color={theme.colors.brand.primary} style={styles.loader} />
      </View>
    );
  }

  if (error || data.length === 0) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>{t('onchainScoreHistory') || 'On-chain Score History'}</Text>
        <Text style={styles.errorText}>{error || 'No data available'}</Text>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{t('onchainScoreHistory') || 'On-chain Score History'}</Text>
      
      {/* Stats Row */}
      <View style={styles.statsContainer}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>{t('onchainCurrent') || 'Current'}</Text>
          <Text
            style={[
              styles.statValue,
              { color: stats.current >= 0.5 ? theme.colors.market.bullish : theme.colors.market.bearish },
            ]}
          >
            {stats.current.toFixed(3)}
          </Text>
          <Text style={styles.statQuality}>{getScoreQuality(stats.current)}</Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>{t('onchainAverage') || 'Average'}</Text>
          <Text style={[styles.statValue, { color: theme.colors.brand.primary }]}>
            {stats.avg.toFixed(3)}
          </Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>{t('onchainRange') || 'Range'}</Text>
          <Text style={styles.statValue}>
            {stats.min.toFixed(3)} - {stats.max.toFixed(3)}
          </Text>
        </View>
      </View>

      {/* Mini Chart (Text-based bar visualization) */}
      <View style={styles.miniChartContainer}>
        <Text style={styles.miniChartLabel}>{t('onchainRecent') || 'Recent Trend'}</Text>
        <View style={styles.barsContainer}>
          {data.slice(-7).map((point, idx) => {
            const date = new Date(point.timestamp);
            const dayStr = date.toLocaleDateString('en-US', { weekday: 'short' });
            const barHeight = Math.max(10, (point.score / 1.0) * 60); // Scale to 60px max
            const barColor = getSentimentColor(point.sentiment);

            return (
              <View key={idx} style={styles.barWrapper}>
                <View
                  style={[
                    styles.bar,
                    {
                      height: barHeight,
                      backgroundColor: barColor,
                    },
                  ]}
                />
                <Text style={styles.barLabel}>{dayStr}</Text>
              </View>
            );
          })}
        </View>
      </View>

      {/* Sentiment Timeline */}
      <View style={styles.sentimentTimeline}>
        <Text style={styles.timelineLabel}>{t('onchainSentimentTrend') || 'Sentiment Trend'}</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {data.slice(-10).map((point, idx) => {
            const date = new Date(point.timestamp);
            const timeStr = date.toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <View key={idx} style={styles.timelineItem}>
                <Text style={styles.timelineEmoji}>{getSentimentEmoji(point.sentiment)}</Text>
                <Text style={styles.timelineScore}>{point.score.toFixed(2)}</Text>
                <Text style={styles.timelineTime}>{timeStr}</Text>
              </View>
            );
          })}
        </ScrollView>
      </View>

      {/* Data Points */}
      <View style={styles.dataTable}>
        <View style={styles.tableHeader}>
          <Text style={[styles.tableCell, styles.tableCellFlex2]}>{t('onchainDate') || 'Date'}</Text>
          <Text style={[styles.tableCell, styles.tableCellFlex1]}>{t('onchainScore') || 'Score'}</Text>
          <Text style={[styles.tableCell, styles.tableCellFlex1]}>{t('onchainSentiment') || 'Sentiment'}</Text>
        </View>
        <ScrollView nestedScrollEnabled style={styles.tableBody}>
          {data.slice().reverse().map((point, idx) => {
            const date = new Date(point.timestamp);
            const dateStr = date.toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });
            const sentimentColor = getSentimentColor(point.sentiment);

            return (
              <View key={idx} style={styles.tableRow}>
                <Text style={[styles.tableCell, styles.tableCellFlex2]}>{dateStr}</Text>
                <Text style={[styles.tableCell, styles.tableCellFlex1, { color: sentimentColor }]}>
                  {point.score.toFixed(3)}
                </Text>
                <Text
                  style={[
                    styles.tableCell,
                    styles.tableCellFlex1,
                    { color: sentimentColor },
                  ]}
                >
                  {getSentimentEmoji(point.sentiment)}
                </Text>
              </View>
            );
          })}
        </ScrollView>
      </View>

      {/* Info Footer */}
      <View style={styles.infoBox}>
        <Text style={styles.infoText}>
          📊 {data.length} {t('onchainDataPoints') || 'data points'} over {days} days
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  title: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  loader: {
    marginVertical: theme.spacing.lg,
  },
  errorText: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.semantic.error,
    marginVertical: theme.spacing.md,
    textAlign: 'center',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: theme.spacing.lg,
    gap: theme.spacing.sm,
  },
  statBox: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    alignItems: 'center',
  },
  statLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
    textTransform: 'uppercase',
  },
  statValue: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.brand.primary,
    marginBottom: theme.spacing.xs,
  },
  statQuality: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    fontStyle: 'italic',
  },
  miniChartContainer: {
    marginVertical: theme.spacing.md,
    paddingBottom: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  miniChartLabel: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  barsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 100,
    gap: theme.spacing.xs,
  },
  barWrapper: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  bar: {
    width: '100%',
    borderRadius: theme.borderRadius.sm,
    marginBottom: theme.spacing.xs,
  },
  barLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  sentimentTimeline: {
    marginVertical: theme.spacing.md,
    paddingBottom: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  timelineLabel: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  timelineItem: {
    marginRight: theme.spacing.md,
    alignItems: 'center',
    minWidth: 70,
  },
  timelineEmoji: {
    fontSize: 28,
    marginBottom: theme.spacing.xs,
  },
  timelineScore: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  timelineTime: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  dataTable: {
    marginTop: theme.spacing.md,
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    backgroundColor: theme.colors.ui.background,
  },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: theme.colors.ui.border,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
  },
  tableBody: {
    maxHeight: 150,
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  tableCell: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  tableCellFlex1: {
    flex: 1,
  },
  tableCellFlex2: {
    flex: 2,
  },
  infoBox: {
    marginTop: theme.spacing.md,
    backgroundColor: theme.colors.brand.primary + '10',
    borderRadius: theme.borderRadius.md,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
  },
  infoText: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
});

export default OnchainScoreChart;
