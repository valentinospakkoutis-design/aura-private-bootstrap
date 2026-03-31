import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert } from 'react-native';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { LoadingSpinner } from '../mobile/src/components/LoadingSpinner';
import { NoBrokerConnected } from '../mobile/src/components/NoBrokerConnected';
import { Button } from '../mobile/src/components/Button';
import { Modal } from '../mobile/src/components/Modal';
import { theme } from '../mobile/src/constants/theme';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const storeCredential = async (key: string, value: string) => {
  if (Platform.OS === 'web') return;
  await SecureStore.setItemAsync(key, value);
};

interface Broker {
  id: string;
  name: string;
  logo: string;
  connected: boolean;
  description: string;
  supported: boolean;
}

const AVAILABLE_BROKERS: Broker[] = [
  {
    id: 'binance',
    name: 'Binance',
    logo: '🟡',
    connected: false,
    description: 'Crypto trading platform',
    supported: true,
  },
  {
    id: 'etoro',
    name: 'eToro',
    logo: '💚',
    connected: false,
    description: 'Social trading & investing',
    supported: true,
  },
  {
    id: 'interactive-brokers',
    name: 'Interactive Brokers',
    logo: '🔵',
    connected: false,
    description: 'Stocks, options, futures',
    supported: true,
  },
  {
    id: 'coinbase',
    name: 'Coinbase',
    logo: '🔷',
    connected: false,
    description: 'Cryptocurrency exchange',
    supported: false,
  },
];

