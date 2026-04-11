import React, { useEffect, useState, useCallback, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, Switch, RefreshControl, Alert, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { api } from '../mobile/src/services/apiClient';
import { SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { theme } from '../mobile/src/constants/theme';
import { getToken } from '../mobile/src/utils/tokenStorage';

interface AutoTradingStatus {
  enabled: boolean;
  is_running: boolean;
  mode: string;
  config: {
    confidence_threshold: number;
    fixed_order_value_usd: number;
    stop_loss_pct: number;
    take_profit_pct: number;
    trail_pct?: number;
    max_positions: number;
    max_order_value_usd: number;
    dca_enabled?: boolean;
  };
  open_positions_count: number;
  positions: Array<{
    symbol: string;
    side: string;
    quantity: number;
    entry_price: number;
    target_price?: number;
    stop_loss?: number;
    trailing_stop?: number;
    trailing_last_move?: string;
  }>;
  total_auto_trades: number;
  last_run: string | null;
  next_run_in_seconds: number;
  recent_log: Array<{ type: string; message: string; timestamp: string; data?: any }>;
}

interface DcaOrder {
  id: number;
  symbol: string;
  target_price: number;
  size_usd: number;
  status: 'pending' | 'executed' | 'cancelled';
  executed_at?: string | null;
  created_at?: string | null;
}

interface CircuitBreakerStatus {
  state: 'active' | 'paused';
  reason: string | null;
  resume_at: string | null;
  minutes_remaining: number;
}

type UiAuthorityMode = 'manual' | 'confirm-first' | 'semi-auto' | 'full-autopilot';
type BackendAutopilotMode = 'safe' | 'balanced' | 'aggressive';

interface ModeDefinition {
  mode: UiAuthorityMode;
  borderColor: string;
  riskColor: string;
  titleKey: string;
  descriptionKey: string;
  riskLabelKey: string;
  requiresConfirmation: boolean;
  autoExecutionAllowed: boolean;
  permissions: {
    alertsOnly: boolean;
    requiresConfirmation: boolean;
    autoExecutionAllowed: boolean;
    exitsManaged: boolean;
    positionResizeAllowed: boolean;
  };
}

const MODE_DEFINITIONS: ModeDefinition[] = [
  {
    mode: 'manual',
    borderColor: '#64748B',
    riskColor: '#64748B',
    titleKey: 'manual',
    descriptionKey: 'manualDesc',
    riskLabelKey: 'riskLow',
    requiresConfirmation: true,
    autoExecutionAllowed: false,
    permissions: {
      alertsOnly: true,
      requiresConfirmation: true,
      autoExecutionAllowed: false,
      exitsManaged: false,
      positionResizeAllowed: false,
    },
  },
  {
    mode: 'confirm-first',
    borderColor: '#0EA5E9',
    riskColor: '#0EA5E9',
    titleKey: 'confirmFirst',
    descriptionKey: 'confirmFirstDesc',
    riskLabelKey: 'riskModerate',
    requiresConfirmation: true,
    autoExecutionAllowed: false,
    permissions: {
      alertsOnly: false,
      requiresConfirmation: true,
      autoExecutionAllowed: false,
      exitsManaged: false,
      positionResizeAllowed: false,
    },
  },
  {
    mode: 'semi-auto',
    borderColor: '#1D4ED8',
    riskColor: '#1D4ED8',
    titleKey: 'semiAuto',
    descriptionKey: 'semiAutoDesc',
    riskLabelKey: 'riskHigh',
    requiresConfirmation: false,
    autoExecutionAllowed: true,
    permissions: {
      alertsOnly: false,
      requiresConfirmation: false,
      autoExecutionAllowed: true,
      exitsManaged: true,
      positionResizeAllowed: false,
    },
  },
  {
    mode: 'full-autopilot',
    borderColor: '#B91C1C',
    riskColor: '#B91C1C',
    titleKey: 'fullAutopilot',
    descriptionKey: 'fullAutopilotDesc',
    riskLabelKey: 'riskVeryHigh',
    requiresConfirmation: false,
    autoExecutionAllowed: true,
    permissions: {
      alertsOnly: false,
      requiresConfirmation: false,
      autoExecutionAllowed: true,
      exitsManaged: true,
      positionResizeAllowed: true,
    },
  },
];

const MODE_RANK: Record<UiAuthorityMode, number> = {
  manual: 0,
  'confirm-first': 1,
  'semi-auto': 2,
  'full-autopilot': 3,
};

function normalizeBackendMode(rawMode: any): UiAuthorityMode {
  const mode = String(rawMode || '').toLowerCase();

  if (mode === 'manual' || mode === 'confirm-first' || mode === 'semi-auto' || mode === 'full-autopilot') {
    return mode;
  }

  if (mode === 'safe') return 'confirm-first';
  if (mode === 'balanced') return 'semi-auto';
  if (mode === 'aggressive') return 'full-autopilot';

  return 'confirm-first';
}

function serializeUiModeToBackend(mode: UiAuthorityMode): BackendAutopilotMode {
  if (mode === 'semi-auto') return 'balanced';
  if (mode === 'full-autopilot') return 'aggressive';
  return 'safe';
}

export default function AutoTradingScreen() {
  const router = useRouter();
  const { showToast } = useAppStore();
  const { t, language } = useLanguage();
  const [status, setStatus] = useState<AutoTradingStatus | null>(null);
  const [circuitBreaker, setCircuitBreaker] = useState<CircuitBreakerStatus | null>(null);
  const [autopilotMode, setAutopilotMode] = useState<UiAuthorityMode>('confirm-first');
  const [dcaOrders, setDcaOrders] = useState<{ pending: DcaOrder[]; executed: DcaOrder[]; cancelled?: DcaOrder[] }>({ pending: [], executed: [] });
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [changingMode, setChangingMode] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const shownDcaPlanTsRef = useRef<string | null>(null);

  const handleAuthRequired = useCallback(async () => {
    showToast(t('sessionExpired'), 'error');
    router.replace('/login');
  }, [router, showToast, t]);

  const loadStatus = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) {
        await handleAuthRequired();
        return;
      }

      const [statusData, autopilotData, cbData, dcaData] = await Promise.all([
        api.getAutoTradingStatus(),
        api.getAutopilotMode().catch(() => null),
        api.getAutoTradingCircuitBreaker().catch(() => null),
        api.getDcaOrders().catch(() => ({ pending: [], executed: [], cancelled: [] })),
      ]);
      setStatus(statusData);
      setCircuitBreaker(cbData);
      setDcaOrders(dcaData || { pending: [], executed: [] });
      const backendMode = autopilotData?.current_mode || autopilotData?.mode;
      if (backendMode) {
        setAutopilotMode(normalizeBackendMode(backendMode));
      }
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.statusCode === 401) {
        await handleAuthRequired();
        return;
      }
      console.error('Failed to load auto trading status:', err);
    } finally {
      setLoading(false);
    }
  }, [handleAuthRequired]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const resetCircuitBreaker = useCallback(() => {
    Alert.alert(
      t('circuitBreakerResetConfirmTitle'),
      t('circuitBreakerResetConfirmBody'),
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('circuitBreakerReset'),
          style: 'destructive',
          onPress: async () => {
            try {
              await api.resetAutoTradingCircuitBreaker();
              showToast(t('circuitBreakerResetSuccess'), 'success');
              await loadStatus();
            } catch (err: any) {
              const msg = err?.response?.data?.detail || err?.message || t('autopilotActionFailed');
              showToast(msg, 'error');
            }
          },
        },
      ]
    );
  }, [loadStatus, showToast, t]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  }, [loadStatus]);

  const showAchievementToasts = useCallback((earned: any[]) => {
    if (!Array.isArray(earned)) return;
    for (const a of earned) {
      const title = language === 'el' ? (a?.title_el || a?.title_en) : (a?.title_en || a?.title_el);
      if (title) {
        showToast(`🏆 ${title}`, 'success');
      }
    }
  }, [showToast, language]);

  const doToggle = useCallback(async (value: boolean) => {
    setToggling(true);
    try {
      const token = await getToken();
      if (!token) {
        await handleAuthRequired();
        return;
      }

      if (value) {
        const res = await api.enableAutoTrading();
        showToast(t('autopilotEnableSuccess'), 'success');
        showAchievementToasts(res?.achievements_earned || []);
      } else {
        await api.disableAutoTrading();
        showToast(t('autopilotDisableSuccess'), 'success');
      }
      await loadStatus();
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.statusCode === 401) {
        await handleAuthRequired();
        return;
      }
      const msg = err?.response?.data?.detail || err?.message || t('autopilotActionFailed');
      showToast(msg, 'error');
    } finally {
      setToggling(false);
    }
  }, [handleAuthRequired, showToast, loadStatus, t, showAchievementToasts]);

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

  const toggleDcaMode = useCallback(async (enabled: boolean) => {
    try {
      await api.updateAutoTradingConfig({ dca_enabled: enabled });
      showToast(enabled ? t('dcaEnabledMsg') : t('dcaDisabledMsg'), 'success');

      if (enabled) {
        const total = status?.config?.fixed_order_value_usd ?? 10;
        const p0 = 71000;
        const p1 = p0 * 0.98;
        const p2 = p0 * 0.96;
        Alert.alert(
          t('dcaPlanTitle'),
          `${t('dcaPlanForSymbol', { symbol: 'BTCUSDC' })}\n` +
          `${t('dcaPlanLineNow', { percent: '40%', price: p0.toFixed(0) })}\n` +
          `${t('dcaPlanLine2', { percent: '35%', price: p1.toFixed(0) })}\n` +
          `${t('dcaPlanLine3', { percent: '25%', price: p2.toFixed(0) })}\n` +
          `${t('dcaPlanTotal', { value: `$${Number(total).toFixed(2)}` })}`
        );
      }

      await loadStatus();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || t('autopilotActionFailed');
      showToast(msg, 'error');
    }
  }, [loadStatus, showToast, status?.config?.fixed_order_value_usd, t]);

  const cancelDcaOrder = useCallback(async (orderId: number) => {
    try {
      await api.cancelDcaOrder(orderId);
      showToast(t('dcaCancelSuccess'), 'success');
      await loadStatus();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || t('autopilotActionFailed');
      showToast(msg, 'error');
    }
  }, [loadStatus, showToast, t]);

  useEffect(() => {
    const logs = status?.recent_log || [];
    const dcaPlanEvent = logs.slice().reverse().find((e) => e.type === 'DCA_PLAN' && e.data?.plan);
    if (!dcaPlanEvent?.timestamp) return;
    if (shownDcaPlanTsRef.current === dcaPlanEvent.timestamp) return;

    shownDcaPlanTsRef.current = dcaPlanEvent.timestamp;
    const plan = Array.isArray(dcaPlanEvent.data?.plan) ? dcaPlanEvent.data.plan : [];
    if (!plan.length) return;

    const symbol = String(dcaPlanEvent.data?.symbol || plan[0]?.symbol || 'BTCUSDC');
    const l1 = plan[0];
    const l2 = plan[1];
    const l3 = plan[2];
    const totalUsd = Number(dcaPlanEvent.data?.total_usd || 0);

    Alert.alert(
      t('dcaPlanTitle'),
      `${t('dcaPlanForSymbol', { symbol })}\n` +
      `${t('dcaPlanLineNow', { percent: '40%', price: Number(l1?.price || 0).toFixed(2) })}\n` +
      `${t('dcaPlanLine2', { percent: '35%', price: Number(l2?.price || 0).toFixed(2) })}\n` +
      `${t('dcaPlanLine3', { percent: '25%', price: Number(l3?.price || 0).toFixed(2) })}\n` +
      `${t('dcaPlanTotal', { value: `$${totalUsd.toFixed(2)}` })}`
    );
  }, [status?.recent_log, t]);

  const getModeDef = (mode: UiAuthorityMode) => {
    return MODE_DEFINITIONS.find((item) => item.mode === mode) || MODE_DEFINITIONS[1];
  };

  const confirmModeChange = useCallback((nextMode: UiAuthorityMode) => {
    if (nextMode === autopilotMode || changingMode) return;

    const localizedMode = t(getModeDef(nextMode).titleKey);
    const isHigherAuthority = MODE_RANK[nextMode] > MODE_RANK[autopilotMode];
    const isSemiAuto = nextMode === 'semi-auto';
    const isFullAutopilot = nextMode === 'full-autopilot';

    let body = `${t('changeModePrompt', { mode: localizedMode })}\n\n${t('changeModeApplyNow')}`;

    if (isFullAutopilot) {
      body = `${t('changeModePrompt', { mode: localizedMode })}\n\n${t('higherRiskModeWarning')}\n${t('liveExecutionWarning')}`;
    } else if (isSemiAuto || isHigherAuthority) {
      body = `${t('changeModePrompt', { mode: localizedMode })}\n\n${t('executionAuthorityIncrease')}`;
    }

    Alert.alert(
      t('changeMode'),
      body,
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('confirm'),
          style: isFullAutopilot ? 'destructive' : 'default',
          onPress: async () => {
            try {
              const token = await getToken();
              if (!token) {
                await handleAuthRequired();
                return;
              }

              setChangingMode(true);
              const backendMode = serializeUiModeToBackend(nextMode);
              await api.setAutopilotMode(backendMode);
              setAutopilotMode(nextMode);
              showToast(`${t('modeChanged')}: ${localizedMode}`, 'success');
              await loadStatus();
            } catch (err: any) {
              if (err?.response?.status === 401 || err?.statusCode === 401) {
                await handleAuthRequired();
                return;
              }
              const msg = err?.response?.data?.detail || err?.message || t('error');
              showToast(msg, 'error');
            } finally {
              setChangingMode(false);
            }
          },
        },
      ]
    );
  }, [autopilotMode, changingMode, handleAuthRequired, showToast, loadStatus, t]);

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
  const dcaEnabled = !!config?.dca_enabled;
  const locale = language === 'el' ? 'el-GR' : 'en-US';
  const environmentMode = status?.mode ?? 'paper';
  const selectedModeDef = getModeDef(autopilotMode);
  const inLiveMode = environmentMode === 'live';
  const executionReady = isEnabled && autopilotMode !== 'manual';
  const hasLastRun = !!status?.last_run;
  const hasNextRun = typeof status?.next_run_in_seconds === 'number' && status.next_run_in_seconds >= 0;
  const isCircuitPaused = circuitBreaker?.state === 'paused';

  const permissionRows = [
    { key: 'alertsOnly', enabled: selectedModeDef.permissions.alertsOnly },
    { key: 'requiresConfirmation', enabled: selectedModeDef.permissions.requiresConfirmation },
    { key: 'autoExecutionAllowed', enabled: selectedModeDef.permissions.autoExecutionAllowed },
    { key: 'exitsManaged', enabled: selectedModeDef.permissions.exitsManaged },
    { key: 'positionResizeAllowed', enabled: selectedModeDef.permissions.positionResizeAllowed },
  ];

  const safeguards = [
    {
      key: 'minConfidence',
      value: typeof config?.confidence_threshold === 'number' ? `${(config.confidence_threshold * 100).toFixed(0)}%` : '—',
    },
    {
      key: 'maxPositions',
      value: typeof config?.max_positions === 'number' ? String(config.max_positions) : '—',
    },
    {
      key: 'maxOrderValue',
      value: typeof config?.max_order_value_usd === 'number' ? `$${config.max_order_value_usd}` : '—',
    },
    {
      key: 'stopLoss',
      value: typeof config?.stop_loss_pct === 'number' ? `${(config.stop_loss_pct * 100).toFixed(0)}%` : '—',
    },
    {
      key: 'takeProfit',
      value: typeof config?.take_profit_pct === 'number' ? `${(config.take_profit_pct * 100).toFixed(0)}%` : '—',
    },
  ];

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
            {t('liveExecutionWarning')}
          </Text>
        </View>

        {/* Current Status */}
        <View style={styles.card}>
          <View style={styles.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{t('currentStatus')}</Text>
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

          <View style={styles.statusGrid}>
            <View style={styles.statusItem}>
              <Text style={styles.statusLabel}>{t('executionEnvironment')}</Text>
              <Text style={styles.statusValue}>{inLiveMode ? t('liveMode') : t('paperMode')}</Text>
            </View>
            <View style={styles.statusItem}>
              <Text style={styles.statusLabel}>{t('currentAuthorityMode')}</Text>
              <Text style={styles.statusValue}>{t(selectedModeDef.titleKey)}</Text>
            </View>
          </View>

          <View style={[styles.modeBadge, { backgroundColor: inLiveMode ? theme.colors.semantic.error + '20' : theme.colors.semantic.success + '20' }]}>
            <Text style={[styles.modeBadgeText, { color: inLiveMode ? theme.colors.semantic.error : theme.colors.semantic.success }]}>
              {inLiveMode ? `🔴 ${t('liveMode')}` : `🟢 ${t('paperMode')}`}
            </Text>
          </View>
          {hasLastRun && (
            <Text style={styles.statusMeta}>
              {t('lastRun')}: {new Date(status!.last_run!).toLocaleTimeString(locale)} | {t('totalTrades')}: {status?.total_auto_trades ?? 0}
            </Text>
          )}
          {hasNextRun && (
            <Text style={styles.statusMeta}>
              {t('nextRun')}: {status?.next_run_in_seconds}s
            </Text>
          )}
        </View>

        {/* Authority Mode Selector */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('autopilotMode')}</Text>
          <View style={styles.modeCardsRow}>
            {MODE_DEFINITIONS.map((modeDef) => {
              const selected = autopilotMode === modeDef.mode;
              return (
                <TouchableOpacity
                  key={modeDef.mode}
                  style={[
                    styles.modeCard,
                    {
                      borderColor: modeDef.borderColor,
                      backgroundColor: selected ? modeDef.borderColor + '12' : theme.colors.ui.background,
                    },
                    selected && styles.modeCardSelected,
                  ]}
                  activeOpacity={0.85}
                  disabled={changingMode}
                  onPress={() => confirmModeChange(modeDef.mode)}
                >
                  <View style={styles.modeCardHeader}>
                    <Text style={[styles.riskPill, { backgroundColor: modeDef.riskColor + '20', color: modeDef.riskColor }]}>{t(modeDef.riskLabelKey)}</Text>
                    {selected && <Text style={styles.modeCheck}>✓</Text>}
                  </View>
                  <Text style={styles.modeCardTitle}>{t(modeDef.titleKey)}</Text>
                  <Text style={styles.modeCardDetail}>{t(modeDef.descriptionKey)}</Text>
                  <Text style={styles.modeCardDetail}>• {t('requiresConfirmation')}: {modeDef.requiresConfirmation ? t('yes') : t('no')}</Text>
                  <Text style={styles.modeCardDetail}>• {t('autoExecutionAllowed')}: {modeDef.autoExecutionAllowed ? t('yes') : t('no')}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Permissions per Mode */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('autopilotPermissions')}</Text>
          {permissionRows.map((item) => (
            <View key={item.key} style={styles.permissionRow}>
              <Text style={[styles.permissionLabel, !item.enabled && styles.permissionMuted]}>{t(item.key)}</Text>
              <Text style={[styles.permissionState, item.enabled ? styles.permissionOn : styles.permissionOff]}>
                {item.enabled ? t('allowed') : t('notAllowed')}
              </Text>
            </View>
          ))}
        </View>

        {/* Safeguards / Risk Boundaries */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('autopilotSafeguards')}</Text>
          {safeguards.map((item) => (
            <View key={item.key} style={styles.configRow}>
              <Text style={styles.configLabel}>{t(item.key)}</Text>
              <Text style={styles.configValue}>{item.value}</Text>
            </View>
          ))}
          <View style={styles.cautionBox}>
            <Text style={styles.cautionText}>{t('liveExecutionWarning')}</Text>
          </View>
        </View>

        {/* Broker / Execution Readiness */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('brokerReadiness')}</Text>
          <View style={styles.configRow}>
            <Text style={styles.configLabel}>{t('executionEnvironment')}</Text>
            <Text style={styles.configValue}>{inLiveMode ? t('liveMode') : t('paperMode')}</Text>
          </View>
          <View style={styles.configRow}>
            <Text style={styles.configLabel}>{t('brokerRequired')}</Text>
            <Text style={styles.configValue}>{inLiveMode ? t('yes') : t('no')}</Text>
          </View>
          <View style={styles.configRow}>
            <Text style={styles.configLabel}>{t('executionReadiness')}</Text>
            <Text style={[styles.configValue, executionReady ? styles.readinessOk : styles.readinessWarn]}>
              {executionReady ? t('ready') : t('caution')}
            </Text>
          </View>
          <Text style={styles.readinessFallback}>{t('brokerReadinessFallback')}</Text>
          {inLiveMode && (
            <Text style={styles.readinessFallback}>{t('liveExecutionWarning')}</Text>
          )}
        </View>

        {/* Circuit Breaker */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('circuitBreaker')}</Text>
          <View style={styles.configRow}>
            <Text style={styles.configLabel}>{t('circuitBreakerState')}</Text>
            <Text style={[styles.configValue, isCircuitPaused ? styles.readinessWarn : styles.readinessOk]}>
              {isCircuitPaused ? t('circuitBreakerPaused') : t('circuitBreakerActive')}
            </Text>
          </View>
          {isCircuitPaused && (
            <>
              <View style={styles.configRow}>
                <Text style={styles.configLabel}>{t('circuitBreakerReason')}</Text>
                <Text style={styles.configValue}>{circuitBreaker?.reason || '-'}</Text>
              </View>
              <View style={styles.configRow}>
                <Text style={styles.configLabel}>{t('circuitBreakerResumeAt')}</Text>
                <Text style={styles.configValue}>
                  {circuitBreaker?.resume_at ? new Date(circuitBreaker.resume_at).toLocaleString(locale) : '-'}
                </Text>
              </View>
              <View style={styles.configRow}>
                <Text style={styles.configLabel}>{t('circuitBreakerMinutesRemaining')}</Text>
                <Text style={styles.configValue}>{circuitBreaker?.minutes_remaining ?? 0}</Text>
              </View>
              <TouchableOpacity style={styles.resetButton} onPress={resetCircuitBreaker}>
                <Text style={styles.resetButtonText}>{t('circuitBreakerReset')}</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* Current Configuration */}
        {config && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('currentConfiguration')}</Text>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('minConfidence')}</Text>
              <Text style={styles.configValue}>{(config.confidence_threshold * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('positionSize')}</Text>
              <Text style={styles.configValue}>${config.fixed_order_value_usd ?? 10}</Text>
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
            <View style={styles.configRow}>
              <Text style={styles.configLabel}>{t('dcaMode')}</Text>
              <Text style={styles.configValue}>{dcaEnabled ? 'ON' : 'OFF'}</Text>
            </View>
          </View>
        )}

        {/* DCA Mode */}
        <View style={styles.card}>
          <View style={styles.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{t('dcaMode')}</Text>
              <Text style={styles.cardSubtitle}>{t('dcaModeSubtitle')}</Text>
            </View>
            <Switch
              value={dcaEnabled}
              onValueChange={toggleDcaMode}
              trackColor={{ false: theme.colors.ui.border, true: theme.colors.brand.primary + '80' }}
              thumbColor={dcaEnabled ? theme.colors.brand.primary : '#f4f3f4'}
            />
          </View>
        </View>

        {/* DCA Orders */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('dcaOrdersTitle')}</Text>
          {dcaOrders.pending.length === 0 ? (
            <Text style={styles.emptyText}>{t('dcaNoPending')}</Text>
          ) : (
            dcaOrders.pending.map((order) => (
              <View key={order.id} style={styles.positionRow}>
                <View>
                  <Text style={styles.positionSymbol}>{order.symbol}</Text>
                  <Text style={styles.positionDetail}>{t('dcaTarget')}: ${order.target_price.toFixed(6)}</Text>
                  <Text style={styles.positionDetail}>{t('dcaSize')}: ${order.size_usd.toFixed(2)}</Text>
                </View>
                <TouchableOpacity
                  style={styles.cancelDcaButton}
                  onPress={() => cancelDcaOrder(order.id)}
                >
                  <Text style={styles.cancelDcaText}>{t('cancel')}</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
        </View>

        {/* Open Positions */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('openPositions')} ({positions.length})</Text>
          {positions.length === 0 ? (
            <Text style={styles.emptyText}>{t('noOpenPositions')}</Text>
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
                  <Text style={[styles.positionDetail, { color: theme.colors.brand.primary }]}>
                    {t('trailingStop')}: ${Number(pos.trailing_stop ?? pos.stop_loss ?? 0).toFixed(2)} {pos.trailing_last_move === 'up' ? t('trailingStopMovedUp') : ''}
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
            <Text style={styles.emptyText}>{t('autopilotNoActivity')}</Text>
          ) : (
            logs.slice().reverse().slice(0, 10).map((entry, i) => (
              <View key={i} style={styles.logEntry}>
                <Text style={styles.logType}>{entry.type}</Text>
                <Text style={styles.logMessage}>{entry.message}</Text>
                <Text style={styles.logTime}>
                  {new Date(entry.timestamp).toLocaleTimeString(locale)}
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
    borderRadius: theme.borderRadius.xlarge,
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
  cancelDcaButton: {
    alignSelf: 'center' as const,
    backgroundColor: theme.colors.semantic.error,
    borderRadius: theme.borderRadius.sm,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
  },
  cancelDcaText: {
    color: '#FFFFFF',
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700' as const,
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
    borderRadius: theme.borderRadius.md,
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
  statusGrid: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginTop: theme.spacing.sm,
  },
  statusItem: {
    flex: 1,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.sm,
    backgroundColor: theme.colors.ui.background,
  },
  statusLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginBottom: 2,
  },
  statusValue: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.primary,
    fontWeight: '700' as const,
  },
  modeCardsRow: {
    flexDirection: 'column',
    gap: theme.spacing.sm,
  },
  modeCard: {
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.sm,
  },
  modeCardSelected: {
    borderWidth: 2,
  },
  modeCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  riskPill: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700' as const,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 3,
    borderRadius: theme.borderRadius.full,
  },
  modeCheck: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.semantic.success,
    fontWeight: '700' as const,
  },
  modeCardTitle: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700' as const,
    color: theme.colors.text.primary,
    marginTop: theme.spacing.xs,
    marginBottom: theme.spacing.xs,
  },
  modeCardDetail: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    lineHeight: 16,
    marginTop: 2,
  },
  permissionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  permissionLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.primary,
    flex: 1,
  },
  permissionMuted: {
    color: theme.colors.text.tertiary,
  },
  permissionState: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700' as const,
  },
  permissionOn: {
    color: theme.colors.semantic.success,
  },
  permissionOff: {
    color: theme.colors.text.tertiary,
  },
  cautionBox: {
    marginTop: theme.spacing.sm,
    borderWidth: 1,
    borderColor: theme.colors.semantic.warning + '66',
    backgroundColor: theme.colors.semantic.warning + '12',
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.sm,
  },
  cautionText: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    lineHeight: 16,
  },
  readinessFallback: {
    marginTop: theme.spacing.sm,
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    lineHeight: 16,
  },
  readinessOk: {
    color: theme.colors.semantic.success,
  },
  readinessWarn: {
    color: theme.colors.semantic.warning,
  },
  resetButton: {
    marginTop: theme.spacing.md,
    backgroundColor: theme.colors.semantic.error,
    borderRadius: theme.borderRadius.md,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  resetButtonText: {
    color: '#FFFFFF',
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700' as const,
  },
});

