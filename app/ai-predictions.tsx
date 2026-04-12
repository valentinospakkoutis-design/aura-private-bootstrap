import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, ActivityIndicator, TouchableOpacity, ScrollView } from 'react-native';
import { type Prediction, useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { NoPredictions } from '../mobile/src/components/NoPredictions';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { useRouter } from 'expo-router';
import { usePriceUpdates } from '../mobile/src/hooks/useWebSocket';
import { useOfflineMode } from '../mobile/src/hooks/useOfflineMode';
import { useLanguage } from '../mobile/src/hooks/useLanguage';

interface Mover {
  symbol: string;
  name: string;
  category: string;
  price: number;
  change_pct: number;
  confidence: number;
}

interface ModelHealth {
  symbol: string;
  version: number;
  accuracy: number;
  trend: 'improving' | 'declining' | 'stable';
  last_improved?: string | null;
  feedback_trades?: number;
}

interface PredictionAccuracyResponse {
  overall_accuracy_7d?: number;
  per_symbol_accuracy?: Record<string, number>;
}

interface ModelPerformanceEntry {
  symbol?: string;
  accuracy?: number | null;
}

interface ModelPerformanceResponse {
  models?: ModelPerformanceEntry[];
}

interface ModelHealthResponse {
  models?: ModelHealth[];
}

interface RLPrediction {
  action?: 'BUY' | 'SELL' | 'HOLD';
  val_sharpe?: number;
}

interface RLPredictionResponse {
  predictions?: Record<string, RLPrediction>;
}

const CATEGORIES = [
  { key: 'all', label: 'Όλα' },
  { key: 'crypto', label: 'Crypto' },
  { key: 'bonds', label: 'Bonds' },
  { key: 'derivatives', label: 'Derivatives' },
  { key: 'sentiment', label: 'Sentiment' },
] as const;

export default function AIPredictionsScreen() {
  const router = useRouter();
  const { t, language } = useLanguage();
  const { predictions, setPredictions } = useAppStore();
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [movers, setMovers] = useState<{ top_gainers: Mover[]; top_losers: Mover[]; top_volume: Mover[] } | null>(null);
  const [modelAccuracy, setModelAccuracy] = useState<Record<string, number>>({});
  const [rlData, setRlData] = useState<RLPredictionResponse | null>(null);
  const [historicalAccuracy, setHistoricalAccuracy] = useState<number | null>(null);
  const [symbolHistoricalAccuracy, setSymbolHistoricalAccuracy] = useState<Record<string, number>>({});
  const [modelHealthBySymbol, setModelHealthBySymbol] = useState<Record<string, ModelHealth>>({});
  const { isOfflineMode } = useOfflineMode();

  const {
    error,
    loading,
    execute: fetchPredictions,
  } = useApi<Prediction[], [boolean?]>((useCache?: boolean) => api.getPredictions(useCache), { showLoading: false, showToast: false });

  const assets = predictions?.map((p) => p.asset) || [];
  const { prices, isConnected } = usePriceUpdates(assets);

  useEffect(() => {
    loadAll();
  }, []);

  const predictionsRef = useRef(predictions);
  useEffect(() => { predictionsRef.current = predictions; }, [predictions]);

  useEffect(() => {
    if (prices.size > 0 && predictionsRef.current && predictionsRef.current.length > 0) {
      setPredictions(
        predictionsRef.current.map((prediction) => {
          const priceUpdate = prices.get(prediction.asset);
          if (priceUpdate) {
            return { ...prediction, price: priceUpdate.price, timestamp: priceUpdate.timestamp };
          }
          return prediction;
        })
      );
    }
  }, [prices, setPredictions]);

  const loadAll = async () => {
    try {
      const [result] = await Promise.all([
        fetchPredictions(isOfflineMode),
        api.getMarketMovers().then(setMovers).catch(() => {}),
        api.getRLBatchPredictions().then(setRlData).catch(() => {}),
        api.getAIPredictionAccuracy().then((data: PredictionAccuracyResponse) => {
          if (typeof data?.overall_accuracy_7d === 'number') {
            setHistoricalAccuracy(data.overall_accuracy_7d);
          }
          setSymbolHistoricalAccuracy(data?.per_symbol_accuracy || {});
        }).catch(() => {}),
        api.getModelPerformance().then((data: ModelPerformanceResponse) => {
          const map: Record<string, number> = {};
          for (const m of data?.models || []) {
            if (m.symbol && m.accuracy != null) map[m.symbol] = m.accuracy;
          }
          setModelAccuracy(map);
        }).catch(() => {}),
        api.getAIModelHealth().then((data: ModelHealthResponse) => {
          const map: Record<string, ModelHealth> = {};
          for (const m of data?.models || []) {
            if (m.symbol) map[m.symbol] = m;
          }
          setModelHealthBySymbol(map);
        }).catch(() => {}),
      ]);
      if (Array.isArray(result)) setPredictions(result);
    } catch (err) {
      console.error('Failed to load predictions:', err);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadAll();
    setRefreshing(false);
  };

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

  const trendArrow = (trend?: string | null) => {
    if (trend === 'bullish') return '↑';
    if (trend === 'bearish') return '↓';
    return '→';
  };

  const onchainIndicator = (sentiment?: string | null) => {
    if (sentiment === 'bullish') return { icon: '🟢', label: t('onchainBullish'), color: theme.colors.market.bullish };
    if (sentiment === 'bearish') return { icon: '🔴', label: t('onchainBearish'), color: theme.colors.market.bearish };
    return { icon: '🟡', label: t('onchainNeutral'), color: '#ca8a04' };
  };

  const modelTrendArrow = (trend?: string) => {
    if (trend === 'improving') return '↑';
    if (trend === 'declining') return '↓';
    return '→';
  };

  const filteredPredictions = selectedCategory === 'all'
    ? predictions
    : predictions?.filter((prediction) => prediction.category === selectedCategory);

  // ── Mover Card ────────────────────────────────────────────
  const renderMoverCard = (item: Mover) => {
    const isPositive = item.change_pct >= 0;
    return (
      <View key={item.symbol} style={s.moverCard}>
        <Text style={s.moverSymbol}>{item.symbol}</Text>
        <Text style={s.moverName} numberOfLines={1}>{item.name}</Text>
        <Text style={s.moverPrice}>${item.price < 1 ? item.price.toFixed(4) : item.price.toFixed(2)}</Text>
        <View style={[s.moverBadge, { backgroundColor: isPositive ? theme.colors.market.bullish + '20' : theme.colors.market.bearish + '20' }]}>
          <Text style={[s.moverChange, { color: isPositive ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
            {isPositive ? '▲' : '▼'} {Math.abs(item.change_pct).toFixed(1)}%
          </Text>
        </View>
      </View>
    );
  };

  // ── Movers Section ────────────────────────────────────────
  const renderMoversSection = () => {
    if (!movers) return null;
    const sections = [
      { title: '📈 Πιο Κερδοφόρες', data: movers.top_gainers },
      { title: '📉 Πιο Ζημιογόνες', data: movers.top_losers },
      { title: '🔥 Υψηλή Βεβαιότητα', data: movers.top_volume },
    ];
    return (
      <View style={s.moversContainer}>
        <Text style={s.moversTitle}>Σημερινές Κορυφαίες Κινήσεις</Text>
        {sections.map((section) => (
          <View key={section.title}>
            <Text style={s.moversSectionTitle}>{section.title}</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.moversRow}>
              {section.data.map(renderMoverCard)}
            </ScrollView>
          </View>
        ))}
      </View>
    );
  };

  const getAccuracyColor = (acc: number) => {
    if (acc >= 0.55) return theme.colors.market.bullish;
    if (acc >= 0.50) return '#F59E0B';
    return theme.colors.market.bearish;
  };

  // ── Prediction Card ───────────────────────────────────────
  const renderPredictionCard = ({ item }: { item: Prediction }) => {
    const accModel = modelAccuracy[item.symbol || ''] ?? null;
    const accHist = (item.symbol && symbolHistoricalAccuracy[item.symbol] != null)
      ? symbolHistoricalAccuracy[item.symbol]
      : null;
    const health = item.symbol ? modelHealthBySymbol[item.symbol] : undefined;
    return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={() => router.push(`/prediction-details?id=${item.id}`)}
      style={s.card}
    >
      <View style={s.cardHeader}>
        <View style={s.assetContainer}>
          <Text style={s.assetName}>{item.asset}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            {item.symbol && item.symbol !== item.asset && (
              <Text style={s.symbolBadge}>{item.symbol}</Text>
            )}
            {accHist !== null && (
              <View style={[s.accuracyBadge, { backgroundColor: getAccuracyColor(accHist / 100) + '20' }]}>
                <Text style={[s.accuracyText, { color: getAccuracyColor(accHist / 100) }]}>
                  {item.symbol || item.asset} 🎯 {accHist.toFixed(0)}%
                </Text>
              </View>
            )}
            {accHist === null && accModel !== null && (
              <View style={[s.accuracyBadge, { backgroundColor: getAccuracyColor(accModel) + '20' }]}>
                <Text style={[s.accuracyText, { color: getAccuracyColor(accModel) }]}>
                  🎯 {(accModel * 100).toFixed(1)}%
                </Text>
              </View>
            )}
            {health && health.trend === 'improving' && (
              <View style={s.modelBadge}>
                <Text style={s.modelBadgeText}>
                  {t('modelVersionBadge', { version: String(health.version), arrow: modelTrendArrow(health.trend) })}
                </Text>
              </View>
            )}
            {item.ensemble?.method && (
              <View style={s.ensembleBadge}>
                <Text style={s.ensembleBadgeText}>
                  {item.ensemble.method === '3-model' ? t('ensembleBadge3Model') : t('ensembleBadge2Model')}
                </Text>
              </View>
            )}
          </View>
        </View>
        <View style={[s.actionBadge, { backgroundColor: getActionColor(item.action) + '20' }]}>
          <Text style={s.actionIcon}>{getActionIcon(item.action)}</Text>
          <Text style={[s.actionText, { color: getActionColor(item.action) }]}>
            {item.action?.toUpperCase() ?? 'N/A'}
          </Text>
        </View>
      </View>

      <View style={s.priceContainer}>
        <View style={s.priceRow}>
          <Text style={s.priceLabel}>Τρέχουσα:</Text>
          <Text style={s.priceValue}>${item.price < 1 ? item.price?.toFixed(4) : item.price?.toFixed(2)}</Text>
        </View>
        <View style={s.priceRow}>
          <Text style={s.priceLabel}>Στόχος:</Text>
          <Text style={[s.priceValue, { color: getActionColor(item.action) }]}>
            ${((item.targetPrice ?? item.price) < 1
              ? (item.targetPrice ?? item.price).toFixed(4)
              : (item.targetPrice ?? item.price).toFixed(2))}
          </Text>
        </View>
      </View>

      <View style={s.confidenceContainer}>
        <View style={s.confidenceHeader}>
          <Text style={s.confidenceLabel}>Βεβαιότητα AI:</Text>
          <Text style={s.confidenceValue}>{(item.confidence * 100).toFixed(0)}%</Text>
        </View>
        <AnimatedProgressBar progress={item.confidence} color={getActionColor(item.action)} height={8} animated />
      </View>

      <Text style={s.reasoning} numberOfLines={2}>
        {item.reasoning || (language === 'el' ? 'Ανάλυση βάσει τεχνικών δεικτών' : 'Analysis based on technical indicators')}
      </Text>

      {(item.trend_1h || item.trend_4h || item.trend_1d) && (
        <View style={[s.mtfRow, { backgroundColor: item.mtf_confluence ? '#16a34a18' : '#f59e0b1c' }]}>
          <Text style={[s.mtfText, { color: item.mtf_confluence ? '#166534' : '#92400e' }]}>
            {`1h ${trendArrow(item.trend_1h)}   4h ${trendArrow(item.trend_4h)}   1d ${trendArrow(item.trend_1d)}`}
          </Text>
          <Text style={[s.mtfStrength, { color: item.mtf_confluence ? '#15803d' : '#b45309' }]}>
            {item.mtf_confluence ? t('mtfStrongSignal') : t('mtfWeakSignal')}
          </Text>
        </View>
      )}

      {item.onchain?.sentiment && (() => {
        const chip = onchainIndicator(item.onchain.sentiment);
        return (
          <View style={s.onchainRow}>
            <Text style={[s.onchainText, { color: chip.color }]}>{chip.icon} {t('onchainLabel')}: {chip.label}</Text>
          </View>
        );
      })()}

      {/* RL Agent prediction */}
      {(() => {
        const rlPred = rlData?.predictions?.[item.symbol];
        if (!rlPred) return null;
        const rlColor = rlPred.action === 'BUY' ? '#22c55e' : rlPred.action === 'SELL' ? '#ef4444' : '#9ca3af';
        const xgAction = item.action === 'buy' ? 'BUY' : item.action === 'sell' ? 'SELL' : 'HOLD';
        const agrees = xgAction !== 'HOLD' && rlPred.action !== 'HOLD' && xgAction === rlPred.action;
        const disagrees = xgAction !== 'HOLD' && rlPred.action !== 'HOLD' && xgAction !== rlPred.action;
        return (
          <View style={{ marginTop: 6, gap: 4 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: rlColor }}>🤖 {rlPred.action}</Text>
              <Text style={{ fontSize: 11, color: '#9ca3af' }}>Sharpe {rlPred.val_sharpe?.toFixed(2)}</Text>
            </View>
            {agrees && (
              <View style={{ alignSelf: 'flex-start', backgroundColor: xgAction === 'BUY' ? '#dcfce7' : '#fee2e2', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 }}>
                <Text style={{ fontSize: 11, fontWeight: '600', color: xgAction === 'BUY' ? '#16a34a' : '#dc2626' }}>✅ Consensus {xgAction}</Text>
              </View>
            )}
            {disagrees && (
              <View style={{ alignSelf: 'flex-start', backgroundColor: '#fef9c3', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 }}>
                <Text style={{ fontSize: 11, fontWeight: '600', color: '#a16207' }}>⚠️ Split Signal</Text>
              </View>
            )}
          </View>
        );
      })()}

      <Text style={s.viewDetails}>Details →</Text>
    </TouchableOpacity>
  );};

  // ── Loading / Error / Empty states ────────────────────────
  if (loading && !refreshing && (!predictions || predictions.length === 0)) {
    return (
      <View style={s.loadingContainer}>
        <ActivityIndicator size="large" color={theme.colors.brand.primary} />
        <Text style={s.loadingTitle}>Το AI αναλύει assets...</Text>
        <Text style={s.loadingSubtitle}>Αυτό μπορεί να πάρει έως 30 δευτερόλεπτα</Text>
      </View>
    );
  }

  if (error && (!predictions || predictions.length === 0)) {
    return <View style={s.container}><NoData onRetry={loadAll} /></View>;
  }

  if (!predictions || predictions.length === 0) {
    return <View style={s.container}><NoPredictions /></View>;
  }

  return (
      <View style={s.container}>
        <FlatList
          data={filteredPredictions}
          keyExtractor={(item) => item.id}
          renderItem={renderPredictionCard}
          contentContainerStyle={s.listContent}
          ListHeaderComponent={
            <>
              {/* Connection Status */}
              {!isOfflineMode && (
                <View style={s.connectionStatus}>
                  <View style={[s.statusDot, { backgroundColor: isConnected ? theme.colors.semantic.success : theme.colors.semantic.error }]} />
                  <Text style={s.statusText}>{isConnected ? 'Live Prices' : 'Reconnecting...'}</Text>
                </View>
              )}

              {/* Top Movers */}
              {renderMoversSection()}

              {/* Historical Accuracy Header */}
              {historicalAccuracy !== null && (
                <TouchableOpacity style={s.histBadge} onPress={() => router.push('/ai-accuracy')}>
                  <Text style={s.histBadgeText}>{t('historicalAccuracyBadge', { value: historicalAccuracy.toFixed(0) })}</Text>
                </TouchableOpacity>
              )}

              {/* Model links */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.sm }}>
                <TouchableOpacity style={s.perfLink} onPress={() => router.push('/model-performance')}>
                  <Text style={s.perfLinkText}>🎯 Μοντέλα →</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.perfLink, { backgroundColor: '#6366f120', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 }]} onPress={() => router.push('/rl-performance')}>
                  <Text style={[s.perfLinkText, { color: '#6366f1' }]}>🤖 RL Agent →</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.perfLink, { backgroundColor: '#16a34a20', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 }]} onPress={() => router.push('/ai-accuracy')}>
                  <Text style={[s.perfLinkText, { color: '#16a34a' }]}>{t('aiAccuracyTitle')} →</Text>
                </TouchableOpacity>
              </View>

              {/* Category Tabs */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabsContainer} contentContainerStyle={s.tabsContent}>
                {CATEGORIES.map((cat) => (
                  <TouchableOpacity
                    key={cat.key}
                    style={[s.tab, selectedCategory === cat.key && s.tabActive]}
                    onPress={() => setSelectedCategory(cat.key)}
                    activeOpacity={0.7}
                  >
                    <Text style={[s.tabLabel, selectedCategory === cat.key && s.tabLabelActive]}>{cat.label}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>

              {/* Count */}
              <Text style={s.countText}>
                {filteredPredictions?.length || 0} predictions
              </Text>
            </>
          }
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />}
          showsVerticalScrollIndicator={false}
        />
      </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16, padding: theme.spacing.xl },
  loadingTitle: { fontSize: theme.typography.sizes.lg, fontWeight: '600', color: theme.colors.text.primary, textAlign: 'center' },
  loadingSubtitle: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary, textAlign: 'center' },
  connectionStatus: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: theme.spacing.sm },
  statusDot: { width: 8, height: 8, borderRadius: 4, marginRight: theme.spacing.xs },
  statusText: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, fontWeight: '600' },
  listContent: { padding: theme.spacing.md, gap: theme.spacing.md },

  // ── Movers ────────────────────────────────────────────────
  moversContainer: { marginBottom: theme.spacing.md },
  moversTitle: { fontSize: theme.typography.sizes.xl, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.md },
  moversSectionTitle: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.secondary, marginBottom: theme.spacing.sm, marginTop: theme.spacing.sm },
  moversRow: { gap: theme.spacing.sm, paddingRight: theme.spacing.md },
  moverCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    width: 130,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  moverSymbol: { fontSize: theme.typography.sizes.sm, fontWeight: '700', color: theme.colors.text.primary },
  moverName: { fontSize: 10, color: theme.colors.text.secondary, textAlign: 'center' },
  moverPrice: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.primary, marginTop: 2 },
  moverBadge: { paddingHorizontal: theme.spacing.sm, paddingVertical: 2, borderRadius: theme.borderRadius.md, marginTop: 2 },
  moverChange: { fontSize: theme.typography.sizes.xs, fontWeight: '700' },

  // ── Category Tabs ─────────────────────────────────────────
  tabsContainer: { marginBottom: theme.spacing.md },
  tabsContent: { gap: theme.spacing.xs },
  tab: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.full,
    backgroundColor: 'transparent',
    borderWidth: 1, borderColor: theme.colors.ui.border,
  },
  tabActive: { backgroundColor: theme.colors.brand.primary, borderColor: theme.colors.brand.primary },
  tabLabel: { fontSize: theme.typography.sizes.xs, fontWeight: '600', color: theme.colors.text.secondary },
  tabLabelActive: { color: '#FFFFFF' },
  searchWrap: { marginBottom: theme.spacing.sm },
  searchInput: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.full,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    color: theme.colors.text.primary,
    fontSize: theme.typography.sizes.body,
  },
  perfLink: { alignSelf: 'flex-end', marginBottom: theme.spacing.sm },
  perfLinkText: { fontSize: theme.typography.sizes.sm, color: theme.colors.brand.primary, fontWeight: '600' },
  accuracyBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  accuracyText: { fontSize: 10, fontWeight: '700' },
  modelBadge: {
    backgroundColor: '#1d4ed820',
    borderColor: '#1d4ed850',
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  modelBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#1d4ed8',
  },
  ensembleBadge: {
    backgroundColor: '#0f172a12',
    borderColor: '#0f172a20',
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  ensembleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.text.secondary,
  },
  histBadge: {
    backgroundColor: '#16a34a22',
    borderColor: '#16a34a55',
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    marginBottom: theme.spacing.sm,
    alignSelf: 'flex-start',
  },
  histBadgeText: {
    color: '#166534',
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
  },
  countText: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, marginBottom: theme.spacing.sm },

  // ── Prediction Cards ──────────────────────────────────────
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.sm },
  assetContainer: { flex: 1 },
  assetName: { fontSize: theme.typography.sizes.h3, fontWeight: '700', color: theme.colors.text.primary, marginBottom: 2 },
  symbolBadge: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, fontFamily: theme.typography.fontFamily.mono },
  actionBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm, borderRadius: theme.borderRadius.lg, gap: theme.spacing.xs },
  actionIcon: { fontSize: 16 },
  actionText: { fontSize: theme.typography.sizes.sm, fontWeight: '600' },
  priceContainer: { marginBottom: theme.spacing.sm, gap: theme.spacing.xs },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  priceLabel: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  priceValue: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.primary },
  confidenceContainer: { marginBottom: theme.spacing.sm },
  confidenceHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.xs },
  confidenceLabel: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  confidenceValue: { fontSize: theme.typography.sizes.sm, fontWeight: '700', color: theme.colors.text.primary },
  reasoning: { fontSize: theme.typography.sizes.small, color: theme.colors.text.tertiary, lineHeight: 16, marginBottom: theme.spacing.sm },
  mtfRow: {
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: '#00000010',
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  mtfText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
    fontFamily: theme.typography.fontFamily.mono,
  },
  mtfStrength: {
    marginTop: 2,
    fontSize: 10,
    fontWeight: '600',
  },
  onchainRow: {
    marginBottom: theme.spacing.sm,
  },
  onchainText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
  },
  viewDetails: { fontSize: theme.typography.sizes.sm, color: theme.colors.brand.primary, fontWeight: '600', textAlign: 'right' },
});

