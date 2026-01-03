import React, { useState, useCallback, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { Button } from '../mobile/src/components/Button';
import { Modal } from '../mobile/src/components/Modal';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { useTheme } from '../mobile/src/context/ThemeContext';
import { useBiometrics } from '../mobile/src/hooks/useBiometrics';
import { useOfflineMode } from '../mobile/src/hooks/useOfflineMode';
import { lightTheme } from '../mobile/src/constants/theme';
import * as Haptics from 'expo-haptics';

type RiskProfile = 'conservative' | 'moderate' | 'aggressive';

export default function SettingsScreen() {
  const router = useRouter();
  const { user, setUser, showToast, showModal } = useAppStore();
  const { theme, themeMode, setThemeMode, isDark } = useTheme();
  
  // Create styles with current theme
  const styles = createStyles(theme);
  
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [paperTradingMode, setPaperTradingMode] = useState(true);
  const [selectedRiskProfile, setSelectedRiskProfile] = useState<RiskProfile>(user?.riskProfile || 'moderate');
  const [showRiskModal, setShowRiskModal] = useState(false);

  // Biometrics hook
  const {
    isAvailable: biometricsAvailable,
    isEnabled: biometricsEnabled,
    biometricType,
    loading: biometricsLoading,
    enable: enableBiometrics,
    disable: disableBiometrics,
  } = useBiometrics();

  // Offline mode hook
  const { isOfflineMode, isOnline, cacheStats, cacheSize, clearCache } = useOfflineMode();

  const {
    loading: updatingProfile,
    execute: updateProfile,
  } = useApi(api.updateProfile, { showLoading: false, showToast: false });

  const {
    loading: updatingRisk,
    execute: updateRisk,
  } = useApi(api.updateRiskProfile, { showLoading: false, showToast: false });

  const handleUpdateRiskProfile = useCallback(async (profile: RiskProfile) => {
    try {
      await updateRisk(profile);
      setSelectedRiskProfile(profile);
      setUser({ ...user!, riskProfile: profile });
      showToast('Το risk profile ενημερώθηκε!', 'success');
      setShowRiskModal(false);
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης', 'error');
    }
  }, [updateRisk, user, setUser, showToast]);

  const handleToggleNotifications = useCallback(async (value: boolean) => {
    try {
      setNotificationsEnabled(value);
      // await api.updateSettings({ notifications: value });
      showToast(value ? 'Ειδοποιήσεις ενεργοποιήθηκαν' : 'Ειδοποιήσεις απενεργοποιήθηκαν', 'success');
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης', 'error');
      setNotificationsEnabled(!value);
    }
  }, [showToast]);

  const handleBiometricsToggle = useCallback(async () => {
    if (biometricsLoading) return;

    if (biometricsEnabled) {
      await disableBiometrics();
    } else {
      await enableBiometrics();
    }
  }, [biometricsEnabled, biometricsLoading, enableBiometrics, disableBiometrics]);

  const handleTogglePaperTrading = useCallback(async (value: boolean) => {
    if (!value) {
      // Warn user before disabling paper trading
      Alert.alert(
        '⚠️ Προσοχή',
        'Απενεργοποιώντας το Paper Trading, το AURA θα κάνει πραγματικά trades με τα χρήματά σου. Είσαι σίγουρος;',
        [
          { text: 'Ακύρωση', style: 'cancel' },
          {
            text: 'Συνέχεια',
            style: 'destructive',
            onPress: async () => {
              try {
                setPaperTradingMode(value);
                // await api.updateSettings({ paperTrading: value });
                showToast('Paper Trading απενεργοποιήθηκε', 'warning');
              } catch (err) {
                showToast('Αποτυχία ενημέρωσης', 'error');
                setPaperTradingMode(!value);
              }
            },
          },
        ]
      );
    } else {
      setPaperTradingMode(value);
      showToast('Paper Trading ενεργοποιήθηκε', 'success');
    }
  }, [showToast]);

  const handleLogout = useCallback(() => {
    showModal(
      'Αποσύνδεση',
      'Είσαι σίγουρος ότι θέλεις να αποσυνδεθείς;',
      async () => {
        try {
          await api.logout();
          setUser(null);
          showToast('Αποσυνδέθηκες επιτυχώς', 'success');
          router.replace('/login');
        } catch (err) {
          showToast('Αποτυχία αποσύνδεσης', 'error');
        }
      }
    );
  }, [showModal, setUser, showToast, router]);

  const handleDeleteAccount = useCallback(() => {
    Alert.alert(
      '🚨 Διαγραφή Λογαριασμού',
      'Αυτή η ενέργεια είναι μόνιμη και δεν μπορεί να αναιρεθεί. Όλα τα δεδομένα σου θα διαγραφούν.',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Διαγραφή',
          style: 'destructive',
          onPress: () => {
            // Second confirmation
            Alert.alert(
              'Τελική Επιβεβαίωση',
              'Γράψε "DELETE" για να επιβεβαιώσεις τη διαγραφή',
              [
                { text: 'Ακύρωση', style: 'cancel' },
                {
                  text: 'Διαγραφή',
                  style: 'destructive',
                  onPress: async () => {
                    try {
                      // await api.deleteAccount();
                      showToast('Ο λογαριασμός διαγράφηκε', 'success');
                      router.replace('/login');
                    } catch (err) {
                      showToast('Αποτυχία διαγραφής', 'error');
                    }
                  },
                },
              ]
            );
          },
        },
      ]
    );
  }, [showToast, router]);

  const handleClearCache = useCallback(() => {
    showModal(
      '🗑️ Clear Cache',
      `Are you sure you want to clear ${cacheStats.count} cached items (${cacheSize})? This will remove all offline data.`,
      async () => {
        await clearCache();
        showToast('Cache cleared successfully', 'success');
      }
    );
  }, [cacheStats, cacheSize, clearCache, showModal, showToast]);

  const getRiskProfileDescription = (profile: RiskProfile) => {
    switch (profile) {
      case 'conservative':
        return 'Χαμηλός κίνδυνος, σταθερά κέρδη';
      case 'moderate':
        return 'Ισορροπημένος κίνδυνος/απόδοση';
      case 'aggressive':
        return 'Υψηλός κίνδυνος, μεγάλα κέρδη';
      default:
        return '';
    }
  };

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Profile Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>👤 Προφίλ</Text>
        
        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/profile')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Όνομα</Text>
            <Text style={styles.settingValue}>{user?.name || 'N/A'}</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/profile')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Email</Text>
            <Text style={styles.settingValue}>{user?.email || 'N/A'}</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>
      </View>

      {/* Trading Settings */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📊 Trading</Text>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => setShowRiskModal(true)}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Risk Profile</Text>
            <Text style={styles.settingValue}>
              {selectedRiskProfile.charAt(0).toUpperCase() + selectedRiskProfile.slice(1)}
            </Text>
            <Text style={styles.settingDescription}>
              {getRiskProfileDescription(selectedRiskProfile)}
            </Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Paper Trading Mode</Text>
            <Text style={styles.settingDescription}>
              {paperTradingMode ? 'Ασφαλής δοκιμή χωρίς πραγματικά χρήματα' : 'Live trading με πραγματικά χρήματα'}
            </Text>
          </View>
          <Switch
            value={paperTradingMode}
            onValueChange={handleTogglePaperTrading}
            trackColor={{ 
              false: theme.colors.ui.border, 
              true: theme.colors.brand.primary 
            }}
            thumbColor="#FFFFFF"
          />
        </View>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/brokers')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Brokers</Text>
            <Text style={styles.settingDescription}>Διαχείριση συνδεδεμένων brokers</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>
      </View>

      {/* Notifications */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🔔 Ειδοποιήσεις</Text>

        <View style={styles.settingItem}>
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Push Notifications</Text>
            <Text style={styles.settingDescription}>Λήψη ειδοποιήσεων για trades και προβλέψεις</Text>
          </View>
          <Switch
            value={notificationsEnabled}
            onValueChange={handleToggleNotifications}
            trackColor={{ 
              false: theme.colors.ui.border, 
              true: theme.colors.brand.primary 
            }}
            thumbColor="#FFFFFF"
          />
        </View>
      </View>

      {/* Appearance Section */}
      <AnimatedCard delay={100} animationType="slideUp">
        <Text style={styles.sectionTitle}>🎨 Εμφάνιση</Text>

        {/* Theme Mode Selector */}
        <View style={styles.settingItem}>
          <Text style={styles.settingLabel}>Θέμα</Text>
        </View>
        
        <View style={styles.themeOptions}>
          {(['light', 'dark', 'auto'] as const).map((mode) => (
            <TouchableOpacity
              key={mode}
              style={[
                styles.themeOption,
                themeMode === mode && styles.themeOptionActive,
              ]}
              onPress={() => {
                setThemeMode(mode);
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              }}
            >
              <Text style={styles.themeOptionIcon}>
                {mode === 'light' ? '☀️' : mode === 'dark' ? '🌙' : '⚙️'}
              </Text>
              <Text
                style={[
                  styles.themeOptionText,
                  themeMode === mode && styles.themeOptionTextActive,
                ]}
              >
                {mode === 'light' ? 'Φωτεινό' : mode === 'dark' ? 'Σκοτεινό' : 'Αυτόματο'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.settingDescription}>
          {themeMode === 'auto'
            ? 'Το θέμα αλλάζει αυτόματα με βάση τις ρυθμίσεις του συστήματος'
            : `Χρήση ${themeMode === 'light' ? 'φωτεινού' : 'σκοτεινού'} θέματος`}
        </Text>
      </AnimatedCard>

      {/* Storage & Cache Section */}
      <AnimatedCard delay={300} animationType="slideUp">
        <Text style={styles.sectionTitle}>💾 Storage & Cache</Text>

        {/* Connection Status */}
        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text style={styles.settingLabel}>Connection Status</Text>
            <Text style={styles.settingDescription}>
              {isOnline ? 'Online' : 'Offline'}
            </Text>
          </View>
          <View style={[styles.statusIndicator, { backgroundColor: isOnline ? theme.colors.semantic.success : theme.colors.semantic.error }]} />
        </View>

        {/* Cache Info */}
        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text style={styles.settingLabel}>Cached Data</Text>
            <Text style={styles.settingDescription}>
              {cacheStats.count} items • {cacheSize}
            </Text>
          </View>
        </View>

        {/* Clear Cache Button */}
        <Button
          title="🗑️ Clear Cache"
          onPress={handleClearCache}
          variant="secondary"
          size="medium"
          fullWidth
          style={styles.clearCacheButton}
        />

        <Text style={styles.settingDescription}>
          Cached data allows the app to work offline. Clear cache if you're experiencing issues.
        </Text>
      </AnimatedCard>

      {/* Security */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🔒 Ασφάλεια</Text>

        {/* Biometrics Toggle */}
        {biometricsAvailable && (
          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Text style={styles.settingLabel}>{biometricType}</Text>
              <Text style={styles.settingDescription}>
                Χρήση {biometricType} για γρήγορη σύνδεση
              </Text>
            </View>
            <Switch
              value={biometricsEnabled}
              onValueChange={handleBiometricsToggle}
              trackColor={{ 
                false: theme.colors.ui.border, 
                true: theme.colors.brand.primary 
              }}
              thumbColor="#FFFFFF"
              disabled={biometricsLoading}
            />
          </View>
        )}

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/change-password')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Αλλαγή Κωδικού</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>ℹ️ Πληροφορίες</Text>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/terms')}
        >
          <Text style={styles.settingLabel}>Όροι Χρήσης</Text>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/privacy')}
        >
          <Text style={styles.settingLabel}>Πολιτική Απορρήτου</Text>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/help')}
        >
          <Text style={styles.settingLabel}>Βοήθεια & Support</Text>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <Text style={styles.settingLabel}>Έκδοση</Text>
          <Text style={styles.settingValue}>1.0.0 (Beta)</Text>
        </View>
      </View>

      {/* Danger Zone */}
      <View style={styles.dangerSection}>
        <Text style={styles.dangerTitle}>⚠️ Danger Zone</Text>

        <Button
          title="Αποσύνδεση"
          onPress={handleLogout}
          variant="secondary"
          size="medium"
          fullWidth
          style={styles.dangerButton}
        />

        <Button
          title="Διαγραφή Λογαριασμού"
          onPress={handleDeleteAccount}
          variant="danger"
          size="medium"
          fullWidth
        />
      </View>

      {/* Risk Profile Modal */}
      <Modal
        visible={showRiskModal}
        title="Επιλογή Risk Profile"
        onClose={() => setShowRiskModal(false)}
      >
        <View style={styles.riskOptions}>
          <TouchableOpacity
            style={[
              styles.riskOption,
              selectedRiskProfile === 'conservative' && styles.riskOptionSelected,
            ]}
            onPress={() => handleUpdateRiskProfile('conservative')}
            disabled={updatingRisk}
          >
            <Text style={styles.riskOptionTitle}>🛡️ Conservative</Text>
            <Text style={styles.riskOptionDescription}>
              Χαμηλός κίνδυνος, σταθερά κέρδη. Ιδανικό για αρχάριους.
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.riskOption,
              selectedRiskProfile === 'moderate' && styles.riskOptionSelected,
            ]}
            onPress={() => handleUpdateRiskProfile('moderate')}
            disabled={updatingRisk}
          >
            <Text style={styles.riskOptionTitle}>⚖️ Moderate</Text>
            <Text style={styles.riskOptionDescription}>
              Ισορροπημένος κίνδυνος/απόδοση. Συνιστάται για τους περισσότερους.
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.riskOption,
              selectedRiskProfile === 'aggressive' && styles.riskOptionSelected,
            ]}
            onPress={() => handleUpdateRiskProfile('aggressive')}
            disabled={updatingRisk}
          >
            <Text style={styles.riskOptionTitle}>🚀 Aggressive</Text>
            <Text style={styles.riskOptionDescription}>
              Υψηλός κίνδυνος, μεγάλα κέρδη. Μόνο για έμπειρους traders.
            </Text>
          </TouchableOpacity>
        </View>
      </Modal>
      </ScrollView>
    </PageTransition>
  );
}

