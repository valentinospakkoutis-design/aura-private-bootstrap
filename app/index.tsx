import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Dimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedOrb } from '../mobile/src/components/AnimatedOrb';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';
import { Platform } from "react-native";
import * as Haptics from "expo-haptics";
import { api } from '../mobile/src/services/apiClient';

const { width } = Dimensions.get('window');

interface QuickAction {
  id: string;
  title: string;
  icon: string;
  route: string;
  color: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: '1',
    title: 'AI Predictions',
    icon: '🤖',
    route: '/ai-predictions',
    color: theme.colors.brand.primary,
  },
  {
    id: '2',
    title: 'Paper Trading',
    icon: '📊',
    route: '/paper-trading',
    color: theme.colors.market.bullish,
  },
  {
    id: '3',
    title: 'Live Trading',
    icon: '💰',
    route: '/live-trading',
    color: theme.colors.semantic.warning,
  },
  {
    id: '4',
    title: 'Voice Briefing',
    icon: '🎙️',
    route: '/voice-briefing',
    color: theme.colors.brand.secondary,
  },
  {
    id: '5',
    title: 'Analytics',
    icon: '📈',
    route: '/analytics',
    color: theme.colors.accent.purple,
  },
  {
    id: '6',
    title: 'Settings',
    icon: '⚙️',
    route: '/settings',
    color: theme.colors.text.secondary,
  },
];

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAppStore();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    loadUnreadCount();
    const interval = setInterval(() => {
      loadUnreadCount();
    }, 30000); // Every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const loadUnreadCount = async () => {
    try {
      const notifications = await api.getNotifications();
      const unread = Array.isArray(notifications) 
        ? notifications.filter((n: any) => !n.read).length 
        : 0;
      setUnreadCount(unread);
    } catch (err) {
      console.error('Error loading unread count:', err);
      setUnreadCount(0);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Καλημέρα';
    if (hour < 18) return 'Καλησπέρα';
    return 'Καληνύχτα';
  };

  const handleQuickAction = (route: string) => {
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    router.push(route as any);
  };

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>{getGreeting()},</Text>
            <Text style={styles.userName}>{user?.name || 'Χρήστη'}! 👋</Text>
          </View>
          <TouchableOpacity
            style={styles.notificationButton}
            onPress={() => router.push('/notifications')}
          >
            <Text style={styles.notificationIcon}>🔔</Text>
            {unreadCount > 0 && (
              <View style={styles.notificationBadge}>
                <Text style={styles.notificationBadgeText}>
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        {/* Animated Orb */}
        <AnimatedCard delay={0} animationType="scale">
          <View style={styles.orbContainer}>
            <AnimatedOrb state="calm" size={width * 0.5} />
            <Text style={styles.orbTitle}>Το AURA σου είναι έτοιμο</Text>
            <Text style={styles.orbDescription}>
              Το AI αναλύει τις αγορές 24/7 για εσένα
            </Text>
          </View>
        </AnimatedCard>

        {/* Quick Stats */}
        <AnimatedCard delay={100} animationType="slideUp">
          <Text style={styles.sectionTitle}>📊 Σήμερα</Text>
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Portfolio</Text>
              <AnimatedCounter
                value={12450.75}
                decimals={2}
                prefix="$"
                style={styles.statValue}
              />
              <Text style={[styles.statChange, { color: theme.colors.market.bullish }]}>
                +2.5%
              </Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>Ανοιχτά Trades</Text>
              <Text style={styles.statValue}>5</Text>
              <Text style={styles.statChange}>3 winning</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statLabel}>AI Predictions</Text>
              <Text style={styles.statValue}>12</Text>
              <Text style={styles.statChange}>νέες σήμερα</Text>
            </View>
          </View>
        </AnimatedCard>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>⚡ Γρήγορες Ενέργειες</Text>
        <View style={styles.actionsGrid}>
          {QUICK_ACTIONS.map((action, index) => (
            <AnimatedCard
              key={action.id}
              delay={200 + index * 50}
              animationType="scale"
              style={styles.actionCard}
            >
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => handleQuickAction(action.route)}
                activeOpacity={0.7}
              >
                <View style={[styles.actionIconContainer, { backgroundColor: action.color + '20' }]}>
                  <Text style={styles.actionIcon}>{action.icon}</Text>
                </View>
                <Text style={styles.actionTitle}>{action.title}</Text>
              </TouchableOpacity>
            </AnimatedCard>
          ))}
        </View>

        {/* Recent Activity */}
        <AnimatedCard delay={500} animationType="slideUp">
          <View style={styles.activityHeader}>
            <Text style={styles.sectionTitle}>🕐 Πρόσφατη Δραστηριότητα</Text>
            <TouchableOpacity onPress={() => router.push('/notifications')}>
              <Text style={styles.viewAllButton}>Όλες →</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.activityItem}>
            <Text style={styles.activityIcon}>💰</Text>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>Νέο Trade: BTC/USD</Text>
              <Text style={styles.activityDescription}>Αγορά στα $42,500</Text>
              <Text style={styles.activityTime}>Πριν 2 ώρες</Text>
            </View>
          </View>

          <View style={styles.activityItem}>
            <Text style={styles.activityIcon}>🤖</Text>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>AI Prediction: ETH/USD</Text>
              <Text style={styles.activityDescription}>Bullish signal - 85% confidence</Text>
              <Text style={styles.activityTime}>Πριν 4 ώρες</Text>
            </View>
          </View>

          <View style={styles.activityItem}>
            <Text style={styles.activityIcon}>🎙️</Text>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>Voice Briefing Ready</Text>
              <Text style={styles.activityDescription}>Το ημερήσιο briefing σου είναι έτοιμο</Text>
              <Text style={styles.activityTime}>Πριν 6 ώρες</Text>
            </View>
          </View>
        </AnimatedCard>

        <View style={styles.bottomPadding} />
      </ScrollView>
    </PageTransition>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.xl,
  },
  greeting: {
    fontSize: theme.typography.sizes.lg,
    color: theme.colors.text.secondary,
  },
  userName: {
    fontSize: theme.typography.sizes['3xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  notificationButton: {
    position: 'relative',
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: theme.colors.ui.cardBackground,
    justifyContent: 'center',
    alignItems: 'center',
  },
  notificationIcon: {
    fontSize: 24,
  },
  notificationBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: theme.colors.semantic.error,
    justifyContent: 'center',
    alignItems: 'center',
  },
  notificationBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  orbContainer: {
    alignItems: 'center',
    paddingVertical: theme.spacing.lg,
  },
  orbTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginTop: theme.spacing.md,
    textAlign: 'center',
  },
  orbDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.xs,
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statLabel: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
    textAlign: 'center',
  },
  statValue: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  statChange: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  statDivider: {
    width: 1,
    height: 40,
    backgroundColor: theme.colors.ui.border,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.lg,
  },
  actionCard: {
    width: (width - theme.spacing.md * 2 - theme.spacing.sm) / 2,
    padding: 0,
  },
  actionButton: {
    padding: theme.spacing.lg,
    alignItems: 'center',
  },
  actionIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  actionIcon: {
    fontSize: 32,
  },
  actionTitle: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    textAlign: 'center',
  },
  activityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  viewAllButton: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.brand.primary,
  },
  activityItem: {
    flexDirection: 'row',
    padding: theme.spacing.md,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.medium,
    marginBottom: theme.spacing.sm,
  },
  activityIcon: {
    fontSize: 32,
    marginRight: theme.spacing.md,
  },
  activityContent: {
    flex: 1,
  },
  activityTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  activityDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  activityTime: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
});

