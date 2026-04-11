import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { useAppStore } from '../mobile/src/stores/appStore';
import { theme } from '../mobile/src/constants/theme';

interface Achievement {
  id: string;
  title_el: string;
  title_en: string;
  desc_el: string;
  desc_en: string;
  icon: string;
  earned_at?: string | null;
}

export default function AchievementsScreen() {
  const { t, language } = useLanguage();
  const { showToast } = useAppStore();
  const [earned, setEarned] = useState<Achievement[]>([]);
  const [locked, setLocked] = useState<Achievement[]>([]);
  const [total, setTotal] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const res = await api.getAchievements();
      setEarned(Array.isArray(res?.earned) ? res.earned : []);
      setLocked(Array.isArray(res?.locked) ? res.locked : []);
      setTotal(Number(res?.total || 0));
    } catch (err) {
      showToast(t('error'), 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const titleFor = (a: Achievement) => (language === 'el' ? a.title_el : a.title_en);
  const descFor = (a: Achievement) => (language === 'el' ? a.desc_el : a.desc_en);

  const allCards: Array<{ item: Achievement; earned: boolean }> = [
    ...earned.map((item) => ({ item, earned: true })),
    ...locked.map((item) => ({ item, earned: false })),
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.header}>{t('achievementsProgress', { earned: String(earned.length), total: String(total || 8) })}</Text>

      {loading ? (
        <Text style={styles.subtle}>{t('loading')}</Text>
      ) : (
        <View style={styles.grid}>
          {allCards.map(({ item, earned: isEarned }) => (
            <View key={item.id} style={[styles.card, !isEarned && styles.cardLocked]}>
              <Text style={[styles.icon, !isEarned && styles.iconLocked]}>{item.icon}</Text>
              <Text style={styles.title}>{isEarned ? titleFor(item) : t('achievementLockedTitle')}</Text>
              <Text style={styles.desc}>{isEarned ? descFor(item) : t('achievementLockedDesc')}</Text>
              {isEarned && item.earned_at ? (
                <Text style={styles.date}>
                  {t('achievementEarnedAt')}: {new Date(item.earned_at).toLocaleDateString(language === 'el' ? 'el-GR' : 'en-US')}
                </Text>
              ) : null}
            </View>
          ))}
        </View>
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
    paddingBottom: theme.spacing.xl,
  },
  header: {
    fontSize: 24,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  subtle: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.md,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: theme.spacing.sm,
  },
  card: {
    width: '48%',
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  cardLocked: {
    opacity: 0.65,
  },
  icon: {
    fontSize: 26,
    marginBottom: theme.spacing.xs,
  },
  iconLocked: {
    color: theme.colors.text.tertiary,
  },
  title: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: 4,
  },
  desc: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  date: {
    marginTop: theme.spacing.xs,
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.tertiary,
  },
});
