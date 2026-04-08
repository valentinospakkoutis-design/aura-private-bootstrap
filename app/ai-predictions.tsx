import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, ActivityIndicator, TouchableOpacity, ScrollView } from 'react-native';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { NoPredictions } from '../mobile/src/components/NoPredictions';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { useRouter } from 'expo-router';
import { usePriceUpdates } from '../mobile/src/hooks/useWebSocket';
import { useOfflineMode } from '../mobile/src/hooks/useOfflineMode';

interface Prediction {
  id: string;
  asset: string;
  symbol?: string;
  category?: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  price: number;
  targetPrice: number;
  timestamp: string;
  reasoning: string;
}

interface Mover {
  symbol: string;
  name: string;
  category: string;
  price: number;
  change_pct: number;
  confidence: number;
}

const CATEGORIES = [
  { key: 'all', label: 'Όλα', icon: '🌐' },
  { key: 'crypto', label: 'Crypto', icon: '₿' },
  { key: 'stocks', label: 'Μετοχές', icon: '📈' },
  { key: 'metals', label: 'Μέταλλα', icon: '🥇' },
  { key: 'bonds', label: 'Ομόλογα', icon: '📊' },
  { key: 'derivatives', label: 'Παράγωγα', icon: '🔮' },
  { key: 'fx', label: 'FX', icon: '💱' },
  { key: 'sentiment', label: 'VIX', icon: '😨' },
] as const;

export default function AIPredictionsScreen() {
  const router = useRouter();
  const { predictions, setPredictions } = useAppStore();
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [movers, setMovers] = useState<{ top_gainers: Mover[]; top_losers: Mover[]; top_volume: Mover[] } | null>(null);
  const [modelAccuracy, setModelAccuracy] = useState<Record<string, number>>({});
  const [rlData, setRlData] = useState<any>(null);
  const { isOfflineMode } = useOfflineMode();

  const {
    error,
    loading,
    execute: fetchPredictions,
  } = useApi((...args: any[]) => api.getPredictions(...args), { showLoading: false, showToast: false });

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
        api.getModelPerformance().then((data: any) => {
          const map: Record<string, number> = {};
          for (const m of data?.models || []) {
            if (m.symbol && m.accuracy != null) map[m.symbol] = m.accuracy;
          }
          setModelAccuracy(map);
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

  const filteredPredictions = selectedCategory === 'all'
    ? predictions
    : predictions?.filter((p: any) => p.category === selectedCategory);

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
  const renderPredictionCard = ({ item, index }: { item: Prediction; index: number }) => {
    const acc = modelAccuracy[item.symbol || ''] ?? null;
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
            {acc !== null && (
              <View style={[s.accuracyBadge, { backgroundColor: getAccuracyColor(acc) + '20' }]}>
                <Text style={[s.accuracyText, { color: getAccuracyColor(acc) }]}>
                  🎯 {(acc * 100).toFixed(1)}%
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
            ${item.targetPrice < 1 ? item.targetPrice?.toFixed(4) : item.targetPrice?.toFixed(2)}
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

      <Text style={s.reasoning} numberOfLines={2}>{item.reasoning}</Text>

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

      <Text style={s.viewDetails}>Δες Ανάλυση →</Text>
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

              {/* Model links */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.sm }}>
                <TouchableOpacity style={s.perfLink} onPress={() => router.push('/model-performance')}>
                  <Text style={s.perfLinkText}>🎯 Μοντέλα →</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.perfLink, { backgroundColor: '#6366f120', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 }]} onPress={() => router.push('/rl-performance')}>
                  <Text style={[s.perfLinkText, { color: '#6366f1' }]}>🤖 RL Agent →</Text>
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
                    <Text style={s.tabIcon}>{cat.icon}</Text>
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
    borderRadius: theme.borderRadius.large,
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
  moverBadge: { paddingHorizontal: theme.spacing.sm, paddingVertical: 2, borderRadius: theme.borderRadius.medium, marginTop: 2 },
  moverChange: { fontSize: theme.typography.sizes.xs, fontWeight: '700' },

  // ── Category Tabs ─────────────────────────────────────────
  tabsContainer: { marginBottom: theme.spacing.md },
  tabsContent: { gap: theme.spacing.xs },
  tab: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm,
    borderRadius: 20,
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1, borderColor: theme.colors.ui.border,
    gap: 4,
  },
  tabActive: { backgroundColor: theme.colors.brand.primary, borderColor: theme.colors.brand.primary },
  tabIcon: { fontSize: 14 },
  tabLabel: { fontSize: theme.typography.sizes.xs, fontWeight: '600', color: theme.colors.text.secondary },
  tabLabelActive: { color: '#FFFFFF' },
  perfLink: { alignSelf: 'flex-end', marginBottom: theme.spacing.sm },
  perfLinkText: { fontSize: theme.typography.sizes.sm, color: theme.colors.brand.primary, fontWeight: '600' },
  accuracyBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  accuracyText: { fontSize: 10, fontWeight: '700' },
  countText: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, marginBottom: theme.spacing.sm },

  // ── Prediction Cards ──────────────────────────────────────
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 3,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.md },
  assetContainer: { flex: 1 },
  assetName: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary, marginBottom: 2 },
  symbolBadge: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, fontFamily: theme.typography.fontFamily.mono },
  actionBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm, borderRadius: theme.borderRadius.large, gap: theme.spacing.xs },
  actionIcon: { fontSize: 16 },
  actionText: { fontSize: theme.typography.sizes.sm, fontWeight: '600' },
  priceContainer: { marginBottom: theme.spacing.md, gap: theme.spacing.xs },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  priceLabel: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  priceValue: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.primary },
  confidenceContainer: { marginBottom: theme.spacing.md },
  confidenceHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.xs },
  confidenceLabel: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  confidenceValue: { fontSize: theme.typography.sizes.sm, fontWeight: '700', color: theme.colors.text.primary },
  reasoning: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary, lineHeight: 20, marginBottom: theme.spacing.md },
  viewDetails: { fontSize: theme.typography.sizes.sm, color: theme.colors.brand.primary, fontWeight: '600', textAlign: 'right' },
});
