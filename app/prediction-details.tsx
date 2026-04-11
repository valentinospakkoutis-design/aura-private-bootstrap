import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { Button } from '../mobile/src/components/Button';
import { theme } from '../mobile/src/constants/theme';
import { useLanguage } from '../mobile/src/hooks/useLanguage';

interface PredictionDetail {
  id: string;
  asset: string;
  symbol: string;
  action: string;
  confidence: number;
  price: number;
  targetPrice: number;
  timestamp: string;
  reasoning: string;
  trend: string;
  trendScore: number;
  priceChange: number;
  priceChangePercent: number;
  recommendationStrength: string;
  pricePath: Array<{ day: number; price: number; date: string }>;
  modelVersion: string;
  mtf_confluence?: boolean | null;
  trend_1h?: 'bullish' | 'bearish' | 'neutral' | null;
  trend_4h?: 'bullish' | 'bearish' | 'neutral' | null;
  trend_1d?: 'bullish' | 'bearish' | 'neutral' | null;
  rsi_1h?: number | null;
  ensemble?: {
    xgboost?: number | null;
    random_forest?: number | null;
    lstm?: number | null;
    method?: '3-model' | '2-model' | string;
  } | null;
  onchain?: {
    score?: number | null;
    sentiment?: 'bullish' | 'bearish' | 'neutral' | string;
    funding_rate?: number | null;
    long_short_ratio?: number | null;
    fear_greed?: number | null;
  } | null;
}

