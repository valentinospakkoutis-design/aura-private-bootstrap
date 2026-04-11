import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Dimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';
import { Platform } from "react-native";
import * as Haptics from "expo-haptics";
import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';

const { width } = Dimensions.get('window');

interface QuickAction {
  id: string;
  title: string;
  icon: string;
  route: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: '1',
    title: 'AI Predictions',
    icon: '🤖',
    route: '/ai-predictions',
  },
  {
    id: '2',
    title: 'Voice Briefing',
    icon: '🎤',
    route: '/voice-briefing',
  },
  {
    id: '3',
    title: 'Analytics',
    icon: '📈',
    route: '/analytics',
  },
  {
    id: '4',
    title: 'Settings',
    icon: '⚙️',
    route: '/settings',
  },
];

interface PortfolioStats {
  totalValue: number;
  totalProfit: number;
  profitPercentage: number;
  openTrades: number;
  closedTrades: number;
  winRate: number;
  mode?: string;
}

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAppStore();
  const { t } = useLanguage();
  const [unreadCount, setUnreadCount] = useState(0);
  const [portfolio, setPortfolio] = useState<PortfolioStats | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);

  useEffect(() => {
    loadUnreadCount();
    loadPortfolio();
    const interval = setInterval(() => {
      loadUnreadCount();
      loadPortfolio();
    }, 30000); // Every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const loadPortfolio = async () => {
    try {
      const stats = await api.getPortfolioStats();
      if (stats && typeof stats.totalValue === 'number') {
        setPortfolio(stats);
      } else {
        setPortfolio(null);
      }
    } catch (err) {
      console.log('[Home] Portfolio load failed:', err);
      setPortfolio(null);
    } finally {
      setPortfolioLoading(false);
    }
  };

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

  const initials = (user?.name || 'AU').split(' ').map((s) => s[0]).join('').slice(0, 2).toUpperCase();

  const handleQuickAction = (route: string) => {
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    router.push({ pathname: route } as any);
  };

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>AURA</Text>
          <TouchableOpacity
            style={styles.notificationButton}
            onPress={() => router.push({ pathname: '/notifications' } as any)}
          >
            <Text style={styles.avatarText}>{initials}</Text>
            {unreadCount > 0 && (
              <View style={styles.notificationBadge}>
                <Text style={styles.notificationBadgeText}>
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        {/* Portfolio Summary */}
        <AnimatedCard delay={0} animationType="scale">
          {portfolioLoading ? (
            <View style={styles.portfolioEmpty}>
              <Text style={styles.portfolioEmptyText}>Φόρτωση portfolio...</Text>
            </View>
          ) : portfolio && portfolio.totalValue > 0 ? (
            <TouchableOpacity activeOpacity={0.8} onPress={() => router.push('/analytics')}>
              <View style={styles.portfolioCard}>
                <Text style={styles.portfolioLabel}>{t('totalPortfolioValue')}</Text>
                <Text style={styles.portfolioValue}>
                  ${portfolio.totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Text>
                <View style={styles.portfolioPnlRow}>
                  <Text style={[
                    styles.portfolioPnl,
                    { color: portfolio.profitPercentage >= 0 ? theme.colors.market.bullish : theme.colors.market.bearish }
                  ]}>
                    {portfolio.profitPercentage >= 0 ? '+' : '-'}${Math.abs(portfolio.totalProfit || 0).toFixed(2)} ({portfolio.profitPercentage >= 0 ? '+' : ''}{portfolio.profitPercentage.toFixed(2)}%)
                  </Text>
                </View>
                <View style={styles.chartPlaceholder}>
                  <View style={styles.chartLine} />
                </View>
              </View>
              <View style={styles.statsRow}>
                <View style={styles.statItem}>
                  <Text style={styles.statLabel}>{t('openTrades')}</Text>
                  <Text style={styles.statValue}>{portfolio.openTrades}</Text>
                </View>
                <View style={styles.statDivider} />
                <View style={styles.statItem}>
                  <Text style={styles.statLabel}>{t('closedTrades')}</Text>
                  <Text style={styles.statValue}>{portfolio.closedTrades}</Text>
                </View>
                <View style={styles.statDivider} />
                <View style={styles.statItem}>
                  <Text style={styles.statLabel}>Win Rate</Text>
                  <Text style={styles.statValue}>{portfolio.winRate.toFixed(0)}%</Text>
                </View>
              </View>
            </TouchableOpacity>
          ) : (
            <View style={styles.portfolioEmpty}>
              <Text style={styles.portfolioEmptyIcon}>📊</Text>
              <Text style={styles.portfolioEmptyText}>
                {t('connectBrokerPrompt')}
              </Text>
              <TouchableOpacity
                style={styles.portfolioEmptyButton}
                onPress={() => router.push('/settings')}
              >
                <Text style={styles.portfolioEmptyButtonText}>Ρυθμίσεις →</Text>
              </TouchableOpacity>
            </View>
          )}
        </AnimatedCard>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>{t('quickActions')}</Text>
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
                <Text style={styles.actionIcon}>{action.icon}</Text>
                <Text style={styles.actionTitle}>{action.title}</Text>
              </TouchableOpacity>
            </AnimatedCard>
          ))}
        </View>

        {/* Recent Activity */}
        <AnimatedCard delay={500} animationType="slideUp">
          <View style={styles.activityHeader}>
            <Text style={styles.sectionTitle}>Πρόσφατη Δραστηριότητα</Text>
            <TouchableOpacity onPress={() => router.push({ pathname: '/notifications' } as any)}>
              <Text style={styles.viewAllButton}>Όλες →</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.activityItem}>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>Νέο Trade: BTC/USD</Text>
              <Text style={styles.activityDescription}>Αγορά στα $42,500</Text>
              <Text style={styles.activityTime}>Πριν 2 ώρες</Text>
            </View>
          </View>

          <View style={styles.activityItem}>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>AI Prediction: ETH/USD</Text>
              <Text style={styles.activityDescription}>Bullish signal - 85% confidence</Text>
              <Text style={styles.activityTime}>Πριν 4 ώρες</Text>
            </View>
          </View>

          <View style={styles.activityItem}>
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
    marginBottom: theme.spacing.lg,
  },
  logo: {
    fontSize: theme.typography.sizes.h3,
    fontWeight: '700',
    color: theme.colors.text.primary,
    letterSpacing: 0.8,
  },
  notificationButton: {
    position: 'relative',
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
    color: theme.colors.text.primary,
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
  portfolioCard: {
    alignItems: 'center',
    paddingVertical: theme.spacing.md,
    paddingBottom: theme.spacing.sm,
  },
  portfolioLabel: {
    fontSize: theme.typography.sizes.small,
    color: theme.colors.text.tertiary,
    marginBottom: theme.spacing.xs,
  },
  portfolioValue: {
    fontSize: theme.typography.sizes.hero,
    fontWeight: '700',
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
    textAlign: 'center',
  },
  portfolioPnlRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing.xs,
  },
  portfolioPnl: {
    fontSize: theme.typography.sizes.body,
    fontWeight: '600',
    fontFamily: theme.typography.fontFamily.mono,
  },
  chartPlaceholder: {
    marginTop: theme.spacing.md,
    width: '100%',
    height: 46,
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    justifyContent: 'center',
    paddingHorizontal: theme.spacing.md,
    backgroundColor: theme.colors.ui.background,
  },
  chartLine: {
    height: 2,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.brand.primary,
    opacity: 0.35,
  },
  portfolioEmpty: {
    alignItems: 'center',
    paddingVertical: theme.spacing.xl,
  },
  portfolioEmptyIcon: {
    fontSize: 48,
    marginBottom: theme.spacing.md,
  },
  portfolioEmptyText: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
  portfolioEmptyButton: {
    marginTop: theme.spacing.md,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.medium,
    backgroundColor: theme.colors.brand.primary + '20',
  },
  portfolioEmptyButtonText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.brand.primary,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.h3,
    fontWeight: '600',
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
    fontSize: theme.typography.sizes.micro,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
    textAlign: 'center',
  },
  statValue: {
    fontSize: theme.typography.sizes.h3,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: 0,
  },
  statDivider: {
    width: 1,
    height: 40,
    backgroundColor: theme.colors.ui.border,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.lg,
  },
  actionCard: {
    width: (width - theme.spacing.md * 2 - theme.spacing.xs) / 2,
    padding: 0,
  },
  actionButton: {
    padding: theme.spacing.md,
    minHeight: 88,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionIcon: {
    fontSize: 24,
    marginBottom: theme.spacing.xs,
  },
  actionTitle: {
    fontSize: theme.typography.sizes.small,
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
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
    marginBottom: theme.spacing.xs,
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

