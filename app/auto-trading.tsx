import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, Switch, RefreshControl, Alert } from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { Button } from '../mobile/src/components/Button';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { theme } from '../mobile/src/constants/theme';

interface AutoTradingStatus {
  enabled: boolean;
  is_running: boolean;
  mode: string;
  config: {
    confidence_threshold: number;
    fixed_order_value_usd: number;
    stop_loss_pct: number;
    take_profit_pct: number;
    max_positions: number;
    max_order_value_usd: number;
  };
  open_positions_count: number;
  positions: any[];
  total_auto_trades: number;
  last_run: string | null;
  next_run_in_seconds: number;
  recent_log: Array<{ type: string; message: string; timestamp: string }>;
}

export default function AutoTradingScreen() {
  const { showToast } = useAppStore();
  const { t } = useLanguage();
  const [status, setStatus] = useState<AutoTradingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const data = await api.getAutoTradingStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to load auto trading status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  }, [loadStatus]);

  const doToggle = useCallback(async (value: boolean) => {
    setToggling(true);
    try {
      if (value) {
        await api.enableAutoTrading();
        showToast('Auto Trading enabled', 'success');
      } else {
        await api.disableAutoTrading();
        showToast('Auto Trading disabled', 'success');
      }
      await loadStatus();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed';
      showToast(msg, 'error');
    } finally {
      setToggling(false);
    }
  }, [showToast, loadStatus]);

  const handleToggle = useCallback((value: boolean) => {
    if (value) {
      Alert.alert(
        t('enableAutoTrading'),
        t('enableAutoTradingMsg'),
        [
          { text: t('cancel'), style: 'cancel' },
          { text: t('enable'), style: 'destructive', onPress: () => doToggle(true) },
        ]
      );
    } else {
      doToggle(false);
    }
  }, [doToggle]);

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.content}>
          <SkeletonCard />
          <SkeletonCard />
        </View>
      </View>
    );
  }

  const isEnabled = status?.enabled ?? false;
  const config = status?.config;
  const positions = status?.positions ?? [];
  const logs = status?.recent_log ?? [];
  const mode = status?.mode ?? 'paper';

  return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.brand.primary} />}
      >
        {/* Warning Banner */}
        <View style={styles.warningBanner}>
          <Text style={styles.warningIcon}>&#9888;&#65039;</Text>
          <Text style={styles.warningText}>
            {t('autoTradingWarning')}
          </Text>
        </View>

        {/* Toggle Card */}
        <View style={styles.card}>
          <View style={styles.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{t('autoTrading')}</Text>
              <Text style={styles.cardSubtitle}>
                {isEnabled ? `${t('active')} — ${t('monitoringPredictions')}` : `${t('disabled')} — ${t('noOrdersPlaced')}`}
              </Text>
            </View>
            <Switch
              value={isEnabled}
              onValueChange={handleToggle}
              disabled={toggling}
              trackColor={{ false: theme.colors.ui.border, true: theme.colors.semantic.success + '80' }}
              thumbColor={isEnabled ? theme.colors.semantic.success : '#f4f3f4'}
            />
          </View>
          <View style={[styles.modeBadge, { backgroundColor: mode === 'live' ? theme.colors.semantic.error + '20' : theme.colors.semantic.success + '20' }]}>
            <Text style={[styles.modeBadgeText, { color: mode === 'live' ? theme.colors.semantic.error : theme.colors.semantic.success }]}>
              {mode === 'live' ? `🔴 ${t('liveMode')}` : `🟢 ${t('paperMode')}`}
            </Text>
          </View>
          {status?.last_run && (
            <Text style={styles.statusMeta}>
              Last run: {new Date(status.last_run).toLocaleTimeString('el-GR')} | Trades: {status.total_auto_trades} | Next in: {status.next_run_in_seconds}s
            </Text>
          )}
        </View>

        {/* Config Card */}
        {config && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('configuration')}</Text>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('minConfidence')}</Text>
              <Text style={styles.configValue}>{(config.confidence_threshold * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('positionSize')}</Text>
              <Text style={styles.configValue}>Fixed ${config.fixed_order_value_usd ?? 10} per trade</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('stopLoss')}</Text>
              <Text style={styles.configValue}>{(config.stop_loss_pct * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('takeProfit')}</Text>
              <Text style={styles.configValue}>{((config.take_profit_pct || 0.05) * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('maxPositions')}</Text>
              <Text style={styles.configValue}>{config.max_positions}</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('maxOrderValue')}</Text>
              <Text style={styles.configValue}>${config.max_order_value_usd}</Text>
            </View>
          </View>
        )}

        {/* Open Positions */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Open Positions ({positions.length})</Text>
          {positions.length === 0 ? (
            <Text style={styles.emptyText}>No auto-opened positions</Text>
          ) : (
            positions.map((pos, i) => (
              <View key={i} style={styles.positionRow}>
                <View>
                  <Text style={styles.positionSymbol}>{pos.symbol}</Text>
                  <Text style={styles.positionDetail}>
                    {pos.side} {pos.quantity} @ ${pos.entry_price?.toFixed(2)}
                  </Text>
                </View>
                <View style={{ alignItems: 'flex-end' as const }}>
                  <Text style={[styles.positionDetail, { color: theme.colors.market.bullish }]}>
                    TP: ${pos.target_price?.toFixed(2)}
                  </Text>
                  <Text style={[styles.positionDetail, { color: theme.colors.market.bearish }]}>
                    SL: ${pos.stop_loss?.toFixed(2)}
                  </Text>
                </View>
              </View>
            ))
          )}
        </View>

        {/* Activity Log */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('activityLog')}</Text>
          {logs.length === 0 ? (
            <Text style={styles.emptyText}>No activity yet</Text>
          ) : (
            logs.slice().reverse().slice(0, 10).map((entry, i) => (
              <View key={i} style={styles.logEntry}>
                <Text style={styles.logType}>{entry.type}</Text>
                <Text style={styles.logMessage}>{entry.message}</Text>
                <Text style={styles.logTime}>
                  {new Date(entry.timestamp).toLocaleTimeString('el-GR')}
                </Text>
              </View>
            ))
          )}
        </View>

        <View style={{ height: theme.spacing.xl * 2 }} />
      </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  content: { padding: theme.spacing.md },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.semantic.error + '15',
    borderWidth: 1,
    borderColor: theme.colors.semantic.error,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
  },
  warningIcon: { fontSize: 28, marginRight: theme.spacing.md },
  warningText: {
    flex: 1,
    fontSize: theme.typography.sizes.md,
    fontWeight: '600' as const,
    color: theme.colors.semantic.error,
    lineHeight: 22,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
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
    fontWeight: '700' as const,
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  cardSubtitle: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  configRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  configLabel: { fontSize: theme.typography.sizes.md, color: theme.colors.text.secondary },
  configValue: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600' as const,
    fontFamily: theme.typography.fontFamily.mono,
    color: theme.colors.text.primary,
  },
  emptyText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    textAlign: 'center' as const,
    paddingVertical: theme.spacing.md,
  },
  positionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  positionSymbol: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700' as const,
    color: theme.colors.text.primary,
  },
  positionDetail: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  logEntry: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing.xs,
    gap: theme.spacing.sm,
  },
  logType: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700' as const,
    color: theme.colors.brand.primary,
    minWidth: 80,
  },
  logMessage: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    flex: 1,
  },
  logTime: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  modeBadge: {
    alignSelf: 'flex-start' as const,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
    marginTop: theme.spacing.sm,
  },
  modeBadgeText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700' as const,
  },
  statusMeta: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.sm,
  },
});
