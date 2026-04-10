import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useAppStore } from '../mobile/src/stores/appStore';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';

interface BacktestResult {
  symbol: string;
  total_return_pct: number;
  annual_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
  total_fees_paid: number;
  calmar_ratio: number;
}

interface Summary {
  total_symbols: number;
  avg_sharpe: number;
  avg_return_pct: number;
  avg_win_rate: number;
  avg_drawdown: number;
  best_symbol: string | null;
  worst_symbol: string | null;
}

export default function BacktestScreen() {
  const { showToast } = useAppStore();
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [resData, sumData] = await Promise.all([
        api.getBacktestResults().catch(() => ({ results: [] })),
        api.getBacktestSummary().catch(() => null),
      ]);
      setResults(resData?.results || []);
      setSummary(sumData);
    } catch (err) {
      console.error('Failed to load backtest data:', err);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleRunBacktest = async () => {
    setRunning(true);
    showToast('Backtest ξεκίνησε για όλα τα assets...', 'success');
    try {
      await api.runBacktestAll();
    } catch (err) {
      showToast('Αποτυχία εκκίνησης backtest', 'error');
    }
  };

  const getReturnColor = (val: number) => val >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish;
  const getSharpeColor = (val: number) => {
    if (val >= 1.0) return theme.colors.market.bullish;
    if (val >= 0.5) return '#F59E0B';
    return theme.colors.market.bearish;
  };

  const sorted = [...results].sort((a, b) => (b.sharpe_ratio || 0) - (a.sharpe_ratio || 0));

  if (loading) {
    return (
      <PageTransition type="fade">
        <View style={s.centered}>
          <ActivityIndicator size="large" color={theme.colors.brand.primary} />
          <Text style={s.loadingText}>Φόρτωση backtest...</Text>
        </View>
      </PageTransition>
    );
  }

  return (
    <PageTransition type="slideUp">
      <ScrollView
        style={s.container}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />}
      >
        {/* Summary */}
        {summary && summary.total_symbols > 0 ? (
          <AnimatedCard delay={0} animationType="slideUp">
            <Text style={s.sectionTitle}>📊 Portfolio Backtest</Text>
            <View style={s.summaryGrid}>
              <View style={s.summaryItem}>
                <Text style={[s.summaryValue, { color: getSharpeColor(summary.avg_sharpe) }]}>
                  {summary.avg_sharpe.toFixed(2)}
                </Text>
                <Text style={s.summaryLabel}>Sharpe Ratio</Text>
              </View>
              <View style={s.summaryItem}>
                <Text style={[s.summaryValue, { color: getReturnColor(summary.avg_return_pct) }]}>
                  {summary.avg_return_pct >= 0 ? '+' : ''}{summary.avg_return_pct.toFixed(1)}%
                </Text>
                <Text style={s.summaryLabel}>Μέση Απόδοση</Text>
              </View>
              <View style={s.summaryItem}>
                <Text style={s.summaryValue}>{summary.avg_win_rate.toFixed(0)}%</Text>
                <Text style={s.summaryLabel}>Win Rate</Text>
              </View>
              <View style={s.summaryItem}>
                <Text style={[s.summaryValue, { color: theme.colors.market.bearish }]}>
                  {summary.avg_drawdown.toFixed(1)}%
                </Text>
                <Text style={s.summaryLabel}>Drawdown</Text>
              </View>
            </View>
            {summary.best_symbol && (
              <Text style={s.bestWorst}>Best: {summary.best_symbol} | Worst: {summary.worst_symbol}</Text>
            )}
          </AnimatedCard>
        ) : (
          <AnimatedCard delay={0} animationType="fade">
            <View style={s.emptyContainer}>
              <Text style={s.emptyIcon}>📉</Text>
              <Text style={s.emptyTitle}>Δεν υπάρχουν backtest αποτελέσματα</Text>
              <Text style={s.emptySubtitle}>Πάτα "Εκτέλεση Backtest" για να ξεκινήσεις</Text>
            </View>
          </AnimatedCard>
        )}

        {/* Results List */}
        {sorted.length > 0 && (
          <Text style={s.listTitle}>🏆 Αποτελέσματα ανά Asset (κατά Sharpe)</Text>
        )}

        {sorted.map((item, index) => (
          <AnimatedCard key={item.symbol} delay={50 + index * 20} animationType="slideUp" style={s.resultCard}>
            <View style={s.resultHeader}>
              <View>
                <Text style={s.resultSymbol}>{item.symbol}</Text>
                <Text style={s.resultTrades}>{item.total_trades} trades</Text>
              </View>
              <View style={[s.returnBadge, { backgroundColor: getReturnColor(item.total_return_pct) + '20' }]}>
                <Text style={[s.returnText, { color: getReturnColor(item.total_return_pct) }]}>
                  {item.total_return_pct >= 0 ? '+' : ''}{item.total_return_pct.toFixed(1)}%
                </Text>
              </View>
            </View>

            <View style={s.metricsRow}>
              <View style={s.metricItem}>
                <Text style={[s.metricValue, { color: getSharpeColor(item.sharpe_ratio) }]}>
                  {item.sharpe_ratio.toFixed(2)}
                </Text>
                <Text style={s.metricLabel}>Sharpe</Text>
              </View>
              <View style={s.metricItem}>
                <Text style={s.metricValue}>{item.win_rate_pct.toFixed(0)}%</Text>
                <Text style={s.metricLabel}>Win Rate</Text>
              </View>
              <View style={s.metricItem}>
                <Text style={[s.metricValue, { color: theme.colors.market.bearish }]}>
                  {item.max_drawdown_pct.toFixed(1)}%
                </Text>
                <Text style={s.metricLabel}>Drawdown</Text>
              </View>
              <View style={s.metricItem}>
                <Text style={s.metricValue}>${item.total_fees_paid.toFixed(0)}</Text>
                <Text style={s.metricLabel}>Fees</Text>
              </View>
            </View>

            {/* Win Rate Progress Bar */}
            <View style={{ marginTop: 8 }}>
              <AnimatedProgressBar
                progress={item.win_rate_pct / 100}
                color={item.win_rate_pct >= 50 ? theme.colors.market.bullish : theme.colors.market.bearish}
                height={6}
                animated
              />
            </View>
          </AnimatedCard>
        ))}

        {/* Run Backtest Button */}
        <TouchableOpacity
          style={[s.runButton, running && s.runButtonDisabled]}
          onPress={handleRunBacktest}
          disabled={running}
          activeOpacity={0.7}
        >
          <Text style={s.runButtonText}>
            {running ? '⏳ Backtest σε εξέλιξη...' : '▶ Εκτέλεση Backtest'}
          </Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </PageTransition>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  content: { padding: theme.spacing.md },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: theme.typography.sizes.md, color: theme.colors.text.secondary },

  sectionTitle: { fontSize: theme.typography.sizes.xl, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.md },
  summaryGrid: { flexDirection: 'row', justifyContent: 'space-between' },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryValue: { fontSize: theme.typography.sizes.xl, fontWeight: '700', color: theme.colors.text.primary },
  summaryLabel: { fontSize: 10, color: theme.colors.text.secondary, marginTop: 2 },
  bestWorst: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, textAlign: 'center', marginTop: theme.spacing.md },

  emptyContainer: { alignItems: 'center', padding: theme.spacing.xl },
  emptyIcon: { fontSize: 48, marginBottom: theme.spacing.md },
  emptyTitle: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.xs },
  emptySubtitle: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },

  listTitle: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary, marginTop: theme.spacing.lg, marginBottom: theme.spacing.md },

  resultCard: { marginBottom: theme.spacing.sm },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.sm },
  resultSymbol: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary },
  resultTrades: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary },
  returnBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  returnText: { fontSize: theme.typography.sizes.sm, fontWeight: '700' },

  metricsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  metricItem: { alignItems: 'center', flex: 1 },
  metricValue: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.primary },
  metricLabel: { fontSize: 10, color: theme.colors.text.secondary, marginTop: 2 },

  runButton: {
    backgroundColor: theme.colors.brand.primary, borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg, alignItems: 'center', marginTop: theme.spacing.xl,
  },
  runButtonDisabled: { backgroundColor: theme.colors.text.secondary, opacity: 0.6 },
  runButtonText: { fontSize: theme.typography.sizes.md, fontWeight: '700', color: '#FFFFFF' },
});

