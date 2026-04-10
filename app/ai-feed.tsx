import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { AnimatedListItem } from '../mobile/src/components/AnimatedListItem';
import { NoData } from '../mobile/src/components/NoData';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { SkeletonList } from '../mobile/src/components/SkeletonLoader';
import { useApi } from '../mobile/src/hooks/useApi';
import { theme } from '../mobile/src/constants/theme';
import { api } from '../mobile/src/services/apiClient';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';

type FeedFilter = 'all' | 'signals' | 'risk' | 'auto' | 'insights';

interface FeedEvent {
  id?: string | number;
  event_type?: string;
  title?: string;
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
}

const STRINGS = {
  filters: {
    all: 'Όλα',
    signals: 'Signals',
    risk: 'Risk',
    auto: 'Auto',
    insights: 'Insights',
  },
  emptyTitle: 'Δεν υπάρχουν events ακόμα',
  emptyDescription: 'Το AI Feed θα εμφανίσει νέα events μόλις παραχθούν από το backend.',
  errorTitle: 'Δεν ήταν δυνατή η φόρτωση του AI Feed',
  errorDescription: 'Δοκίμασε ξανά για να φορτώσουμε τα τελευταία events.',
  fallbackTitle: 'AI Event',
  fallbackBody: 'Δεν υπάρχει διαθέσιμη περιγραφή για αυτό το event.',
  fallbackBadge: 'Event',
};

const FILTER_TYPES: Record<FeedFilter, string[] | null> = {
  all: null,
  signals: ['trade_signal', 'no_trade_explanation', 'blocked_trade', 'reduced_position'],
  risk: ['risk_alert', 'portfolio_alert', 'exposure_warning'],
  auto: ['auto_trade', 'autopilot_update'],
  insights: ['market_insight', 'decision_explanation', 'portfolio_health', 'personalization_insight'],
};

const EVENT_TYPE_STYLES: Record<
  string,
  { label: string; backgroundColor: string; textColor: string }
> = {
  trade_signal: {
    label: 'Signal',
    backgroundColor: theme.colors.market.bullish + '20',
    textColor: theme.colors.market.bullish,
  },
  no_trade_explanation: {
    label: 'No Trade',
    backgroundColor: theme.colors.ui.border,
    textColor: theme.colors.text.secondary,
  },
  risk_alert: {
    label: 'Risk',
    backgroundColor: theme.colors.semantic.error + '20',
    textColor: theme.colors.semantic.error,
  },
  auto_trade: {
    label: 'Auto',
    backgroundColor: theme.colors.accent.blue + '20',
    textColor: theme.colors.accent.blue,
  },
  market_insight: {
    label: 'Insight',
    backgroundColor: theme.colors.accent.purple + '20',
    textColor: theme.colors.accent.purple,
  },
  portfolio_alert: {
    label: 'Portfolio',
    backgroundColor: theme.colors.accent.orange + '20',
    textColor: theme.colors.accent.orange,
  },
  blocked_trade: {
    label: 'Blocked',
    backgroundColor: theme.colors.semantic.error + '20',
    textColor: theme.colors.semantic.error,
  },
  reduced_position: {
    label: 'Reduced',
    backgroundColor: theme.colors.semantic.warning + '20',
    textColor: theme.colors.semantic.warning,
  },
  decision_explanation: {
    label: 'Explain',
    backgroundColor: theme.colors.brand.secondary + '20',
    textColor: theme.colors.brand.secondary,
  },
  exposure_warning: {
    label: 'Exposure',
    backgroundColor: theme.colors.semantic.warning + '20',
    textColor: theme.colors.semantic.warning,
  },
  autopilot_update: {
    label: 'Autopilot',
    backgroundColor: theme.colors.accent.blue + '20',
    textColor: theme.colors.accent.blue,
  },
  portfolio_health: {
    label: 'Health',
    backgroundColor: theme.colors.accent.orange + '20',
    textColor: theme.colors.accent.orange,
  },
  personalization_insight: {
    label: 'Personal',
    backgroundColor: theme.colors.brand.primary + '20',
    textColor: theme.colors.brand.primary,
  },
};

function getSeverityIcon(event: FeedEvent) {
  const severity = (event.severity || event.priority || '').toString().toLowerCase();

  if (severity === 'critical' || severity === 'high') return '🔴';
  if (severity === 'warning' || severity === 'medium') return '🟡';
  return '🔵';
}

function getEventTypeStyle(eventType?: string) {
  if (!eventType) {
    return {
      label: STRINGS.fallbackBadge,
      backgroundColor: theme.colors.ui.border,
      textColor: theme.colors.text.secondary,
    };
  }

  return (
    EVENT_TYPE_STYLES[eventType] || {
      label: 'Event',
      backgroundColor: theme.colors.ui.border,
      textColor: theme.colors.text.secondary,
    }
  );
}

function getEventBody(event: FeedEvent) {
  return event.body || event.summary || event.short_summary || STRINGS.fallbackBody;
}

function getEventSymbol(event: FeedEvent) {
  return event.symbol || event.related_symbol || '';
}

function getEventTimestamp(event: FeedEvent) {
  return event.timestamp || event.created_at || '';
}

function matchesFilter(event: FeedEvent, activeFilter: FeedFilter) {
  const allowedTypes = FILTER_TYPES[activeFilter];
  if (!allowedTypes) return true;
  return allowedTypes.includes(event.event_type || '');
}

