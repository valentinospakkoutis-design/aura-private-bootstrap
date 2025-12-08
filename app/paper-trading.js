import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { useRouter } from 'expo-router';

export default function PaperTradingScreen() {
  const router = useRouter();
  const [isActive, setIsActive] = useState(false);

  const handleStartTrading = () => {
    Alert.alert(
      '🚀 Paper Trading',
      'Το Paper Trading θα ξεκινήσει σύντομα!\n\nΓια να ξεκινήσετε:\n• Συνδέστε brokers API keys\n• Ρυθμίστε προφίλ κινδύνου\n• Ενεργοποιήστε AI agent',
      [
        { text: 'Ρυθμίσεις', onPress: () => router.push('/settings') },
        { text: 'OK', style: 'cancel' }
      ]
    );
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>📊 Paper Trading</Text>
        </View>

        {/* Status Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Κατάσταση</Text>
            <View style={[styles.statusBadge, isActive && styles.statusBadgeActive]}>
              <Text style={styles.statusText}>{isActive ? 'Ενεργό' : 'Ανενεργό'}</Text>
            </View>
          </View>
          <Text style={styles.cardText}>
            {isActive 
              ? 'Το Paper Trading είναι ενεργό. Οι συναλλαγές είναι προσομοιωμένες.'
              : 'Το Paper Trading δεν είναι ενεργό. Ξεκινήστε για να προσομοιώσετε συναλλαγές χωρίς κίνδυνο.'}
          </Text>
        </View>

        {/* Info Section */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ Τι είναι το Paper Trading;</Text>
          <Text style={styles.infoText}>
            Το Paper Trading σας επιτρέπει να προσομοιώσετε συναλλαγές χωρίς να χρησιμοποιήσετε πραγματικά χρήματα. 
            Είναι ιδανικό για να μάθετε και να δοκιμάσετε στρατηγικές trading.
          </Text>
        </View>

        {/* Requirements */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📋 Απαιτήσεις:</Text>
          <View style={styles.requirementItem}>
            <Text style={styles.requirementText}>✅ Σύνδεση με broker (Binance, eToro, IB)</Text>
          </View>
          <View style={styles.requirementItem}>
            <Text style={styles.requirementText}>✅ Ρύθμιση προφίλ κινδύνου</Text>
          </View>
          <View style={styles.requirementItem}>
            <Text style={styles.requirementText}>✅ Ενεργοποίηση AI agent</Text>
          </View>
        </View>

        {/* Action Button */}
        <TouchableOpacity 
          style={[styles.primaryButton, isActive && styles.primaryButtonActive]}
          onPress={handleStartTrading}
        >
          <Text style={styles.primaryButtonText}>
            {isActive ? '⏸️ Διακοπή Paper Trading' : '🚀 Ξεκίνα Paper Trading'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => router.push('/settings')}
        >
          <Text style={styles.secondaryButtonText}>⚙️ Ρυθμίσεις</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>💡 Συμβουλή: Ξεκινήστε με μικρά ποσά για να μάθετε</Text>
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
  card: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  cardText: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
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
  infoCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
  },
  infoText: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
  },
  requirementItem: {
    marginBottom: 10,
  },
  requirementText: {
    fontSize: 14,
    color: '#999',
  },
  primaryButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonActive: {
    backgroundColor: '#ff6b6b',
  },
  primaryButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  secondaryButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  secondaryButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
    fontStyle: 'italic',
  },
});


