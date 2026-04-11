import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, View, RefreshControl } from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { theme } from '../mobile/src/constants/theme';
import { useLanguage } from '../mobile/src/hooks/useLanguage';

type BandStats = { accuracy: number; count: number };

type AccuracySummary = {
  overall_accuracy_7d: number;
  total_evaluated: number;
  by_confidence_band: Record<string, BandStats>;
  best_assets: string[];
  worst_assets: string[];
};

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}

export default function AIAccuracyScreen() {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState<AccuracySummary | null>(null);

  const load = async () => {
    try {
      const summary = await api.getAIPredictionAccuracy();
      setData(summary);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const overall = useMemo(() => clamp(Number(data?.overall_accuracy_7d || 0), 0, 100), [data]);

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={s.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={s.title}>{t('aiAccuracyTitle')}</Text>

      <View style={s.card}>
        <Text style={s.cardTitle}>{t('overallAccuracy7d')}</Text>
        <Text style={s.bigValue}>{overall.toFixed(1)}%</Text>
        <View style={s.progressTrack}>
          <View style={[s.progressFill, { width: `${overall}%` }]} />
        </View>
        <Text style={s.meta}>{t('evaluatedPredictionsCount', { value: String(data?.total_evaluated || 0) })}</Text>
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>{t('confidenceBreakdown')}</Text>
        {['90-100', '80-90', '70-80'].map((band) => {
          const row = data?.by_confidence_band?.[band] || { accuracy: 0, count: 0 };
          return (
            <View key={band} style={s.row}>
              <Text style={s.rowLabel}>{band}</Text>
              <Text style={s.rowValue}>{row.accuracy.toFixed(1)}%</Text>
              <Text style={s.rowCount}>({row.count})</Text>
            </View>
          );
        })}
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>{t('bestAssets')}</Text>
        {data?.best_assets?.length ? data.best_assets.map((a) => <Text key={a} style={s.assetGood}>• {a}</Text>) : <Text style={s.meta}>-</Text>}
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>{t('worstAssets')}</Text>
        {data?.worst_assets?.length ? data.worst_assets.map((a) => <Text key={a} style={s.assetBad}>• {a}</Text>) : <Text style={s.meta}>-</Text>}
      </View>

      {loading && <Text style={s.meta}>{t('loading')}</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  content: { padding: theme.spacing.md, gap: theme.spacing.md, paddingBottom: theme.spacing.xl * 2 },
  title: { fontSize: 26, fontWeight: '700', color: theme.colors.text.primary },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  cardTitle: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary, marginBottom: theme.spacing.sm },
  bigValue: { fontSize: 36, fontWeight: '800', color: '#166534', marginBottom: theme.spacing.sm },
  progressTrack: { width: '100%', height: 14, borderRadius: 999, backgroundColor: '#DCFCE7', overflow: 'hidden' },
  progressFill: { height: 14, borderRadius: 999, backgroundColor: '#16A34A' },
  meta: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary, marginTop: theme.spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.xs },
  rowLabel: { flex: 1, fontSize: theme.typography.sizes.md, color: theme.colors.text.primary, fontWeight: '600' },
  rowValue: { width: 70, textAlign: 'right', fontSize: theme.typography.sizes.md, color: '#166534', fontWeight: '700' },
  rowCount: { width: 60, textAlign: 'right', fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  assetGood: { color: '#15803D', fontSize: theme.typography.sizes.md, marginTop: theme.spacing.xs },
  assetBad: { color: '#B91C1C', fontSize: theme.typography.sizes.md, marginTop: theme.spacing.xs },
});