export default function AiFeedScreen() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FeedFilter>('all');

  const {
    loading,
    error,
    execute: fetchFeedEvents,
  } = useApi(api.getFeedEvents, { showLoading: false, showToast: false });

  const loadFeedEvents = useCallback(async () => {
    try {
      const response = await fetchFeedEvents(50);
      setEvents(Array.isArray(response) ? response : []);
    } catch (err) {
      console.error('Failed to load AI feed events:', err);
    }
  }, [fetchFeedEvents]);

  useEffect(() => {
    loadFeedEvents();

    const interval = setInterval(() => {
      loadFeedEvents();
    }, 60000);

    return () => clearInterval(interval);
  }, [loadFeedEvents]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadFeedEvents();
    setRefreshing(false);
  }, [loadFeedEvents]);

  const filteredEvents = useMemo(
    () => events.filter((event) => matchesFilter(event, activeFilter)),
    [events, activeFilter]
  );

  const renderFilterButton = (filter: FeedFilter) => {
    const isActive = activeFilter === filter;

    return (
      <TouchableOpacity
        key={filter}
        style={[styles.filterButton, isActive && styles.filterButtonActive]}
        onPress={() => setActiveFilter(filter)}
        activeOpacity={0.8}
      >
        <Text style={[styles.filterButtonText, isActive && styles.filterButtonTextActive]}>
          {STRINGS.filters[filter]}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderEvent = ({ item, index }: { item: FeedEvent; index: number }) => {
    const typeStyle = getEventTypeStyle(item.event_type);
    const symbol = getEventSymbol(item);
    const timestamp = getEventTimestamp(item);

    return (
      <AnimatedListItem index={index}>
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderLeft}>
              <Text style={styles.severityIcon}>{getSeverityIcon(item)}</Text>
              <View style={styles.headerTextBlock}>
                <View style={styles.badgesRow}>
                  <View style={[styles.typeBadge, { backgroundColor: typeStyle.backgroundColor }]}>
                    <Text style={[styles.typeBadgeText, { color: typeStyle.textColor }]}>
                      {typeStyle.label}
                    </Text>
                  </View>
                  {symbol ? (
                    <View style={styles.symbolBadge}>
                      <Text style={styles.symbolBadgeText}>{symbol}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.cardTitle} numberOfLines={2}>
                  {item.title || STRINGS.fallbackTitle}
                </Text>
              </View>
            </View>
            <Text style={styles.timestampText}>
              {timestamp ? DateFormatter.toRelativeTime(timestamp) : ''}
            </Text>
          </View>

          <Text style={styles.cardBody}>{getEventBody(item)}</Text>

          {Array.isArray(item.reason_codes) && item.reason_codes.length > 0 ? (
            <View style={styles.reasonCodeRow}>
              {item.reason_codes.slice(0, 3).map((code) => (
                <View key={code} style={styles.reasonCodeChip}>
                  <Text style={styles.reasonCodeText}>{code}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      </AnimatedListItem>
    );
  };

  if (loading && !refreshing && !events.length) {
    return (
      <PageTransition type="fade">
        <View style={styles.container}>
          <View style={styles.filterBar}>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.filterBarContent}
            >
              {renderFilterButton('all')}
              {renderFilterButton('signals')}
              {renderFilterButton('risk')}
              {renderFilterButton('auto')}
              {renderFilterButton('insights')}
            </ScrollView>
          </View>
          <SkeletonList count={5} />
        </View>
      </PageTransition>
    );
  }

  if (error && !events.length) {
    return (
      <PageTransition type="fade">
        <NoData
          title={STRINGS.errorTitle}
          description={STRINGS.errorDescription}
          onRetry={loadFeedEvents}
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition type="slideUp">
      <View style={styles.container}>
        <View style={styles.filterBar}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterBarContent}
          >
            {renderFilterButton('all')}
            {renderFilterButton('signals')}
            {renderFilterButton('risk')}
            {renderFilterButton('auto')}
            {renderFilterButton('insights')}
          </ScrollView>
        </View>

        {filteredEvents.length === 0 ? (
          <View style={styles.emptyContainer}>
            <NoData
              title={STRINGS.emptyTitle}
              description={STRINGS.emptyDescription}
              onRetry={loadFeedEvents}
            />
          </View>
        ) : (
          <FlatList
            data={filteredEvents}
            keyExtractor={(item, index) => `${item.id || item.title || 'event'}-${index}`}
            renderItem={renderEvent}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor={theme.colors.brand.primary}
              />
            }
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  filterBar: {
    paddingTop: theme.spacing.md,
    paddingBottom: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  filterBarContent: {
    paddingHorizontal: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  filterButton: {
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  filterButtonActive: {
    backgroundColor: theme.colors.brand.primary,
    borderColor: theme.colors.brand.primary,
  },
  filterButtonText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  filterButtonTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    ...theme.shadows.small,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing.sm,
  },
  cardHeaderLeft: {
    flexDirection: 'row',
    flex: 1,
    marginRight: theme.spacing.sm,
  },
  severityIcon: {
    fontSize: 20,
    marginRight: theme.spacing.sm,
    marginTop: 2,
  },
  headerTextBlock: {
    flex: 1,
  },
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.xs,
  },
  typeBadge: {
    paddingVertical: 5,
    paddingHorizontal: theme.spacing.sm,
    borderRadius: theme.borderRadius.full,
  },
  typeBadgeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
  },
  symbolBadge: {
    paddingVertical: 5,
    paddingHorizontal: theme.spacing.sm,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  symbolBadgeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  cardTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    color: theme.colors.text.primary,
    lineHeight: 22,
  },
  timestampText: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.tertiary,
    marginTop: 2,
  },
  cardBody: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
  },
  reasonCodeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing.xs,
    marginTop: theme.spacing.md,
  },
  reasonCodeChip: {
    paddingVertical: 6,
    paddingHorizontal: theme.spacing.sm,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.ui.background,
  },
  reasonCodeText: {
    fontSize: theme.typography.sizes.xs,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  emptyContainer: {
    flex: 1,
  },
});
