import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useAppStore } from '../mobile/src/stores/appStore';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';

interface ModelInfo {
  symbol: string;
  version: string;
  accuracy: number;
  precision: number;
  recall: number;
  training_samples: number;
  trained_at: string | null;
}

export default function ModelPerformanceScreen() {
  const { showToast } = useAppStore();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [training, setTraining] = useState(false);

  useEffect(() => { loadModels(); }, []);

  const loadModels = async () => {
    try {
      const data = await api.getModelPerformance();
      setModels(data?.models || []);
    } catch (err) {
      console.error('Failed to load models:', err);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadModels();
    setRefreshing(false);
  };

  const handleRetrain = async () => {
    setTraining(true);
    showToast('Εκπαίδευση ξεκίνησε... (~30 λεπτά)', 'success');
    try {
      await api.triggerFullPipeline();
    } catch (err) {
      showToast('Αποτυχία εκκίνησης εκπαίδευσης', 'error');
    }
    // Don't un-disable — training takes a long time
  };

  const getAccuracyColor = (acc: number) => {
    if (acc >= 0.55) return theme.colors.market.bullish;
    if (acc >= 0.50) return '#F59E0B';
    return theme.colors.market.bearish;
  };

  if (loading) {
    return (
      <PageTransition type="fade">
        <View style={s.centered}>
          <ActivityIndicator size="large" color={theme.colors.brand.primary} />
          <Text style={s.loadingText}>Φόρτωση μοντέλων...</Text>
        </View>
      </PageTransition>
    );
  }

  const sorted = [...models].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0));
  const totalModels = models.length;
  const avgAccuracy = totalModels > 0 ? models.reduce((sum, m) => sum + (m.accuracy || 0), 0) / totalModels : 0;
  const bestModel = sorted[0];
  const lastTrained = models.reduce((latest, m) => {
    if (!m.trained_at) return latest;
    return m.trained_at > (latest || '') ? m.trained_at : latest;
  }, '' as string);

  return (
    <PageTransition type="slideUp">
      <ScrollView
        style={s.container}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />}
      >
        {/* Summary Card */}
        <AnimatedCard delay={0} animationType="slideUp">
          <Text style={s.sectionTitle}>📊 Σύνοψη AI Μοντέλων</Text>
          <View style={s.summaryGrid}>
            <View style={s.summaryItem}>
              <Text style={s.summaryValue}>{totalModels}</Text>
              <Text style={s.summaryLabel}>Μοντέλα</Text>
            </View>
            <View style={s.summaryItem}>
              <Text style={[s.summaryValue, { color: getAccuracyColor(avgAccuracy) }]}>
                {(avgAccuracy * 100).toFixed(1)}%
              </Text>
              <Text style={s.summaryLabel}>Μέση Ακρίβεια</Text>
            </View>
            <View style={s.summaryItem}>
              <Text style={s.summaryValue}>{bestModel?.symbol || '-'}</Text>
              <Text style={s.summaryLabel}>Κορυφαίο</Text>
            </View>
          </View>
          {lastTrained ? (
            <Text style={s.lastTrained}>
              Τελευταία εκπαίδευση: {new Date(lastTrained).toLocaleDateString('el-GR')}
            </Text>
          ) : null}
        </AnimatedCard>

        {/* Model List */}
        <Text style={s.listTitle}>🏆 Κατάταξη Μοντέλων</Text>

        {sorted.length === 0 ? (
          <AnimatedCard delay={100} animationType="fade">
            <Text style={s.emptyText}>Δεν υπάρχουν εκπαιδευμένα μοντέλα ακόμα</Text>
          </AnimatedCard>
        ) : (
          sorted.map((model, index) => {
            const acc = model.accuracy || 0;
            const color = getAccuracyColor(acc);
            return (
              <AnimatedCard key={model.symbol} delay={100 + index * 30} animationType="slideUp" style={s.modelCard}>
                <View style={s.modelHeader}>
                  <View>
                    <Text style={s.modelSymbol}>{model.symbol}</Text>
                    <Text style={s.modelVersion}>{model.version}</Text>
                  </View>
                  <View style={[s.rankBadge, { backgroundColor: color + '20' }]}>
                    <Text style={[s.rankText, { color }]}>#{index + 1}</Text>
                  </View>
                </View>

                {/* Accuracy bar */}
                <View style={s.metricRow}>
                  <Text style={s.metricLabel}>Ακρίβεια</Text>
                  <Text style={[s.metricValue, { color }]}>{(acc * 100).toFixed(1)}%</Text>
                </View>
                <AnimatedProgressBar progress={acc} color={color} height={8} animated />

                {/* Precision & Samples */}
                <View style={s.metricGrid}>
                  <View style={s.metricGridItem}>
                    <Text style={s.metricGridValue}>{((model.precision || 0) * 100).toFixed(1)}%</Text>
                    <Text style={s.metricGridLabel}>Precision</Text>
                  </View>
                  <View style={s.metricGridItem}>
                    <Text style={s.metricGridValue}>{((model.recall || 0) * 100).toFixed(1)}%</Text>
                    <Text style={s.metricGridLabel}>Recall</Text>
                  </View>
                  <View style={s.metricGridItem}>
                    <Text style={s.metricGridValue}>{model.training_samples || 0}</Text>
                    <Text style={s.metricGridLabel}>Samples</Text>
                  </View>
                </View>
              </AnimatedCard>
            );
          })
        )}

        {/* Retrain Button */}
        <TouchableOpacity
          style={[s.retrainButton, training && s.retrainButtonDisabled]}
          onPress={handleRetrain}
          disabled={training}
          activeOpacity={0.7}
        >
          <Text style={s.retrainText}>{training ? '⏳ Εκπαίδευση σε εξέλιξη...' : '🔄 Εκπαίδευση Μοντέλων'}</Text>
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
  summaryGrid: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.md },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryValue: { fontSize: theme.typography.sizes['2xl'], fontWeight: '700', color: theme.colors.text.primary },
  summaryLabel: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, marginTop: 2 },
  lastTrained: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary, textAlign: 'center' },

  listTitle: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary, marginTop: theme.spacing.lg, marginBottom: theme.spacing.md },
  emptyText: { fontSize: theme.typography.sizes.md, color: theme.colors.text.secondary, textAlign: 'center', padding: theme.spacing.xl },

  modelCard: { marginBottom: theme.spacing.sm },
  modelHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.sm },
  modelSymbol: { fontSize: theme.typography.sizes.lg, fontWeight: '700', color: theme.colors.text.primary },
  modelVersion: { fontSize: theme.typography.sizes.xs, color: theme.colors.text.secondary },
  rankBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  rankText: { fontSize: theme.typography.sizes.sm, fontWeight: '700' },

  metricRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, marginTop: theme.spacing.sm },
  metricLabel: { fontSize: theme.typography.sizes.sm, color: theme.colors.text.secondary },
  metricValue: { fontSize: theme.typography.sizes.md, fontWeight: '700' },

  metricGrid: { flexDirection: 'row', justifyContent: 'space-between', marginTop: theme.spacing.md, paddingTop: theme.spacing.sm, borderTopWidth: 1, borderTopColor: theme.colors.ui.border },
  metricGridItem: { alignItems: 'center', flex: 1 },
  metricGridValue: { fontSize: theme.typography.sizes.md, fontWeight: '600', color: theme.colors.text.primary },
  metricGridLabel: { fontSize: 10, color: theme.colors.text.secondary, marginTop: 2 },

  retrainButton: {
    backgroundColor: theme.colors.brand.primary, borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg, alignItems: 'center', marginTop: theme.spacing.xl,
  },
  retrainButtonDisabled: { backgroundColor: theme.colors.text.secondary, opacity: 0.6 },
  retrainText: { fontSize: theme.typography.sizes.md, fontWeight: '700', color: '#FFFFFF' },
});

