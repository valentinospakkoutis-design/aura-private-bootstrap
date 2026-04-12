import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, FlatList, RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { SkeletonList } from '../mobile/src/components/SkeletonLoader';
import { EmptyState } from '../mobile/src/components/EmptyState';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';

// ── Types ──────────────────────────────────────────────────────

interface FeedEvent {
  id: number | string;
  event_type: string;
  title: string;
  body?: string;
  summary?: string;
  short_summary?: string;
  symbol?: string;
  related_symbol?: string;
  severity?: string;
  priority?: string;
  timestamp?: string;
  created_at?: string;
  reason_codes?: string[];
  metadata?: Record<string, any>;
}

type FilterKey = 'all' | 'signals' | 'risk' | 'auto' | 'insights';

// ── Config ─────────────────────────────────────────────────────

const SEVERITY_ICONS: Record<string, string> = {
  critical: '🔴',
  warning: '🟡',
  info: '🔵',
  high: '🔴',
  medium: '🟡',
  low: '🔵',
};

const EVENT_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  trade_signal:           { label: 'Signal',    color: theme.colors.market.bullish },
  trade_opportunity:      { label: 'Signal',    color: theme.colors.market.bullish },
  no_trade_explanation:   { label: 'No Trade',  color: theme.colors.text.secondary },
  risk_alert:             { label: 'Risk',      color: theme.colors.semantic.error },
  exposure_warning:       { label: 'Exposure',  color: theme.colors.semantic.warning },
  portfolio_alert:        { label: 'Portfolio', color: theme.colors.semantic.warning },
  auto_trade:             { label: 'Auto',      color: theme.colors.brand.primary },
  autopilot_update:       { label: 'Autopilot', color: theme.colors.brand.primary },
  market_insight:         { label: 'Insight',   color: theme.colors.accent.purple },
  portfolio_health:       { label: 'Health',    color: theme.colors.accent.blue },
  personalization_insight:{ label: 'Personal',  color: theme.colors.brand.secondary },
  blocked_trade:          { label: 'Blocked',   color: theme.colors.semantic.error },
  reduced_position:       { label: 'Reduced',   color: theme.colors.semantic.warning },
  decision_explanation:   { label: 'Decision',  color: theme.colors.brand.primary },
  system:                 { label: 'System',    color: theme.colors.text.secondary },
};

const DEFAULT_EVENT_CONFIG = { label: 'Event', color: theme.colors.text.secondary };

const FILTER_MAP: Record<FilterKey, string[]> = {
  all: [],
  signals: ['trade_signal', 'trade_opportunity', 'no_trade_explanation'],
  risk: ['risk_alert', 'exposure_warning', 'portfolio_alert', 'blocked_trade', 'reduced_position'],
  auto: ['auto_trade', 'autopilot_update'],
  insights: ['market_insight', 'portfolio_health', 'personalization_insight', 'decision_explanation'],
};

const AUTO_REFRESH_MS = 60_000;

// ── Screen ─────────────────────────────────────────────────────

