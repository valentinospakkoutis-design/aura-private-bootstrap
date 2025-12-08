import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import DailyQuote from '../mobile/src/components/DailyQuote';
import AuraOrb3D from '../mobile/src/components/AuraOrb3D';

export default function HomeScreen() {
  const router = useRouter();
  const [greeting, setGreeting] = useState('');

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) {
      setGreeting('Καλημέρα');
    } else if (hour < 18) {
      setGreeting('Καλό απόγευμα');
    } else {
      setGreeting('Καλησπέρα');
    }
  }, []);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        {/* Header Section */}
        <View style={styles.header}>
          <Text style={styles.greeting}>{greeting}! 👋</Text>
          
          {/* 3D Orb */}
          <AuraOrb3D 
            size={200} 
            color="#4CAF50" 
            speed={0.5}
            style={{ marginVertical: 20 }}
          />
          
          <Text style={styles.title}>AURA</Text>
          <Text style={styles.subtitle}>Το χρηματοοικονομικό σου ον</Text>
        </View>

        {/* Status Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Κατάσταση Συστήματος</Text>
            <View style={styles.statusDot} />
          </View>
          <Text style={styles.cardSubtitle}>✅ Σύστημα Ενεργό</Text>
          <Text style={styles.cardText}>✅ Backend Έτοιμο για σύνδεση</Text>
          <Text style={styles.cardText}>✅ AI Engine Αναμονή</Text>
        </View>

        {/* Quote of the Day */}
        <DailyQuote style={{ marginBottom: 20 }} />

        {/* Quick Stats */}
        <View style={styles.statsContainer}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>0</Text>
            <Text style={styles.statLabel}>Ενεργά Trades</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>€0</Text>
            <Text style={styles.statLabel}>Σημερινό P/L</Text>
          </View>
        </View>

        {/* Action Buttons */}
        <TouchableOpacity 
          style={styles.primaryButton}
          onPress={() => router.push('/paper-trading')}
        >
          <Text style={styles.primaryButtonText}>🚀 Ξεκίνα Paper Trading</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => router.push('/settings')}
        >
          <Text style={styles.secondaryButtonText}>⚙️ Ρυθμίσεις</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => router.push('/profile')}
        >
          <Text style={styles.secondaryButtonText}>👤 Προφίλ</Text>
        </TouchableOpacity>

        {/* Info Section */}
        <View style={styles.infoSection}>
          <Text style={styles.infoTitle}>📚 Επόμενα Βήματα:</Text>
          <Text style={styles.infoText}>• Σύνδεση με brokers (Binance, eToro)</Text>
          <Text style={styles.infoText}>• Ρύθμιση προφίλ κινδύνου</Text>
          <Text style={styles.infoText}>• Επιλογή στρατηγικών trading</Text>
          <Text style={styles.infoText}>• Ενεργοποίηση AI agent</Text>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>AURA v1.0.0</Text>
          <Text style={styles.footerSubtext}>Made with 💎 in Cyprus</Text>
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
    marginBottom: 30,
    alignItems: 'center',
  },
  greeting: {
    fontSize: 24,
    color: '#999',
    marginBottom: 10,
  },
  title: {
    fontSize: 56,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    fontStyle: 'italic',
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
    marginBottom: 10,
  },
  cardSubtitle: {
    fontSize: 16,
    color: '#4CAF50',
    marginBottom: 8,
  },
  cardText: {
    fontSize: 14,
    color: '#999',
    marginBottom: 5,
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#4CAF50',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 5,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  statNumber: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  statLabel: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
  primaryButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 12,
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
  infoSection: {
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
    marginBottom: 15,
  },
  infoText: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
    lineHeight: 20,
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
  },
  footerSubtext: {
    fontSize: 12,
    color: '#444',
  },
});