export default function BrokersScreen() {
  const { brokers, setBrokers, addBroker, removeBroker, showToast, showModal } = useAppStore();
  const [selectedBroker, setSelectedBroker] = useState<Broker | null>(null);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);

  const {
    loading: loadingBrokers,
    execute: fetchBrokers,
  } = useApi((...args: any[]) => api.getBrokers(...args), { showLoading: false, showToast: false });

  const {
    loading: connecting,
    execute: connectBrokerApi,
  } = useApi((...args: any[]) => api.connectBroker(...args), { showLoading: false, showToast: false });

  useEffect(() => {
    loadBrokers();
  }, []);

  const loadBrokers = async () => {
    try {
      const data = await fetchBrokers();
      // Backend returns {brokers: [{broker, connected, ...}], total_connected, timestamp}
      const brokerList = data?.brokers ?? (Array.isArray(data) ? data : []);
      const mapped = brokerList.map((b: any) => ({
        id: b.broker || b.id,
        name: (b.broker || b.id || '').charAt(0).toUpperCase() + (b.broker || b.id || '').slice(1),
        connected: b.connected ?? false,
      }));
      setBrokers(mapped);
    } catch (err) {
      console.error('Failed to load brokers:', err);
    }
  };

  const handleOpenConnectModal = useCallback((broker: Broker) => {
    if (!broker.supported) {
      showToast('Αυτός ο broker δεν υποστηρίζεται ακόμα', 'warning');
      return;
    }
    setSelectedBroker(broker);
    setShowConnectModal(true);
    setApiKey('');
    setApiSecret('');
  }, [showToast]);

  const handleCloseConnectModal = useCallback(() => {
    setShowConnectModal(false);
    setSelectedBroker(null);
    setApiKey('');
    setApiSecret('');
  }, []);

  const validateInputs = useCallback((): boolean => {
    if (!apiKey.trim()) {
      showToast('Το API Key είναι υποχρεωτικό', 'error');
      return false;
    }

    if (!apiSecret.trim()) {
      showToast('Το API Secret είναι υποχρεωτικό', 'error');
      return false;
    }

    // Basic validation for Binance API keys
    if (selectedBroker?.id === 'binance') {
      if (apiKey.length < 64) {
        showToast('Το Binance API Key πρέπει να είναι 64 χαρακτήρες', 'error');
        return false;
      }
      if (apiSecret.length < 64) {
        showToast('Το Binance API Secret πρέπει να είναι 64 χαρακτήρες', 'error');
        return false;
      }
    }

    return true;
  }, [apiKey, apiSecret, selectedBroker, showToast]);

  const handleConnectBroker = useCallback(async () => {
    if (!selectedBroker || !validateInputs()) return;

    try {
      setIsConnecting(true);

      // Store credentials securely (native only)
      await storeCredential(`${selectedBroker.id}_api_key`, apiKey);
      await storeCredential(`${selectedBroker.id}_api_secret`, apiSecret);

      // Connect to broker via API
      const result = await connectBrokerApi(selectedBroker.id, apiKey, apiSecret);

      if (result?.status === 'connected') {
        addBroker({
          id: result.id || selectedBroker.id,
          name: selectedBroker.name,
          connected: true,
          apiKey: apiKey.substring(0, 8) + '...',
        });

        showToast(`${selectedBroker.name} συνδέθηκε επιτυχώς! 🎉`, 'success');
        handleCloseConnectModal();
        await loadBrokers();
      } else {
        throw new Error('Connection failed');
      }
    } catch (err: any) {
      console.error('Failed to connect broker:', err);
      
      // Clean up stored credentials on failure (native only)
      if (Platform.OS !== 'web') {
        await SecureStore.deleteItemAsync(`${selectedBroker.id}_api_key`).catch(() => {});
        await SecureStore.deleteItemAsync(`${selectedBroker.id}_api_secret`).catch(() => {});
      }

      showToast(
        err?.message || 'Αποτυχία σύνδεσης. Έλεγξε τα API credentials.',
        'error'
      );
    } finally {
      setIsConnecting(false);
    }
  }, [selectedBroker, apiKey, apiSecret, validateInputs, connectBrokerApi, addBroker, showToast, handleCloseConnectModal, loadBrokers]);

  const handleDisconnectBroker = useCallback((broker: any) => {
    showModal(
      'Αποσύνδεση Broker',
      `Είσαι σίγουρος ότι θέλεις να αποσυνδέσεις το ${broker.name};`,
      async () => {
        try {
          // Delete from API
          await api.disconnectBroker(broker.id);

          // Delete stored credentials (native only)
          if (Platform.OS !== 'web') {
            await SecureStore.deleteItemAsync(`${broker.id}_api_key`).catch(() => {});
            await SecureStore.deleteItemAsync(`${broker.id}_api_secret`).catch(() => {});
          }

          // Remove from store
          removeBroker(broker.id);

          showToast(`${broker.name} αποσυνδέθηκε`, 'success');
          await loadBrokers();
        } catch (err) {
          console.error('Failed to disconnect broker:', err);
          showToast('Αποτυχία αποσύνδεσης', 'error');
        }
      }
    );
  }, [showModal, removeBroker, showToast, loadBrokers]);

  // Merge store brokers with available brokers
  const getBrokersWithStatus = useCallback((): Broker[] => {
    return AVAILABLE_BROKERS.map(broker => {
      const connectedBroker = brokers.find(b => b.id === broker.id || b.name === broker.name);
      return {
        ...broker,
        connected: connectedBroker?.connected || false,
      };
    });
  }, [brokers]);

  if (loadingBrokers) {
    return <LoadingSpinner fullScreen message="Φόρτωση brokers..." />;
  }

  const connectedBrokers = brokers.filter((b) => b.connected);
  const hasConnectedBrokers = connectedBrokers.length > 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Connected Brokers */}
      {hasConnectedBrokers && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>✅ Συνδεδεμένα Brokers</Text>
          {connectedBrokers.map((broker) => (
            <View key={broker.id} style={styles.brokerCard}>
              <View style={styles.brokerHeader}>
                <View style={styles.brokerInfo}>
                  <Text style={styles.brokerLogo}>
                    {AVAILABLE_BROKERS.find((b) => b.id === broker.id)?.logo || '🔷'}
                  </Text>
                  <View style={styles.brokerDetails}>
                    <Text style={styles.brokerName}>{broker.name}</Text>
                    <Text style={styles.brokerStatus}>🟢 Συνδεδεμένο</Text>
                  </View>
                </View>
                <TouchableOpacity
                  style={styles.disconnectButton}
                  onPress={() => handleDisconnectBroker(broker)}
                >
                  <Text style={styles.disconnectText}>Αποσύνδεση</Text>
                </TouchableOpacity>
              </View>
              {broker.apiKey && (
                <Text style={styles.apiKeyPreview}>API Key: {broker.apiKey}</Text>
              )}
            </View>
          ))}
        </View>
      )}

      {/* Available Brokers */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📋 Διαθέσιμα Brokers</Text>
        {AVAILABLE_BROKERS.map((broker) => {
          const isConnected = brokers.some((b) => b.id === broker.id && b.connected);
          
          return (
            <TouchableOpacity
              key={broker.id}
              style={[
                styles.brokerCard,
                !broker.supported && styles.brokerCardDisabled,
                isConnected && styles.brokerCardConnected,
              ]}
              onPress={() => !isConnected && handleOpenConnectModal(broker)}
              disabled={isConnected || !broker.supported}
              activeOpacity={0.7}
            >
              <View style={styles.brokerHeader}>
                <View style={styles.brokerInfo}>
                  <Text style={styles.brokerLogo}>{broker.logo}</Text>
                  <View style={styles.brokerDetails}>
                    <Text style={styles.brokerName}>{broker.name}</Text>
                    <Text style={styles.brokerDescription}>{broker.description}</Text>
                  </View>
                </View>
                {isConnected ? (
                  <View style={styles.connectedBadge}>
                    <Text style={styles.connectedText}>✓</Text>
                  </View>
                ) : broker.supported ? (
                  <Text style={styles.arrow}>→</Text>
                ) : (
                  <View style={styles.comingSoonBadge}>
                    <Text style={styles.comingSoonText}>Σύντομα</Text>
                  </View>
                )}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Info Card */}
      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>🔒 Ασφάλεια</Text>
        <Text style={styles.infoText}>
          • Τα API credentials αποθηκεύονται με κρυπτογράφηση{'\n'}
          • Δεν αποθηκεύουμε ποτέ τους κωδικούς σου{'\n'}
          • Χρησιμοποιούμε μόνο read-only permissions όπου είναι δυνατόν{'\n'}
          • Μπορείς να αποσυνδέσεις ανά πάσα στιγμή
        </Text>
      </View>

      {/* Connect Modal */}
      <Modal
        visible={showConnectModal}
        title={`Σύνδεση με ${selectedBroker?.name}`}
        onClose={handleCloseConnectModal}
      >
        <View style={styles.modalContent}>
          <Text style={styles.modalDescription}>
            Για να συνδέσεις το {selectedBroker?.name}, χρειάζεσαι τα API credentials από το broker σου.
          </Text>

          {/* API Key Input */}
          <View style={styles.inputContainer}>
            <Text style={styles.inputLabel}>API Key *</Text>
            <TextInput
              style={styles.input}
              value={apiKey}
              onChangeText={setApiKey}
              placeholder="Εισήγαγε το API Key"
              placeholderTextColor={theme.colors.text.secondary}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
            />
          </View>

          {/* API Secret Input */}
          <View style={styles.inputContainer}>
            <Text style={styles.inputLabel}>API Secret *</Text>
            <TextInput
              style={styles.input}
              value={apiSecret}
              onChangeText={setApiSecret}
              placeholder="Εισήγαγε το API Secret"
              placeholderTextColor={theme.colors.text.secondary}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
            />
          </View>

          {/* Warning */}
          <View style={styles.warningBox}>
            <Text style={styles.warningText}>
              ⚠️ Βεβαιώσου ότι το API Key έχει μόνο trading permissions (όχι withdrawal).
            </Text>
          </View>

          {/* Connect Button */}
          <Button
            title="Σύνδεση"
            onPress={handleConnectBroker}
            variant="primary"
            size="large"
            fullWidth
            loading={isConnecting}
            disabled={isConnecting || !apiKey.trim() || !apiSecret.trim()}
          />
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
  brokerCard: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  brokerCardDisabled: {
    opacity: 0.6,
  },
  brokerCardConnected: {
    borderWidth: 2,
    borderColor: theme.colors.semantic.success,
  },
  brokerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brokerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  brokerLogo: {
    fontSize: 40,
    marginRight: theme.spacing.md,
  },
  brokerDetails: {
    flex: 1,
  },
  brokerName: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  brokerDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  brokerStatus: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.semantic.success,
    fontWeight: '600',
  },
  apiKeyPreview: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.mono,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.sm,
    paddingTop: theme.spacing.sm,
    borderTopWidth: 1,
    borderTopColor: theme.colors.ui.border,
  },
  disconnectButton: {
    backgroundColor: theme.colors.semantic.error + '20',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.medium,
  },
  disconnectText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.semantic.error,
  },
  arrow: {
    fontSize: 18,
    color: theme.colors.text.secondary,
  },
  connectedBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.colors.semantic.success,
    justifyContent: 'center',
    alignItems: 'center',
  },
  connectedText: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '700',
  },
  comingSoonBadge: {
    backgroundColor: theme.colors.ui.border,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.small,
  },
  comingSoonText: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.secondary,
    fontWeight: '600',
  },
  infoCard: {
    backgroundColor: theme.colors.brand.primary + '10',
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    borderWidth: 1,
    borderColor: theme.colors.brand.primary + '30',
  },
  infoTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  infoText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 22,
  },
  modalContent: {
    marginTop: theme.spacing.md,
  },
  modalDescription: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 22,
    marginBottom: theme.spacing.lg,
  },
  inputContainer: {
    marginBottom: theme.spacing.md,
  },
  inputLabel: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  input: {
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontFamily: theme.typography.fontFamily.mono,
  },
  warningBox: {
    backgroundColor: theme.colors.semantic.warning + '20',
    borderWidth: 1,
    borderColor: theme.colors.semantic.warning,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.lg,
  },
  warningText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.semantic.warning,
    lineHeight: 20,
  },
});

