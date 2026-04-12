import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Share, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';

import { api } from '../mobile/src/services/apiClient';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { useAppStore } from '../mobile/src/stores/appStore';
import { theme } from '../mobile/src/constants/theme';

interface ReferralStats {
  code: string;
  total_referrals: number;
  rewards_earned: number;
  share_url: string;
}

interface ReferralError {
  message?: string;
  response?: {
    data?: {
      detail?: string;
    };
  };
}

export default function ReferralScreen() {
  const { t } = useLanguage();
  const { showToast } = useAppStore();

  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [inputCode, setInputCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getReferralStats();
      setStats(data || null);
    } catch (err) {
      const error = err as ReferralError;
      showToast(error.message || t('error'), 'error');
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const shareMessage = useMemo(() => {
    const code = stats?.code || 'AURA0000';
    const url = stats?.share_url || 'https://aura-app.com/join';
    return (
      `Χρησιμοποίησε τον κωδικό ${code}\n` +
      `και ξεκίνα να trade με AI!\n` +
      `${url}`
    );
  }, [stats]);

  const handleShare = useCallback(async () => {
    try {
      await Share.share({ message: shareMessage });
    } catch {
      showToast(t('error'), 'error');
    }
  }, [shareMessage, showToast, t]);

  const handleCopyFallback = useCallback(async () => {
    try {
      await Clipboard.setStringAsync(stats?.code || '');
      showToast('Referral code copied', 'success');
    } catch {
      showToast(t('error'), 'error');
    }
  }, [showToast, stats?.code, t]);

  const handleApply = useCallback(async () => {
    const trimmed = inputCode.trim();
    if (!trimmed) {
      showToast('Referral code is required', 'warning');
      return;
    }
    setApplying(true);
    try {
      const result = await api.applyReferralCode(trimmed);
      showToast(result?.message || 'Referral applied!', 'success');
      setInputCode('');
      await loadStats();
    } catch (err) {
      const error = err as ReferralError;
      showToast(error.response?.data?.detail || error.message || 'Failed to apply referral code', 'error');
    } finally {
      setApplying(false);
    }
  }, [inputCode, loadStats, showToast]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t('referFriends')}</Text>
      <Text style={styles.subtitle}>{t('referralReward')}</Text>

      <View style={styles.card}>
        <Text style={styles.label}>{t('referralCode')}</Text>
        <View style={styles.codeRow}>
          <Text style={styles.code}>{stats?.code || '--------'}</Text>
          <TouchableOpacity style={styles.smallBtn} onPress={handleCopyFallback}>
            <Text style={styles.smallBtnText}>Copy</Text>
          </TouchableOpacity>
        </View>
        <TouchableOpacity style={styles.shareBtn} onPress={handleShare}>
          <Text style={styles.shareBtnText}>Share</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.statsText}>
          {stats?.total_referrals ?? 0} {t('friendsReferred')} | {stats?.rewards_earned ?? 0} μήνες PRO κερδισμένα
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Έχεις referral code;</Text>
        <TextInput
          value={inputCode}
          onChangeText={setInputCode}
          autoCapitalize="characters"
          placeholder="ABCD1234"
          placeholderTextColor={theme.colors.text.secondary}
          style={styles.input}
        />
        <TouchableOpacity style={[styles.shareBtn, applying && styles.btnDisabled]} onPress={handleApply} disabled={applying}>
          <Text style={styles.shareBtnText}>{applying ? t('loading') : 'Apply code'}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.howTitle}>Πώς λειτουργεί</Text>
        <Text style={styles.howLine}>1. Μοιράσου τον κωδικό σου</Text>
        <Text style={styles.howLine}>2. Φίλος κατεβάζει το AURA</Text>
        <Text style={styles.howLine}>3. Κερδίζεις 1 μήνα PRO!</Text>
      </View>

      {loading && <Text style={styles.loading}>{t('loading')}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
    padding: theme.spacing.md,
    gap: theme.spacing.md,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: theme.colors.text.primary,
  },
  subtitle: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    padding: theme.spacing.md,
  },
  label: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
    marginBottom: theme.spacing.xs,
  },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: theme.spacing.sm,
  },
  code: {
    fontSize: 26,
    fontFamily: theme.typography.fontFamily.mono,
    fontWeight: '700',
    color: theme.colors.brand.primary,
    letterSpacing: 2,
  },
  smallBtn: {
    backgroundColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
  },
  smallBtnText: {
    color: theme.colors.text.primary,
    fontWeight: '700',
  },
  shareBtn: {
    marginTop: theme.spacing.xs,
    backgroundColor: theme.colors.brand.primary,
    borderRadius: theme.borderRadius.md,
    alignItems: 'center',
    paddingVertical: theme.spacing.sm,
  },
  shareBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: theme.typography.sizes.md,
  },
  statsText: {
    color: theme.colors.text.primary,
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
  },
  input: {
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    color: theme.colors.text.primary,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    fontFamily: theme.typography.fontFamily.mono,
    marginBottom: theme.spacing.sm,
  },
  btnDisabled: {
    opacity: 0.6,
  },
  howTitle: {
    color: theme.colors.text.primary,
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    marginBottom: theme.spacing.xs,
  },
  howLine: {
    color: theme.colors.text.secondary,
    fontSize: theme.typography.sizes.sm,
    marginBottom: 4,
  },
  loading: {
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
});
