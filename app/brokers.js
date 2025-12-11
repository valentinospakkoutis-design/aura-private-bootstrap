import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';
import { storeApiKey, getApiKey, deleteApiKey } from '../mobile/src/utils/security';

export default function BrokersScreen() {
  const router = useRouter();
  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedBroker, setSelectedBroker] = useState('binance');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [testnet, setTestnet] = useState(true);

  useEffect(() => {
    loadBrokerStatus();
  }, []);

  const loadBrokerStatus = async () => {
    try {
      const status = await api.get('/api/brokers/status');
      setBrokers(status.brokers || []);
    } catch (error) {
      console.error('Error loading broker status:', error);
    }
  };

  const handleConnect = async () => {
    if (!apiKey || !apiSecret) {
      Alert.alert('Σφάλμα', 'Παρακαλώ συμπληρώστε API Key και API Secret');
      return;
    }

    setLoading(true);
    try {
      const result = await api.post('/api/brokers/connect', {
        broker: selectedBroker,
        api_key: apiKey,
        api_secret: apiSecret,
        testnet: testnet
      });

      if (result.status === 'connected') {
        // Store API keys securely (optional - user can choose)
        try {
          await storeApiKey(`${selectedBroker}_key`, apiKey);
          await storeApiKey(`${selectedBroker}_secret`, apiSecret);
        } catch (error) {
          console.error('Error storing API keys:', error);
          // Don't fail the connection if storage fails
        }
        
        Alert.alert('Επιτυχία', `Συνδέθηκε επιτυχώς με ${selectedBroker.toUpperCase()}!`);
        setApiKey('');
        setApiSecret('');
        loadBrokerStatus();
      }
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία σύνδεσης');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async (brokerName) => {
    try {
      await api.delete(`/api/brokers/${brokerName}/disconnect`);
      
      // Delete stored API keys for security
      try {
        await deleteApiKey(`${brokerName}_key`);
        await deleteApiKey(`${brokerName}_secret`);
      } catch (error) {
        console.error('Error deleting stored keys:', error);
        // Don't fail if deletion fails
      }
      
      Alert.alert('Επιτυχία', `Αποσυνδέθηκε από ${brokerName.toUpperCase()}`);
      loadBrokerStatus();
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία αποσύνδεσης');
    }
  };

  const isConnected = (brokerName) => {
    return brokers.some(b => b.broker === brokerName && b.connected);
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>📊 Brokers API</Text>
        </View>

        {/* Connected Brokers */}
        {brokers.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Συνδεδεμένοι Brokers</Text>
            {brokers.map((broker, index) => (
              <View key={index} style={styles.brokerCard}>
                <View style={styles.brokerInfo}>
                  <Text style={styles.brokerName}>{broker.broker.toUpperCase()}</Text>
                  <View style={[styles.statusBadge, broker.connected && styles.statusBadgeActive]}>
                    <Text style={styles.statusText}>
                      {broker.connected ? 'Συνδεδεμένο' : 'Αποσυνδεδεμένο'}
                    </Text>
                  </View>
                </View>
                {broker.connected && (
                  <TouchableOpacity
                    style={styles.disconnectButton}
                    onPress={() => handleDisconnect(broker.broker)}
                  >
                    <Text style={styles.disconnectButtonText}>Αποσύνδεση</Text>
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </View>
        )}

        {/* Connect New Broker */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Σύνδεση Broker</Text>

          {/* Broker Selection */}
          <View style={styles.brokerSelector}>
            {['binance', 'etoro', 'ib'].map((broker) => (
              <TouchableOpacity
                key={broker}
                style={[
                  styles.brokerOption,
                  selectedBroker === broker && styles.brokerOptionActive
                ]}
                onPress={() => setSelectedBroker(broker)}
              >
                <Text style={[
                  styles.brokerOptionText,
                  selectedBroker === broker && styles.brokerOptionTextActive
                ]}>
                  {broker.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* API Key Input */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>API Key</Text>
            <TextInput
              style={styles.input}
              value={apiKey}
              onChangeText={setApiKey}
              placeholder="Εισάγετε API Key"
              placeholderTextColor="#666"
              secureTextEntry={false}
              autoCapitalize="none"
            />
          </View>

          {/* API Secret Input */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>API Secret</Text>
            <TextInput
              style={styles.input}
              value={apiSecret}
              onChangeText={setApiSecret}
              placeholder="Εισάγετε API Secret"
              placeholderTextColor="#666"
              secureTextEntry={true}
              autoCapitalize="none"
            />
          </View>

          {/* Testnet Toggle */}
          <View style={styles.toggleGroup}>
            <Text style={styles.toggleLabel}>Testnet (Paper Trading)</Text>
            <TouchableOpacity
              style={[styles.toggle, testnet && styles.toggleActive]}
              onPress={() => setTestnet(!testnet)}
            >
              <View style={[styles.toggleThumb, testnet && styles.toggleThumbActive]} />
            </TouchableOpacity>
          </View>

          {/* Connect Button */}
          <TouchableOpacity
            style={[styles.connectButton, loading && styles.connectButtonDisabled]}
            onPress={handleConnect}
            disabled={loading || isConnected(selectedBroker)}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.connectButtonText}>
                {isConnected(selectedBroker) ? 'Συνδεδεμένο' : 'Σύνδεση'}
              </Text>
            )}
          </TouchableOpacity>

          {/* Info */}
          <View style={styles.infoBox}>
            <Text style={styles.infoText}>
              💡 Για Paper Trading, χρησιμοποιήστε Testnet API keys.
              {'\n'}Τα keys αποθηκεύονται ασφαλώς και χρησιμοποιούνται μόνο για trading.
            </Text>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>🔒 Όλα τα API keys είναι κρυπτογραφημένα</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  content: {
    padding: 20,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 30,
    marginTop: 10,
  },
  backButton: {
    marginRight: 15,
    padding: 5,
  },
  backButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  brokerCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  brokerInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brokerName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  statusBadge: {
    backgroundColor: '#3a3a3a',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusBadgeActive: {
    backgroundColor: '#4CAF50',
  },
  statusText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  disconnectButton: {
    marginTop: 10,
    backgroundColor: '#ff6b6b',
    borderRadius: 8,
    padding: 10,
    alignItems: 'center',
  },
  disconnectButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  brokerSelector: {
    flexDirection: 'row',
    marginBottom: 20,
    gap: 10,
  },
  brokerOption: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  brokerOptionActive: {
    backgroundColor: '#4CAF50',
    borderColor: '#4CAF50',
  },
  brokerOptionText: {
    color: '#999',
    fontWeight: 'bold',
  },
  brokerOptionTextActive: {
    color: '#fff',
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 14,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  toggleGroup: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  toggleLabel: {
    fontSize: 14,
    color: '#fff',
  },
  toggle: {
    width: 50,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#3a3a3a',
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  toggleActive: {
    backgroundColor: '#4CAF50',
  },
  toggleThumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#fff',
    alignSelf: 'flex-start',
  },
  toggleThumbActive: {
    alignSelf: 'flex-end',
  },
  connectButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  connectButtonDisabled: {
    opacity: 0.5,
  },
  connectButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  infoBox: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 15,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  infoText: {
    fontSize: 12,
    color: '#999',
    lineHeight: 18,
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 12,
    color: '#666',
  },
});

