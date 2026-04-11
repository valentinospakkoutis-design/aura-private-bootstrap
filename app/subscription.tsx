import React, { useCallback, useEffect, useState } from 'react';

import { View, Text, StyleSheet, ScrollView, TouchableOpacity, RefreshControl } from 'react-native';

import { api } from '../mobile/src/services/apiClient';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { theme } from '../mobile/src/constants/theme';
import { Button } from '../mobile/src/components/Button';

type Tier = 'free' | 'pro' | 'elite';

interface SubscriptionStatus {
  tier: Tier;
  is_active: boolean;
  daily_prediction_limit?: number | null;
  features?: {
    live_trading?: boolean;
    auto_trading?: boolean;
    dca_strategy?: boolean;
    claude_validation?: boolean;
    unlimited_predictions?: boolean;
  };
}

const PLAN_ORDER: Tier[] = ['free', 'pro', 'elite'];

export default function SubscriptionScreen() {
  const { t } = useLanguage();
  const { showToast } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [upgradingTier, setUpgradingTier] = useState<Tier | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const data = await api.getSubscriptionStatus();
      setStatus(data);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || t('subscriptionLoadError');
      showToast(typeof msg === 'string' ? msg : t('subscriptionLoadError'), 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleUpgrade = useCallback(async (tier: Tier) => {
    if (tier === 'free') return;
    try {
      setUpgradingTier(tier);
      await api.upgradeSubscription(tier);
      showToast(t('subscriptionUpgradeSuccess', { tier: tier.toUpperCase() }), 'success');
      await loadStatus();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || t('subscriptionUpgradeError');
      showToast(typeof msg === 'string' ? msg : t('subscriptionUpgradeError'), 'error');
    } finally {
      setUpgradingTier(null);
    }
  }, [loadStatus, showToast, t]);

  const currentTier = (status?.tier || 'free') as Tier;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadStatus(); }} />}
    >
      <View style={styles.headerCard}>
        <Text style={styles.headerTitle}>{t('subscriptionTitle')}</Text>
        <Text style={styles.headerSubtitle}>{t('currentPlan')}: {currentTier.toUpperCase()}</Text>
        {typeof status?.daily_prediction_limit === 'number' && (
          <Text style={styles.limitText}>{t('freeDailyLimit', { limit: String(status.daily_prediction_limit) })}</Text>
        )}
      </View>

      {PLAN_ORDER.map((tier) => {
        const isCurrent = tier === currentTier;
        const canUpgrade = tier !== 'free' && PLAN_ORDER.indexOf(tier) > PLAN_ORDER.indexOf(currentTier);

        return (
          <View key={tier} style={[styles.planCard, isCurrent && styles.planCardActive]}>
            <View style={styles.planHeader}>
              <Text style={styles.planName}>{tier.toUpperCase()}</Text>
              {isCurrent && <Text style={styles.currentBadge}>{t('currentPlanBadge')}</Text>}
            </View>

            <Text style={styles.planLine}>• {t(`plan_${tier}_line1`)}</Text>
            <Text style={styles.planLine}>• {t(`plan_${tier}_line2`)}</Text>
            <Text style={styles.planLine}>• {t(`plan_${tier}_line3`)}</Text>

            {canUpgrade ? (
              <Button
                title={t('upgradeTo', { tier: tier.toUpperCase() })}
                loading={upgradingTier === tier}
                onPress={() => handleUpgrade(tier)}
                fullWidth
              />
            ) : (
              <TouchableOpacity style={styles.disabledButton} activeOpacity={1}>
                <Text style={styles.disabledButtonText}>{isCurrent ? t('currentPlanBadge') : t('included')}</Text>
              </TouchableOpacity>
            )}
          </View>
        );
      })}

      <View style={styles.featuresCard}>
        <Text style={styles.featuresTitle}>{t('featuresByPlan')}</Text>
        <Text style={styles.featureLine}>• {t('liveTrading')}: {status?.features?.live_trading ? '✓' : '✕'}</Text>
        <Text style={styles.featureLine}>• {t('autoTrading')}: {status?.features?.auto_trading ? '✓' : '✕'}</Text>
        <Text style={styles.featureLine}>• DCA: {status?.features?.dca_strategy ? '✓' : '✕'}</Text>
        <Text style={styles.featureLine}>• Claude AI: {status?.features?.claude_validation ? '✓' : '✕'}</Text>
      </View>

      {loading && <Text style={styles.loading}>{t('loading')}</Text>}
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
    gap: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  headerCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
  },
  headerTitle: {
    fontSize: theme.typography.sizes.xl,
    color: theme.colors.text.primary,
    fontWeight: '700',
    marginBottom: theme.spacing.xs,
  },
  headerSubtitle: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  limitText: {
    marginTop: theme.spacing.sm,
    color: theme.colors.semantic.warning,
    fontSize: theme.typography.sizes.sm,
  },
  planCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    gap: theme.spacing.sm,
  },
  planCardActive: {
    borderColor: theme.colors.brand.primary,
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  planName: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  currentBadge: {
    backgroundColor: theme.colors.brand.primary,
    color: '#fff',
    fontSize: theme.typography.sizes.xs,
    fontWeight: '700',
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 4,
    borderRadius: 999,
  },
  planLine: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
  },
  disabledButton: {
    marginTop: theme.spacing.sm,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  disabledButtonText: {
    color: theme.colors.text.secondary,
    fontWeight: '600',
  },
  featuresCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    gap: theme.spacing.xs,
  },
  featuresTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  featureLine: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
  },
  loading: {
    textAlign: 'center',
    color: theme.colors.text.secondary,
  },
});
