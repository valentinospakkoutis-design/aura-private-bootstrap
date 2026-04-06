import React, { useState, useEffect, useCallback, useRef } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, StyleSheet, Alert, RefreshControl } from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { theme } from '../mobile/src/constants/theme';

interface RLModel {
  symbol: string;
  val_sharpe: number;
  val_return_pct: number;
  total_trades: number;
  episode: number;
  trained_at: string;
}

export default function RLPerformanceScreen() {
  const [batchData, setBatchData] = useState<any>(null);
  const [models, setModels] = useState<RLModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [training, setTraining] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [batch, status] = await Promise.all([
        api.getRLBatchPredictions(),
        api.getRLStatus(),
      ]);
      setBatchData(batch);
      setModels([...(status.models ?? [])].sort((a: RLModel, b: RLModel) => (b.val_sharpe || 0) - (a.val_sharpe || 0)));
    } catch (e) {
      console.error('RL fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 60000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchData]);

  const handleTrainAll = useCallback(() => {
    Alert.alert('Εκπαίδευση RL Agent', 'Θα εκπαιδευτούν τα υπόλοιπα symbols (~4 ώρες). Συνεχίζεις;', [
      { text: 'Ακύρωση', style: 'cancel' },
      {
        text: 'Εκκίνηση', onPress: async () => {
          setTraining(true);
          try {
            await api.trainAllRL();
            Alert.alert('✅', 'Εκπαίδευση ξεκίνησε!');
            setTimeout(fetchData, 3000);
          } catch { Alert.alert('❌', 'Σφάλμα εκκίνησης'); }
          finally { setTraining(false); }
        }
      }
    ]);
  }, [fetchData]);

  const avgSharpe = models.length > 0
    ? (models.reduce((s, m) => s + (m.val_sharpe ?? 0), 0) / models.length).toFixed(2)
    : '0.00';

  const sharpeColor = (v: number) => v >= 2 ? '#22c55e' : v >= 1 ? '#f59e0b' : '#ef4444';

  if (loading) {
    return (
      <View style={st.centered}>
        <ActivityIndicator size="large" color={theme.colors.brand.primary} />
        <Text style={st.loadingText}>Φόρτωση RL Models...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={st.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} />}>
      {/* Summary */}
      <View style={st.summaryCard}>
        <Text style={st.summaryTitle}>🤖 RL Agent Performance</Text>
        <Text style={st.stat}>{batchData?.trained_count ?? 0}/{batchData?.total_count ?? 34} models εκπαιδευμένα</Text>
        <Text style={st.stat}>Μέσο Sharpe: {avgSharpe}</Text>
        {models.length > 0 && <Text style={st.best}>🏆 {models[0].symbol} — Sharpe {(models[0].val_sharpe ?? 0).toFixed(2)}</Text>}
        {batchData?.is_training ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 8 }}>
            <ActivityIndicator size="small" color="#f59e0b" />
            <Text style={{ color: '#f59e0b', fontWeight: '600', marginLeft: 6 }}>Εκπαίδευση σε εξέλιξη...</Text>
          </View>
        ) : <Text style={{ color: '#22c55e', fontWeight: '600', marginTop: 8 }}>✅ Ολοκληρώθηκε</Text>}
      </View>

      {/* Trained */}
      <Text style={st.section}>📊 Εκπαιδευμένα Models</Text>
      {models.map((m, i) => {
        const pred = batchData?.predictions?.[m.symbol];
        const ac = pred?.action === 'BUY' ? '#22c55e' : pred?.action === 'SELL' ? '#ef4444' : '#9ca3af';
        return (
          <View key={m.symbol} style={st.card}>
            <View style={st.cardHeader}>
              <View style={st.rank}><Text style={st.rankText}>#{i + 1}</Text></View>
              <Text style={st.sym}>{m.symbol}</Text>
              <Text style={[st.sharpe, { color: sharpeColor(m.val_sharpe ?? 0) }]}>Sharpe {(m.val_sharpe ?? 0).toFixed(2)}</Text>
            </View>
            <Text style={st.stats}>Return: {(m.val_return_pct ?? 0).toFixed(1)}%  ·  Trades: {m.total_trades}  ·  Ep: {m.episode}</Text>
            {pred && (
              <View style={[st.actionBadge, { backgroundColor: pred.action === 'BUY' ? '#dcfce7' : pred.action === 'SELL' ? '#fee2e2' : '#f3f4f6' }]}>
                <Text style={{ color: ac, fontWeight: '700', fontSize: 12 }}>🤖 {pred.action}  ·  Confidence: {((pred.confidence || 0) * 100).toFixed(0)}%</Text>
              </View>
            )}
          </View>
        );
      })}

      {/* Pending */}
      {(batchData?.pending_symbols?.length ?? 0) > 0 && (
        <>
          <Text style={st.section}>⏳ Εκκρεμή ({batchData.pending_symbols.length})</Text>
          <View style={st.pendingGrid}>
            {batchData.pending_symbols.map((s: string) => (
              <View key={s} style={st.chip}><Text style={st.chipText}>{s}</Text></View>
            ))}
          </View>
        </>
      )}

      {/* Train button */}
      {batchData && batchData.trained_count < batchData.total_count && !batchData.is_training && (
        <TouchableOpacity style={[st.trainBtn, training && { opacity: 0.5 }]} onPress={handleTrainAll} disabled={training}>
          <Text style={st.trainBtnText}>{training ? '⏳ Εκκίνηση...' : '🚀 Εκπαίδευση Νέων Symbols'}</Text>
        </TouchableOpacity>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  loadingText: { marginTop: 12, color: theme.colors.text.secondary, fontSize: 14 },
  summaryCard: {
    margin: 16, padding: 16, backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: 16, shadowColor: '#000', shadowOpacity: 0.08,
    shadowOffset: { width: 0, height: 2 }, shadowRadius: 8, elevation: 3,
  },
  summaryTitle: { fontSize: 18, fontWeight: '700', color: theme.colors.text.primary, marginBottom: 8 },
  stat: { fontSize: 14, color: theme.colors.text.secondary, marginBottom: 4 },
  best: { fontSize: 14, fontWeight: '600', color: theme.colors.brand.primary, marginTop: 4 },
  section: { fontSize: 15, fontWeight: '700', color: theme.colors.text.primary, marginHorizontal: 16, marginTop: 16, marginBottom: 8 },
  card: {
    marginHorizontal: 16, marginBottom: 8, padding: 14, backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: 12, shadowColor: '#000', shadowOpacity: 0.05,
    shadowOffset: { width: 0, height: 1 }, shadowRadius: 4, elevation: 2,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  rank: { backgroundColor: theme.colors.brand.primary, borderRadius: 12, paddingHorizontal: 8, paddingVertical: 2, marginRight: 8 },
  rankText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  sym: { fontSize: 15, fontWeight: '700', color: theme.colors.text.primary, flex: 1 },
  sharpe: { fontSize: 14, fontWeight: '700' },
  stats: { fontSize: 12, color: theme.colors.text.secondary, marginBottom: 6 },
  actionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, alignSelf: 'flex-start' },
  pendingGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12 },
  chip: { backgroundColor: theme.colors.ui.cardBackground, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, margin: 4, borderWidth: 1, borderColor: theme.colors.ui.border },
  chipText: { fontSize: 12, color: theme.colors.text.secondary },
  trainBtn: { margin: 16, backgroundColor: theme.colors.brand.primary, padding: 16, borderRadius: 12, alignItems: 'center' },
  trainBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
