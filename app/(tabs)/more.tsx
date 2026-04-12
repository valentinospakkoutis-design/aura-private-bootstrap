import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../../mobile/src/constants/theme';
import { useLanguage } from '../../mobile/src/hooks/useLanguage';

export default function MoreScreen() {
  const router = useRouter();
  const { t } = useLanguage();

  const MORE_ITEMS = [
    { icon: '🏆', title: t('leaderboard'), href: '/leaderboard' },
    { icon: '👥', title: t('referFriends'), href: '/referral' },
    { icon: '📊', title: t('analytics'), href: '/analytics' },
    { icon: '🎯', title: t('aiAccuracyTitle'), href: '/ai-accuracy' },
    { icon: '🧪', title: t('simulationTitle'), href: '/simulation' },
    { icon: '🔗', title: t('brokers'), href: '/brokers' },
    { icon: '👤', title: t('profile'), href: '/profile' },
    { icon: '🔔', title: t('notifications'), href: '/notifications' },
    { icon: '🎙️', title: t('voiceBriefing'), href: '/voice-briefing' },
    { icon: '📊', title: t('weeklyReportTitle'), href: '/weekly-report' },
    { icon: '🏆', title: t('achievements'), href: '/achievements' },
    { icon: '💎', title: t('subscriptionTitle'), href: '/subscription' },
    { icon: '📝', title: t('paperTrading'), href: '/paper-trading' },
    { icon: '💰', title: 'Live Trading', href: '/live-trading' },
    { icon: '📉', title: t('futures'), href: '/futures-trading' },
    { icon: '🟡', title: t('bybitFutures'), href: '/bybit-trading' },
    { icon: '⚙️', title: t('settings'), href: '/settings' },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>More</Text>
      {MORE_ITEMS.map((item) => (
        <TouchableOpacity
          key={item.href}
          style={styles.item}
          onPress={() => router.push({ pathname: item.href } as any)}
          activeOpacity={0.7}
        >
          <Text style={styles.icon}>{item.icon}</Text>
          <Text style={styles.label}>{item.title}</Text>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>
      ))}
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
    marginBottom: theme.spacing.xl,
    marginTop: theme.spacing.lg,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.ui.cardBackground,
    padding: theme.spacing.lg,
    borderRadius: theme.borderRadius.xlarge,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  icon: {
    fontSize: 24,
    marginRight: theme.spacing.md,
  },
  label: {
    flex: 1,
    fontSize: theme.typography.sizes.lg,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  arrow: {
    fontSize: 18,
    color: theme.colors.text.secondary,
  },
});