export default function AIFeedScreen() {
  const { t } = useLanguage();
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all');

  const loadEvents = useCallback(async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(false);
      const data = await api.getFeedEvents(50);
      setEvents(Array.isArray(data) ? data : []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEvents(true);
    const interval = setInterval(() => loadEvents(false), AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [loadEvents]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadEvents(false);
    setRefreshing(false);
  }, [loadEvents]);

  const filteredEvents = useMemo(() => {
    if (activeFilter === 'all') return events;
    const types = FILTER_MAP[activeFilter];
    return events.filter(e => types.includes(e.event_type));
  }, [events, activeFilter]);

  // ── Filters ──

  const FILTERS: { key: FilterKey; labelKey: string }[] = [
    { key: 'all', labelKey: 'filterAll' },
    { key: 'signals', labelKey: 'filterSignals' },
    { key: 'risk', labelKey: 'filterRisk' },
    { key: 'auto', labelKey: 'filterAuto' },
    { key: 'insights', labelKey: 'filterInsights' },
  ];

  const renderFilterBar = () => (
    <View style={styles.filterBar}>
      {FILTERS.map(f => {
        const active = activeFilter === f.key;
        return (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterChip, active && styles.filterChipActive]}
            onPress={() => setActiveFilter(f.key)}
            activeOpacity={0.7}
          >
            <Text style={[styles.filterText, active && styles.filterTextActive]}>
              {t(f.labelKey)}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  // ── Card ──

  const renderCard = ({ item }: { item: FeedEvent }) => {
    const typeConfig = EVENT_TYPE_CONFIG[item.event_type] || DEFAULT_EVENT_CONFIG;
    const severityIcon = SEVERITY_ICONS[item.severity || item.priority || 'info'] || '🔵';
    const sym = item.symbol || item.related_symbol;
    const bodyText = item.body || item.summary || item.short_summary || '';
    const ts = item.timestamp || item.created_at;
    const relativeTime = ts ? DateFormatter.toRelativeTime(ts) : '';

    return (
      <View style={styles.card}>
        {/* Header row */}
        <View style={styles.cardHeader}>
          <Text style={styles.severityIcon}>{severityIcon}</Text>
          <View style={[styles.typeBadge, { backgroundColor: typeConfig.color + '18' }]}>
            <Text style={[styles.typeBadgeText, { color: typeConfig.color }]}>
              {typeConfig.label}
            </Text>
          </View>
          {sym ? (
            <View style={styles.symbolBadge}>
              <Text style={styles.symbolText}>{sym}</Text>
            </View>
          ) : null}
          <View style={{ flex: 1 }} />
          {relativeTime ? (
            <Text style={styles.timestamp}>{relativeTime}</Text>
          ) : null}
        </View>

        {/* Title */}
        <Text style={styles.cardTitle} numberOfLines={2}>
          {item.title || typeConfig.label}
        </Text>

        {/* Body */}
        {bodyText ? (
          <Text style={styles.cardBody} numberOfLines={4}>
            {bodyText}
          </Text>
        ) : null}
      </View>
    );
  };

  // ── States ──

  if (loading && events.length === 0) {
    return (
      <View style={styles.container}>
        {renderFilterBar()}
        <View style={styles.content}>
          <SkeletonList count={5} />
        </View>
      </View>
    );
  }

  if (error && events.length === 0) {
    return (
      <View style={styles.container}>
        {renderFilterBar()}
        <NoData onRetry={() => loadEvents(true)} />
      </View>
    );
  }

  if (filteredEvents.length === 0) {
    return (
      <View style={styles.container}>
        {renderFilterBar()}
        <EmptyState
          icon="AI"
          title={t('aiFeedEmpty')}
          description={t('aiFeedEmptyDesc')}
          actionLabel={t('retry')}
          onAction={() => loadEvents(true)}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {renderFilterBar()}
      <FlatList
        data={filteredEvents}
        keyExtractor={(item, i) => String(item.id ?? i)}
        renderItem={renderCard}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.colors.brand.primary}
          />
        }
      />
    </View>
  );
}

// ── Styles ──────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
  },
  listContent: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },

  // Filter bar
  filterBar: {
    flexDirection: 'row',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.xs,
    backgroundColor: theme.colors.ui.background,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  filterChip: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs + 2,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  filterChipActive: {
    backgroundColor: theme.colors.brand.primary + '15',
    borderColor: theme.colors.brand.primary,
  },
  filterText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '500' as const,
    color: theme.colors.text.secondary,
  },
  filterTextActive: {
    color: theme.colors.brand.primary,
    fontWeight: '700' as const,
  },

  // Card
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  severityIcon: {
    fontSize: 14,
  },
  typeBadge: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 2,
    borderRadius: theme.borderRadius.full,
  },
  typeBadgeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700' as const,
  },
  symbolBadge: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 2,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.brand.primary + '12',
  },
  symbolText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '600' as const,
    color: theme.colors.brand.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  timestamp: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.tertiary,
  },
  cardTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700' as const,
    color: theme.colors.text.primary,
    lineHeight: 22,
    marginBottom: theme.spacing.xs,
  },
  cardBody: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
  },
});
