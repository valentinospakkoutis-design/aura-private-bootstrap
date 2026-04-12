import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { useAppStore } from '../mobile/src/stores/appStore';
import { theme } from '../mobile/src/constants/theme';

interface LeaderboardRow {
  display_name: string;
  paper_pnl_pct: number;
  paper_trades: number;
  win_rate: number;
  rank: number;
}

type LeaderboardPeriod = 'weekly' | 'monthly' | 'alltime';

const PERIODS: Array<{ key: LeaderboardPeriod; icon: string }> = [
  { key: 'weekly', icon: '🗓️' },
  { key: 'monthly', icon: '📆' },
  { key: 'alltime', icon: '⏳' },
];

export default function LeaderboardScreen() {
  const { t } = useLanguage();
  const { showToast } = useAppStore();

  const [period, setPeriod] = useState<LeaderboardPeriod>('weekly');
  const [rankings, setRankings] = useState<LeaderboardRow[]>([]);
  const [myRank, setMyRank] = useState<number | null>(null);
  const [myDisplayName, setMyDisplayName] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadLeaderboard = useCallback(async (selected: LeaderboardPeriod) => {
    try {
      const data = await api.getLeaderboard(selected, 50);
      setRankings(Array.isArray(data?.rankings) ? data.rankings : []);
      setMyRank(typeof data?.my_rank === 'number' ? data.my_rank : null);
      setMyDisplayName(typeof data?.my_display_name === 'string' ? data.my_display_name : '');
    } catch (err: any) {
      showToast(err?.message || t('error'), 'error');
      setRankings([]);
      setMyRank(null);
    } finally {
      setLoading(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    setLoading(true);
    loadLeaderboard(period);
  }, [period, loadLeaderboard]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadLeaderboard(period);
    setRefreshing(false);
  }, [period, loadLeaderboard]);

  const topThree = rankings.slice(0, 3);
  const rest = rankings.slice(3);

  const podiumEmoji = (rank: number) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    return '🥉';
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.title}>{t('leaderboard')}</Text>

      <View style={styles.tabsWrap}>
        {PERIODS.map((item) => {
          const active = period === item.key;
          const label = item.key === 'weekly' ? t('weekly') : item.key === 'monthly' ? t('monthly') : t('allTime');
          return (
            <TouchableOpacity
              key={item.key}
              style={[styles.tab, active && styles.tabActive]}
              onPress={() => setPeriod(item.key)}
              activeOpacity={0.8}
            >
              <Text style={styles.tabIcon}>{item.icon}</Text>
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {!!myDisplayName && (
        <View style={styles.myCard}>
          <Text style={styles.myLabel}>{t('myRank')}</Text>
          <Text style={styles.myValue}>#{myRank || '-'} • {myDisplayName}</Text>
        </View>
      )}

      {loading ? (
        <Text style={styles.loading}>{t('loading')}</Text>
      ) : (
        <>
          <View style={styles.podiumWrap}>
            {topThree.map((row) => (
              <View key={`${row.rank}-${row.display_name}`} style={styles.podiumCard}>
                <Text style={styles.podiumEmoji}>{podiumEmoji(row.rank)}</Text>
                <Text style={styles.podiumName}>{row.display_name}</Text>
                <Text style={[styles.podiumPnl, { color: row.paper_pnl_pct >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                  {row.paper_pnl_pct >= 0 ? '+' : ''}{row.paper_pnl_pct.toFixed(2)}%
                </Text>
              </View>
            ))}
          </View>

          <View style={styles.listCard}>
            {rest.map((row) => {
              const isMe = !!myDisplayName && row.display_name === myDisplayName;
              return (
                <View key={`${row.rank}-${row.display_name}`} style={[styles.row, isMe && styles.rowMe]}>
                  <Text style={styles.rank}>#{row.rank}</Text>
                  <View style={styles.rowBody}>
                    <Text style={styles.name}>{row.display_name}</Text>
                    <Text style={styles.meta}>{row.paper_trades} trades • WR {row.win_rate.toFixed(1)}%</Text>
                  </View>
                  <Text style={[styles.pnl, { color: row.paper_pnl_pct >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }]}>
                    {row.paper_pnl_pct >= 0 ? '+' : ''}{row.paper_pnl_pct.toFixed(2)}%
                  </Text>
                </View>
              );
            })}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  tabsWrap: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.md,
  },
  tab: {
    flex: 1,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    backgroundColor: theme.colors.ui.cardBackground,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  tabActive: {
    borderColor: theme.colors.brand.primary,
    backgroundColor: theme.colors.brand.primary + '1a',
  },
  tabIcon: {
    fontSize: 16,
    marginBottom: 2,
  },
  tabLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    fontWeight: '600',
  },
  tabLabelActive: {
    color: theme.colors.brand.primary,
  },
  myCard: {
    backgroundColor: '#7c3aed22',
    borderColor: '#7c3aed66',
    borderWidth: 1,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.md,
  },
  myLabel: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.xs,
    marginBottom: 4,
  },
  myValue: {
    color: '#6d28d9',
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
  },
  loading: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.md,
    textAlign: 'center',
    marginVertical: theme.spacing.xl,
  },
  podiumWrap: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.md,
  },
  podiumCard: {
    flex: 1,
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    padding: theme.spacing.md,
    alignItems: 'center',
  },
  podiumEmoji: {
    fontSize: 28,
    marginBottom: 4,
  },
  podiumName: {
    color: theme.colors.text.primary,
    fontWeight: '700',
    fontSize: theme.typography.sizes.sm,
    marginBottom: 4,
  },
  podiumPnl: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
  },
  listCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  rowMe: {
    backgroundColor: '#7c3aed14',
  },
  rank: {
    width: 42,
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
  },
  rowBody: {
    flex: 1,
  },
  name: {
    color: theme.colors.text.primary,
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
  },
  meta: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.xs,
    marginTop: 2,
  },
  pnl: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    fontFamily: theme.typography.fontFamily.mono,
  },
});
