import React, { useState, useCallback, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '@/stores/appStore';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/apiClient';
import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { theme } from '@/constants/theme';
import * as SecureStore from 'expo-secure-store';

type RiskProfile = 'conservative' | 'moderate' | 'aggressive';

export default function SettingsScreen() {
  const router = useRouter();
  const { user, setUser, showToast, showModal } = useAppStore();
  
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [biometricsEnabled, setBiometricsEnabled] = useState(false);
  const [paperTradingMode, setPaperTradingMode] = useState(true);
  const [selectedRiskProfile, setSelectedRiskProfile] = useState<RiskProfile>(user?.riskProfile || 'moderate');
  const [showRiskModal, setShowRiskModal] = useState(false);

  const {
    loading: updatingProfile,
    execute: updateProfile,
  } = useApi(api.updateProfile, { showLoading: false, showToast: false });

  const {
    loading: updatingRisk,
    execute: updateRisk,
  } = useApi(api.updateRiskProfile, { showLoading: false, showToast: false });

  useEffect(() => {
    loadBiometricsSetting();
  }, []);

  const loadBiometricsSetting = async () => {
    try {
      const value = await SecureStore.getItemAsync('biometrics_enabled');
      setBiometricsEnabled(value === 'true');
    } catch (err) {
      console.error('Error loading biometrics setting:', err);
    }
  };

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

  const handleToggleBiometrics = useCallback(async (value: boolean) => {
    try {
      setBiometricsEnabled(value);
      await SecureStore.setItemAsync('biometrics_enabled', value ? 'true' : 'false');
      showToast(value ? 'Biometrics ενεργοποιήθηκαν' : 'Biometrics απενεργοποιήθηκαν', 'success');
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης', 'error');
      setBiometricsEnabled(!value);
    }
  }, [showToast]);

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

      {/* Security */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🔒 Ασφάλεια</Text>

        <View style={styles.settingItem}>
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Biometrics</Text>
            <Text style={styles.settingDescription}>Χρήση Face ID / Touch ID για login</Text>
          </View>
          <Switch
            value={biometricsEnabled}
            onValueChange={handleToggleBiometrics}
            trackColor={{ 
              false: theme.colors.ui.border, 
              true: theme.colors.brand.primary 
            }}
            thumbColor="#FFFFFF"
          />
        </View>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>ℹ️ Σχετικά</Text>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/help')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Βοήθεια & Υποστήριξη</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/terms')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Όροι Χρήσης</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.settingItem}
          onPress={() => router.push('/privacy')}
        >
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Πολιτική Απορρήτου</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingLeft}>
            <Text style={styles.settingLabel}>Έκδοση</Text>
            <Text style={styles.settingValue}>v1.0.0</Text>
          </View>
        </View>
      </View>

      {/* Danger Zone */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>⚠️ Ζώνη Κινδύνου</Text>

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
          style={styles.dangerButton}
        />
      </View>

      {/* Risk Profile Modal */}
      <Modal
        visible={showRiskModal}
        title="Επιλογή Risk Profile"
        message="Επίλεξε το risk profile που ταιριάζει καλύτερα με την προτίμησή σου:"
        onClose={() => setShowRiskModal(false)}
      >
        <View style={styles.riskOptions}>
          {(['conservative', 'moderate', 'aggressive'] as RiskProfile[]).map((profile) => (
            <TouchableOpacity
              key={profile}
              style={[
                styles.riskOption,
                selectedRiskProfile === profile && styles.riskOptionSelected
              ]}
              onPress={() => handleUpdateRiskProfile(profile)}
            >
              <Text style={[
                styles.riskOptionTitle,
                selectedRiskProfile === profile && styles.riskOptionTitleSelected
              ]}>
                {profile.charAt(0).toUpperCase() + profile.slice(1)}
              </Text>
              <Text style={styles.riskOptionDescription}>
                {getRiskProfileDescription(profile)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </Modal>
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
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  settingLeft: {
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
    fontSize: theme.typography.sizes.lg,
    color: theme.colors.text.secondary,
    marginLeft: theme.spacing.sm,
  },
  dangerButton: {
    marginBottom: theme.spacing.sm,
  },
  riskOptions: {
    gap: theme.spacing.sm,
  },
  riskOption: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  riskOptionSelected: {
    borderColor: theme.colors.brand.primary,
    backgroundColor: theme.colors.brand.primary + '10',
  },
  riskOptionTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  riskOptionTitleSelected: {
    color: theme.colors.brand.primary,
  },
  riskOptionDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
});

