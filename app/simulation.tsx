import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import Slider from '@react-native-community/slider';
import { useRouter } from 'expo-router';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { theme } from '../mobile/src/constants/theme';
import { api } from '../mobile/src/services/apiClient';
import { getToken } from '../mobile/src/utils/tokenStorage';
import { useAppStore } from '../mobile/src/stores/appStore';

type StrategyKey = 'ai_follow' | 'conservative_ai' | 'buy_and_hold';

interface SimulationTrade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  entry_price: number;
  exit_price: number;
  pnl: number;
  confidence: number;
}

interface SimulationMetrics {
  total_pl: number;
  total_pl_pct: number;
  win_rate: number;
  total_trades: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
}

const STRATEGIES: { key: StrategyKey; labelKey: string }[] = [
  { key: 'ai_follow', labelKey: 'simulationStrategyAiFollow' },
  { key: 'conservative_ai', labelKey: 'simulationStrategyConservativeAi' },
  { key: 'buy_and_hold', labelKey: 'simulationStrategyBuyHold' },
];

const AVAILABLE_SYMBOLS = ['BTCUSDC', 'ETHUSDC', 'BNBUSDC', 'SOLUSDC', 'ADAUSDC'];
const TIMEFRAMES = [7, 14, 30, 90];

export default function SimulationScreen() {
  const router = useRouter();
  const { t } = useLanguage();
  const { showToast } = useAppStore();

  const [strategy, setStrategy] = useState<StrategyKey>('ai_follow');
  const [symbols, setSymbols] = useState<string[]>(['BTCUSDC', 'ETHUSDC']);
  const [timeframeDays, setTimeframeDays] = useState<number>(30);
  const [capital, setCapital] = useState<string>('10000');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(70);
  const [stopLossPct, setStopLossPct] = useState<number>(3);
  const [takeProfitPct, setTakeProfitPct] = useState<number>(5);

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<SimulationMetrics | null>(null);
  const [trades, setTrades] = useState<SimulationTrade[]>([]);

  const pnlPositive = (metrics?.total_pl || 0) >= 0;
  const pnlColor = pnlPositive ? theme.colors.market.bullish : theme.colors.market.bearish;

  const isValid = useMemo(() => {
    const parsedCapital = Number(capital);
    return Number.isFinite(parsedCapital) && parsedCapital > 0 && symbols.length > 0;
  }, [capital, symbols.length]);

  const isAuthError = useCallback((err: any) => {
    const detail = String(err?.response?.data?.detail || err?.message || '').toLowerCase();
    return err?.response?.status === 401
      || err?.statusCode === 401
      || detail.includes('missing authorization token')
      || detail.includes('authorization token')
      || detail.includes('not authenticated');
  }, []);

  const handleAuthRequired = useCallback(async () => {
    setError(null);
    showToast(t('sessionExpired'), 'error');
    router.replace('/login');
  }, [router, showToast, t]);

  const toggleSymbol = (symbol: string) => {
    setSymbols((prev) => {
      if (prev.includes(symbol)) {
        return prev.filter((s) => s !== symbol);
      }
      return [...prev, symbol];
    });
  };

  const normalizeMetrics = (raw: any): SimulationMetrics => {
    const source = raw?.metrics || raw?.summary || raw || {};
    return {
      total_pl: Number(source.total_pl ?? source.totalPnl ?? source.total_profit ?? 0),
      total_pl_pct: Number(source.total_pl_pct ?? source.totalPnlPct ?? source.total_return_pct ?? 0),
      win_rate: Number(source.win_rate ?? source.winRate ?? source.win_rate_pct ?? 0),
      total_trades: Number(source.total_trades ?? source.totalTrades ?? 0),
      max_drawdown: Number(source.max_drawdown ?? source.maxDrawdown ?? source.max_drawdown_pct ?? 0),
      sharpe_ratio: Number(source.sharpe_ratio ?? source.sharpeRatio ?? 0),
      profit_factor: Number(source.profit_factor ?? source.profitFactor ?? 0),
      avg_win: Number(source.avg_win ?? source.avgWin ?? 0),
      avg_loss: Number(source.avg_loss ?? source.avgLoss ?? 0),
    };
  };

  const normalizeTrades = (raw: any): SimulationTrade[] => {
    const source = raw?.trades || raw?.data?.trades || [];
    if (!Array.isArray(source)) return [];

    return source.map((trade: any, index: number) => {
      const normalizedSide = String(trade.side || trade.action || 'BUY').toUpperCase() === 'SELL' ? 'SELL' : 'BUY';
      return {
        id: String(trade.id || `${trade.symbol || 'trade'}_${index}`),
        symbol: String(trade.symbol || trade.asset || '-'),
        side: normalizedSide,
        entry_price: Number(trade.entry_price ?? trade.entryPrice ?? trade.entry ?? 0),
        exit_price: Number(trade.exit_price ?? trade.exitPrice ?? trade.exit ?? 0),
        pnl: Number(trade.pnl ?? trade.profit ?? trade.total_pl ?? 0),
        confidence: Number(trade.confidence ?? trade.confidence_score ?? 0),
      };
    });
  };

  const runSimulation = async () => {
    setRunning(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) {
        await handleAuthRequired();
        return;
      }

      const payload = {
        strategy,
        symbols,
        timeframe_days: timeframeDays,
        capital: Number(capital),
        confidence_threshold: confidenceThreshold,
        stop_loss_pct: stopLossPct,
        take_profit_pct: takeProfitPct,
      };

      const response = await api.runSimulation(payload);
      setMetrics(normalizeMetrics(response));
      setTrades(normalizeTrades(response));
    } catch (e: any) {
      if (isAuthError(e)) {
        await handleAuthRequired();
        return;
      }
      const message = e?.response?.data?.detail || e?.message || t('simulationRunError');
      setError(message);
      setMetrics(null);
      setTrades([]);
    } finally {
      setRunning(false);
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('simulationFormTitle')}</Text>

          <Text style={styles.label}>{t('simulationStrategy')}</Text>
          <View style={styles.wrapRow}>
            {STRATEGIES.map((item) => {
              const selected = strategy === item.key;
              return (
                <TouchableOpacity
                  key={item.key}
                  style={[styles.chip, selected && styles.chipSelected]}
                  onPress={() => setStrategy(item.key)}
                >
                  <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{t(item.labelKey)}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={styles.label}>{t('simulationSymbols')}</Text>
          <View style={styles.wrapRow}>
            {AVAILABLE_SYMBOLS.map((symbol) => {
              const selected = symbols.includes(symbol);
              return (
                <TouchableOpacity
                  key={symbol}
                  style={[styles.chip, selected && styles.chipSelected]}
                  onPress={() => toggleSymbol(symbol)}
                >
                  <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{symbol}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={styles.label}>{t('simulationTimeframe')}</Text>
          <View style={styles.row}>
            {TIMEFRAMES.map((days) => {
              const active = timeframeDays === days;
              return (
                <TouchableOpacity
                  key={days}
                  style={[styles.timeframeButton, active && styles.timeframeButtonActive]}
                  onPress={() => setTimeframeDays(days)}
                >
                  <Text style={[styles.timeframeText, active && styles.timeframeTextActive]}>{days}d</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={styles.label}>{t('simulationCapital')}</Text>
          <TextInput
            style={styles.input}
            value={capital}
            onChangeText={setCapital}
            keyboardType="decimal-pad"
            placeholder="10000"
            placeholderTextColor={theme.colors.text.tertiary}
          />

          <View style={styles.sliderHeader}>
            <Text style={styles.label}>{t('simulationConfidenceThreshold')}</Text>
            <Text style={styles.sliderValue}>{confidenceThreshold}%</Text>
          </View>
          <Slider
            minimumValue={50}
            maximumValue={95}
            step={1}
            value={confidenceThreshold}
            onValueChange={setConfidenceThreshold}
            minimumTrackTintColor={theme.colors.brand.primary}
            maximumTrackTintColor={theme.colors.ui.border}
            thumbTintColor={theme.colors.brand.primary}
          />

          <View style={styles.sliderHeader}>
            <Text style={styles.label}>{t('simulationStopLoss')}</Text>
            <Text style={styles.sliderValue}>{stopLossPct}%</Text>
          </View>
          <Slider
            minimumValue={1}
            maximumValue={10}
            step={1}
            value={stopLossPct}
            onValueChange={setStopLossPct}
            minimumTrackTintColor={theme.colors.market.bearish}
            maximumTrackTintColor={theme.colors.ui.border}
            thumbTintColor={theme.colors.market.bearish}
          />

          <View style={styles.sliderHeader}>
            <Text style={styles.label}>{t('simulationTakeProfit')}</Text>
            <Text style={styles.sliderValue}>{takeProfitPct}%</Text>
          </View>
          <Slider
            minimumValue={1}
            maximumValue={20}
            step={1}
            value={takeProfitPct}
            onValueChange={setTakeProfitPct}
            minimumTrackTintColor={theme.colors.market.bullish}
            maximumTrackTintColor={theme.colors.ui.border}
            thumbTintColor={theme.colors.market.bullish}
          />

          <TouchableOpacity
            style={[styles.runButton, (!isValid || running) && styles.runButtonDisabled]}
            onPress={runSimulation}
            disabled={!isValid || running}
            activeOpacity={0.8}
          >
            {running ? (
              <View style={styles.loadingRow}>
                <ActivityIndicator color="#FFFFFF" size="small" />
                <Text style={styles.runButtonText}>{t('simulationRunning')}</Text>
              </View>
            ) : (
              <Text style={styles.runButtonText}>{t('simulationRun')}</Text>
            )}
          </TouchableOpacity>

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
        </View>

        {metrics && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>{t('simulationResults')}</Text>

            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationTotalPl')}</Text>
              <Text style={[styles.resultValue, { color: pnlColor }]}>
                {`${metrics.total_pl >= 0 ? '+' : ''}$${Math.abs(metrics.total_pl).toFixed(2)} (${metrics.total_pl_pct >= 0 ? '+' : ''}${metrics.total_pl_pct.toFixed(2)}%)`}
              </Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationWinRate')}</Text>
              <Text style={styles.resultValue}>{metrics.win_rate.toFixed(2)}%</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationTotalTrades')}</Text>
              <Text style={styles.resultValue}>{metrics.total_trades}</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationMaxDrawdown')}</Text>
              <Text style={[styles.resultValue, { color: theme.colors.market.bearish }]}>{metrics.max_drawdown.toFixed(2)}%</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationSharpeRatio')}</Text>
              <Text style={styles.resultValue}>{metrics.sharpe_ratio.toFixed(2)}</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationProfitFactor')}</Text>
              <Text style={styles.resultValue}>{metrics.profit_factor.toFixed(2)}</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>{t('simulationAvgWinAvgLoss')}</Text>
              <Text style={styles.resultValue}>{`$${metrics.avg_win.toFixed(2)} / -$${Math.abs(metrics.avg_loss).toFixed(2)}`}</Text>
            </View>
          </View>
        )}

        {trades.length > 0 && (
          <View style={[styles.card, styles.tradeListCard]}>
            <Text style={styles.sectionTitle}>{t('simulationTrades')}</Text>
            <ScrollView style={styles.tradeList} nestedScrollEnabled>
              {trades.map((trade) => {
                const buy = trade.side === 'BUY';
                const sideColor = buy ? theme.colors.market.bullish : theme.colors.market.bearish;
                const tradePnlColor = trade.pnl >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish;
                return (
                  <View key={trade.id} style={styles.tradeItem}>
                    <View style={styles.tradeTopRow}>
                      <Text style={styles.tradeSymbol}>{trade.symbol}</Text>
                      <View style={[styles.badge, { backgroundColor: sideColor + '20' }]}>
                        <Text style={[styles.badgeText, { color: sideColor }]}>{trade.side}</Text>
                      </View>
                    </View>

                    <Text style={styles.tradeText}>
                      {t('simulationEntryExit')}: {trade.entry_price.toFixed(4)} → {trade.exit_price.toFixed(4)}
                    </Text>
                    <Text style={[styles.tradeText, { color: tradePnlColor }]}>
                      {t('simulationTradePl')}: {trade.pnl >= 0 ? '+' : ''}${Math.abs(trade.pnl).toFixed(2)}
                    </Text>
                    <Text style={styles.tradeText}>{t('simulationTradeConfidence')}: {Math.round(trade.confidence * (trade.confidence <= 1 ? 100 : 1))}%</Text>
                  </View>
                );
              })}
            </ScrollView>
          </View>
        )}
        <View style={styles.bottomSpace} />
      </ScrollView>

      <View style={styles.disclaimerWrap}>
        <Text style={styles.disclaimerText}>{t('simulationDisclaimer')}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  scroll: {
    flex: 1,
  },
  content: {
    padding: theme.spacing.md,
    paddingBottom: 96,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  label: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
    marginTop: theme.spacing.sm,
  },
  wrapRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.xs,
  },
  chip: {
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    backgroundColor: theme.colors.ui.background,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.full,
  },
  chipSelected: {
    backgroundColor: theme.colors.brand.primary,
    borderColor: theme.colors.brand.primary,
  },
  chipText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.primary,
    fontWeight: '600',
  },
  chipTextSelected: {
    color: '#FFFFFF',
  },
  row: {
    flexDirection: 'row',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  timeframeButton: {
    flex: 1,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.md,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  timeframeButtonActive: {
    backgroundColor: theme.colors.brand.primary,
    borderColor: theme.colors.brand.primary,
  },
  timeframeText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.primary,
    fontWeight: '700',
  },
  timeframeTextActive: {
    color: '#FFFFFF',
  },
  input: {
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: theme.spacing.xs,
  },
  sliderValue: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    fontWeight: '700',
  },
  runButton: {
    backgroundColor: '#2563EB',
    borderRadius: theme.borderRadius.md,
    paddingVertical: theme.spacing.md,
    alignItems: 'center',
    marginTop: theme.spacing.md,
  },
  runButtonDisabled: {
    opacity: 0.6,
  },
  runButtonText: {
    color: '#FFFFFF',
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  errorBox: {
    marginTop: theme.spacing.md,
    backgroundColor: theme.colors.market.bearish + '15',
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.sm,
  },
  errorText: {
    color: theme.colors.market.bearish,
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
  },
  resultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  resultLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    flex: 1,
  },
  resultValue: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontWeight: '700',
    textAlign: 'right',
  },
  tradeListCard: {
    maxHeight: 340,
  },
  tradeList: {
    maxHeight: 260,
  },
  tradeItem: {
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.sm,
    marginBottom: theme.spacing.sm,
    backgroundColor: theme.colors.ui.background,
  },
  tradeTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.xs,
  },
  tradeSymbol: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontWeight: '700',
  },
  badge: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 2,
    borderRadius: theme.borderRadius.full,
  },
  badgeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
  },
  tradeText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: 2,
  },
  bottomSpace: {
    height: theme.spacing.md,
  },
  disclaimerWrap: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopWidth: 1,
    borderTopColor: theme.colors.ui.border,
    backgroundColor: theme.colors.ui.cardBackground,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
  },
  disclaimerText: {
    textAlign: 'center',
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    fontWeight: '600',
  },
});
