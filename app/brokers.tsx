import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert } from 'react-native';
import { useAppStore } from '@/stores/appStore';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/apiClient';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { NoBrokerConnected } from '@/components/NoBrokerConnected';
import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { theme } from '@/constants/theme';
import * as SecureStore from 'expo-secure-store';

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
  } = useApi(api.getBrokers, { showLoading: false, showToast: false });

  const {
    loading: connecting,
    execute: connectBrokerApi,
  } = useApi(api.connectBroker, { showLoading: false, showToast: false });

  useEffect(() => {
    loadBrokers();
  }, []);

  const loadBrokers = async () => {
    try {
      const data = await fetchBrokers();
      if (Array.isArray(data)) {
        setBrokers(data);
      }
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

      // Store credentials securely
      await SecureStore.setItemAsync(`${selectedBroker.id}_api_key`, apiKey);
      await SecureStore.setItemAsync(`${selectedBroker.id}_api_secret`, apiSecret);

      // Connect to broker via API
      const result = await connectBrokerApi(selectedBroker.id, apiKey, apiSecret);

      if (result?.success) {
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
      
      // Clean up stored credentials on failure
      await SecureStore.deleteItemAsync(`${selectedBroker.id}_api_key`).catch(() => {});
      await SecureStore.deleteItemAsync(`${selectedBroker.id}_api_secret`).catch(() => {});

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
      `Είσαι σίγουρος ότι θέλεις να αποσυνδέσεις τον ${broker.name};`,
      async () => {
        try {
          await api.disconnectBroker(broker.id);
          
          // Clean up stored credentials
          await SecureStore.deleteItemAsync(`${broker.id}_api_key`).catch(() => {});
          await SecureStore.deleteItemAsync(`${broker.id}_api_secret`).catch(() => {});

          removeBroker(broker.id);
          showToast(`${broker.name} αποσυνδέθηκε`, 'success');
          await loadBrokers();
        } catch (err) {
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

  const brokersWithStatus = getBrokersWithStatus();
  const hasConnectedBrokers = brokersWithStatus.some(b => b.connected);

  if (!hasConnectedBrokers && brokersWithStatus.length === 0) {
    return <NoBrokerConnected />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Info Card */}
      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>🔌 Σύνδεση Brokers</Text>
        <Text style={styles.infoText}>
          Σύνδεσε τους brokers σου για να επιτρέψεις στο AURA να εκτελεί trades. Τα API keys σου αποθηκεύονται ασφαλώς.
        </Text>
      </View>

      {/* Brokers List */}
      <Text style={styles.sectionTitle}>Διαθέσιμοι Brokers</Text>
      {brokersWithStatus.map((broker) => (
        <View key={broker.id} style={styles.brokerCard}>
          <View style={styles.brokerHeader}>
            <View style={styles.brokerInfo}>
              <Text style={styles.brokerLogo}>{broker.logo}</Text>
              <View style={styles.brokerDetails}>
                <Text style={styles.brokerName}>{broker.name}</Text>
                <Text style={styles.brokerDescription}>{broker.description}</Text>
              </View>
            </View>
            {broker.connected ? (
              <View style={styles.connectedBadge}>
                <Text style={styles.connectedText}>✓ Συνδεδεμένο</Text>
              </View>
            ) : (
              <View style={styles.notSupportedBadge}>
                <Text style={styles.notSupportedText}>
                  {broker.supported ? 'Διαθέσιμο' : 'Σύντομα'}
                </Text>
              </View>
            )}
          </View>

          <View style={styles.brokerActions}>
            {broker.connected ? (
              <Button
                title="Αποσύνδεση"
                onPress={() => handleDisconnectBroker(broker)}
                variant="danger"
                size="medium"
                fullWidth
              />
            ) : (
              <Button
                title={broker.supported ? "Σύνδεση" : "Σύντομα"}
                onPress={() => handleOpenConnectModal(broker)}
                variant="primary"
                size="medium"
                fullWidth
                disabled={!broker.supported}
              />
            )}
          </View>
        </View>
      ))}

      {/* Connect Modal */}
      <Modal
        visible={showConnectModal}
        title={`Σύνδεση ${selectedBroker?.name}`}
        onClose={handleCloseConnectModal}
      >
        <View style={styles.modalContent}>
          <Text style={styles.modalDescription}>
            Εισάγετε τα API credentials σας. Θα αποθηκευτούν ασφαλώς στο device σας.
          </Text>

          <View style={styles.inputContainer}>
            <Text style={styles.inputLabel}>API Key</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter API Key"
              placeholderTextColor={theme.colors.text.tertiary}
              value={apiKey}
              onChangeText={setApiKey}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry={false}
            />
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.inputLabel}>API Secret</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter API Secret"
              placeholderTextColor={theme.colors.text.tertiary}
              value={apiSecret}
              onChangeText={setApiSecret}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry={true}
            />
          </View>

          <View style={styles.modalActions}>
            <Button
              title="Ακύρωση"
              onPress={handleCloseConnectModal}
              variant="ghost"
              size="medium"
              style={styles.modalButton}
            />
            <Button
              title="Σύνδεση"
              onPress={handleConnectBroker}
              variant="primary"
              size="medium"
              fullWidth
              loading={isConnecting || connecting}
              disabled={isConnecting || connecting}
            />
          </View>
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
  infoCard: {
    backgroundColor: theme.colors.brand.primary + '10',
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
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
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 22,
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
  brokerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing.md,
  },
  brokerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  brokerLogo: {
    fontSize: 32,
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
  connectedBadge: {
    backgroundColor: theme.colors.semantic.success + '20',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
  },
  connectedText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.semantic.success,
  },
  notSupportedBadge: {
    backgroundColor: theme.colors.ui.border,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
  },
  notSupportedText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  brokerActions: {
    marginTop: theme.spacing.sm,
  },
  modalContent: {
    gap: theme.spacing.md,
  },
  modalDescription: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 22,
    marginBottom: theme.spacing.sm,
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
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  modalActions: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginTop: theme.spacing.md,
  },
  modalButton: {
    flex: 1,
  },
});