export default function PredictionDetailsScreen() {
  const router = useRouter();
  const { t } = useLanguage();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [prediction, setPrediction] = useState<PredictionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadPrediction = useCallback(async () => {
    if (!id) {
      setError('No prediction ID provided');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const response = await api.getPredictionById(id);
      setPrediction(response);
    } catch (err: any) {
      console.error('Failed to load prediction:', err);
      setError(err?.message || 'Failed to load prediction');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadPrediction();
  }, [loadPrediction]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadPrediction();
    setRefreshing(false);
  }, [loadPrediction]);

  const getActionColor = (action: string) => {
    switch (action) {
      case 'buy': return theme.colors.market.bullish;
      case 'sell': return theme.colors.market.bearish;
      case 'hold': return theme.colors.market.neutral;
      default: return theme.colors.text.secondary;
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'buy': return '📈';
      case 'sell': return '📉';
      case 'hold': return '⏸️';
      default: return '❓';
    }
  };

  const trendLabel = (trend?: string | null) => {
    if (trend === 'bullish') return t('mtfBullish');
    if (trend === 'bearish') return t('mtfBearish');
    return t('mtfNeutral');
  };

  const onchainSentimentLabel = (sentiment?: string | null) => {
    if (sentiment === 'bullish') return t('onchainBullish');
    if (sentiment === 'bearish') return t('onchainBearish');
    return t('onchainNeutral');
  };

  const fearGreedStatus = (value?: number | null) => {
    if (typeof value !== 'number') return t('onchainNeutral');
    if (value < 20) return t('onchainExtremeFear');
    if (value > 80) return t('onchainExtremeGreed');
    return t('onchainNeutral');
  };

  const fundingStatus = (value?: number | null) => {
    if (typeof value !== 'number') return 'N/A';
    return value > 0.01 ? t('onchainOverheated') : t('onchainNormal');
  };

  const longShortStatus = (value?: number | null) => {
    if (typeof value !== 'number') return 'N/A';
    return value > 2 ? t('onchainOverleveraged') : t('onchainBalanced');
  };

  if (loading && !refreshing) {
    return (
      <PageTransition type="fade">
        <View style={styles.container}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </View>
      </PageTransition>
    );
  }

  if (error || !prediction) {
    return (
      <PageTransition type="fade">
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorTitle}>Prediction Not Found</Text>
          <Text style={styles.errorText}>{error || 'Could not load prediction details.'}</Text>
          <Button title="Go Back" onPress={() => router.back()} variant="primary" size="medium" />
        </View>
      </PageTransition>
    );
  }

  const actionColor = getActionColor(prediction.action);
  const isPositive = prediction.priceChangePercent >= 0;

  return (
    <PageTransition type="slideUp">
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.assetName}>{prediction.asset}</Text>
          <Text style={styles.symbol}>{prediction.symbol}</Text>
        </View>

        {/* Action Badge */}
        <View style={[styles.actionBadge, { backgroundColor: actionColor + '20' }]}>
          <Text style={styles.actionIcon}>{getActionIcon(prediction.action)}</Text>
          <Text style={[styles.actionText, { color: actionColor }]}>
            {prediction.action?.toUpperCase() ?? 'N/A'}
          </Text>
          <Text style={[styles.strengthText, { color: actionColor }]}>
            {prediction.recommendationStrength}
          </Text>
        </View>

        {/* Price Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Price</Text>
          <View style={styles.priceRow}>
            <View style={styles.priceCol}>
              <Text style={styles.priceLabel}>Current</Text>
              <Text style={styles.priceValue}>
                ${prediction.price?.toFixed(2) ?? '0.00'}
              </Text>
            </View>
            <View style={styles.priceCol}>
              <Text style={styles.priceLabel}>Target</Text>
              <Text style={[styles.priceValue, { color: actionColor }]}>
                ${prediction.targetPrice?.toFixed(2) ?? '0.00'}
              </Text>
            </View>
          </View>
          <View style={styles.changeRow}>
            <Text style={[styles.changeText, { color: isPositive ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
              {isPositive ? '+' : ''}{prediction.priceChangePercent?.toFixed(2) ?? '0'}% ({isPositive ? '+' : ''}${prediction.priceChange?.toFixed(2) ?? '0'})
            </Text>
          </View>
        </View>

        {/* Confidence Card */}
        <View style={styles.card}>
          <View style={styles.confidenceHeader}>
            <Text style={styles.cardTitle}>AI Confidence</Text>
            <Text style={styles.confidenceValue}>{((prediction.confidence ?? 0) * 100).toFixed(0)}%</Text>
          </View>
          <AnimatedProgressBar progress={prediction.confidence ?? 0} color={actionColor} height={10} animated />
          <Text style={styles.modelVersion}>Model: {prediction.modelVersion}</Text>
          {prediction.ensemble?.method && (
            <Text style={styles.ensembleMethod}>
              {prediction.ensemble.method === '3-model' ? t('ensembleBadge3Model') : t('ensembleBadge2Model')}
            </Text>
          )}
        </View>

        {prediction.ensemble && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('ensembleBreakdownTitle')}</Text>

            <View style={styles.ensembleRow}>
              <Text style={styles.ensembleLabel}>XGBoost</Text>
              <Text style={styles.ensembleValue}>
                {typeof prediction.ensemble.xgboost === 'number' ? `${(prediction.ensemble.xgboost * 100).toFixed(0)}%` : 'N/A'}
              </Text>
            </View>
            <AnimatedProgressBar progress={prediction.ensemble.xgboost ?? 0} color={theme.colors.brand.primary} height={8} animated />

            <View style={styles.ensembleSpacer} />

            <View style={styles.ensembleRow}>
              <Text style={styles.ensembleLabel}>RandomForest</Text>
              <Text style={styles.ensembleValue}>
                {typeof prediction.ensemble.random_forest === 'number' ? `${(prediction.ensemble.random_forest * 100).toFixed(0)}%` : 'N/A'}
              </Text>
            </View>
            <AnimatedProgressBar progress={prediction.ensemble.random_forest ?? 0} color={'#2563eb'} height={8} animated />

            <View style={styles.ensembleSpacer} />

            <View style={styles.ensembleRow}>
              <Text style={styles.ensembleLabel}>LSTM</Text>
              <Text style={styles.ensembleValue}>
                {typeof prediction.ensemble.lstm === 'number' ? `${(prediction.ensemble.lstm * 100).toFixed(0)}%` : 'N/A'}
              </Text>
            </View>
            <AnimatedProgressBar progress={prediction.ensemble.lstm ?? 0} color={'#7c3aed'} height={8} animated />
          </View>
        )}

        {prediction.onchain && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('onchainSignalsTitle')}</Text>

            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>{t('onchainFundingRate')}</Text>
              <Text style={styles.trendValue}>
                {typeof prediction.onchain.funding_rate === 'number'
                  ? `${prediction.onchain.funding_rate.toFixed(3)}% ${fundingStatus(prediction.onchain.funding_rate)}`
                  : 'N/A'}
              </Text>
            </View>

            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>{t('onchainLongShort')}</Text>
              <Text style={styles.trendValue}>
                {typeof prediction.onchain.long_short_ratio === 'number'
                  ? `${prediction.onchain.long_short_ratio.toFixed(2)}x ${longShortStatus(prediction.onchain.long_short_ratio)}`
                  : 'N/A'}
              </Text>
            </View>

            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>{t('onchainFearGreed')}</Text>
              <Text style={styles.trendValue}>
                {typeof prediction.onchain.fear_greed === 'number'
                  ? `${prediction.onchain.fear_greed} ${fearGreedStatus(prediction.onchain.fear_greed)}`
                  : 'N/A'}
              </Text>
            </View>

            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>{t('onchainSentiment')}</Text>
              <Text style={styles.trendValue}>{onchainSentimentLabel(prediction.onchain.sentiment)}</Text>
            </View>
          </View>
        )}

        {/* Trend Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Trend Analysis</Text>
          <View style={styles.trendRow}>
            <Text style={styles.trendLabel}>Direction:</Text>
            <Text style={[styles.trendValue, { color: actionColor }]}>{prediction.trend}</Text>
          </View>
          <View style={styles.trendRow}>
            <Text style={styles.trendLabel}>Score:</Text>
            <Text style={styles.trendValue}>{prediction.trendScore?.toFixed(3) ?? 'N/A'}</Text>
          </View>
        </View>

        {(prediction.trend_1h || prediction.trend_4h || prediction.trend_1d) && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('timeframeAnalysis')}</Text>
            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>1h</Text>
              <Text style={styles.trendValue}>{trendLabel(prediction.trend_1h)}</Text>
            </View>
            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>4h</Text>
              <Text style={styles.trendValue}>{trendLabel(prediction.trend_4h)}</Text>
            </View>
            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>1d</Text>
              <Text style={styles.trendValue}>{trendLabel(prediction.trend_1d)}</Text>
            </View>
            <View style={styles.trendRow}>
              <Text style={styles.trendLabel}>{t('rsi1h')}</Text>
              <Text style={styles.trendValue}>
                {typeof prediction.rsi_1h === 'number' ? prediction.rsi_1h.toFixed(1) : 'N/A'}
              </Text>
            </View>
            <View style={[styles.mtfBadge, { backgroundColor: prediction.mtf_confluence ? '#16a34a18' : '#f59e0b1c' }]}>
              <Text style={[styles.mtfBadgeText, { color: prediction.mtf_confluence ? '#166534' : '#92400e' }]}>
                {prediction.mtf_confluence ? t('mtfStrongSignal') : t('mtfWeakSignal')}
              </Text>
            </View>
          </View>
        )}

        {/* Reasoning Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>AI Reasoning</Text>
          <Text style={styles.reasoning}>{prediction.reasoning}</Text>
        </View>

        {/* Timestamp */}
        <Text style={styles.timestamp}>
          Updated: {new Date(prediction.timestamp).toLocaleString('el-GR')}
        </Text>

        {/* Back Button */}
        <Button title="Back to Predictions" onPress={() => router.back()} variant="secondary" size="large" fullWidth style={styles.backButton} />

        <View style={{ height: theme.spacing.xl }} />
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
  header: {
    marginBottom: theme.spacing.md,
  },
  assetName: {
    fontSize: theme.typography.sizes['3xl'] || 28,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  symbol: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.xs,
  },
  actionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.lg,
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.lg,
  },
  actionIcon: {
    fontSize: 20,
  },
  actionText: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
  },
  strengthText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
  },
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
  cardTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  priceCol: {
    flex: 1,
  },
  priceLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  priceValue: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  changeRow: {
    marginTop: theme.spacing.md,
    paddingTop: theme.spacing.md,
    borderTopWidth: 1,
    borderTopColor: theme.colors.ui.border,
  },
  changeText: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '600',
  },
  confidenceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  confidenceValue: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  modelVersion: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.sm,
  },
  ensembleMethod: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.sm,
    fontWeight: '600',
  },
  ensembleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.xs,
  },
  ensembleLabel: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  ensembleValue: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontWeight: '700',
  },
  ensembleSpacer: {
    height: theme.spacing.sm,
  },
  trendRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  trendLabel: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  trendValue: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  mtfBadge: {
    marginTop: theme.spacing.sm,
    alignSelf: 'flex-start',
    borderRadius: theme.borderRadius.full,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: 4,
  },
  mtfBadgeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
  },
  reasoning: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 24,
  },
  timestamp: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    textAlign: 'center',
    marginVertical: theme.spacing.md,
  },
  backButton: {
    marginTop: theme.spacing.sm,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.xl,
    backgroundColor: theme.colors.ui.background,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: theme.spacing.md,
  },
  errorTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  errorText: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    textAlign: 'center',
    marginBottom: theme.spacing.lg,
  },
});