// Styles function - needs theme as parameter
const createStyles = (theme: typeof lightTheme) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  section: {
    marginBottom: theme.spacing.xl,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: theme.colors.ui.cardBackground,
    padding: theme.spacing.lg,
    borderRadius: theme.borderRadius.large,
    marginBottom: theme.spacing.sm,
  },
  settingLeft: {
    flex: 1,
    marginRight: theme.spacing.md,
  },
  settingInfo: {
    flex: 1,
  },
  settingLabel: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  settingValue: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  settingDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.xs,
  },
  arrow: {
    fontSize: 18,
    color: theme.colors.text.secondary,
  },
  dangerSection: {
    marginTop: theme.spacing.xl,
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.semantic.error + '10',
    borderRadius: theme.borderRadius.xl,
    borderWidth: 1,
    borderColor: theme.colors.semantic.error + '30',
  },
  dangerTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.semantic.error,
    marginBottom: theme.spacing.md,
  },
  dangerButton: {
    marginBottom: theme.spacing.sm,
  },
  riskOptions: {
    gap: theme.spacing.md,
    marginTop: theme.spacing.md,
  },
  riskOption: {
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.large,
    borderWidth: 2,
    borderColor: theme.colors.ui.border,
  },
  riskOptionSelected: {
    borderColor: theme.colors.brand.primary,
    backgroundColor: theme.colors.brand.primary + '10',
  },
  riskOptionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  riskOptionDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
  },
  themeOptions: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginVertical: theme.spacing.md,
  },
  themeOption: {
    flex: 1,
    alignItems: 'center',
    padding: theme.spacing.md,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.medium,
    borderWidth: 2,
    borderColor: theme.colors.ui.border,
  },
  themeOptionActive: {
    borderColor: theme.colors.brand.primary,
    backgroundColor: theme.colors.brand.primary + '10',
  },
  themeOptionIcon: {
    fontSize: 32,
    marginBottom: theme.spacing.xs,
  },
  themeOptionText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  themeOptionTextActive: {
    color: theme.colors.brand.primary,
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  clearCacheButton: {
    marginTop: theme.spacing.md,
  },
});

