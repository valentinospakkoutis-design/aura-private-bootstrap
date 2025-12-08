import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';

export default function ProfileScreen() {
  const router = useRouter();

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        
        {/* Profile Header */}
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>VP</Text>
          </View>
          <Text style={styles.name}>Valentinos Pakkoutis</Text>
          <Text style={styles.email}>valentinospakkoutis@design.com</Text>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>💎 Premium User</Text>
          </View>
        </View>

        {/* Stats */}
        <View style={styles.statsContainer}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>0</Text>
            <Text style={styles.statLabel}>Συνολικά Trades</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>0%</Text>
            <Text style={styles.statLabel}>ROI</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>0</Text>
            <Text style={styles.statLabel}>Ημέρες</Text>
          </View>
        </View>

        {/* Profile Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📋 Πληροφορίες Προφίλ</Text>
          
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Όνομα</Text>
            <Text style={styles.infoValue}>Valentinos Pakkoutis</Text>
          </View>

          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Email</Text>
            <Text style={styles.infoValue}>valentinospakkoutis@design.com</Text>
          </View>

          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Τηλέφωνο</Text>
            <Text style={styles.infoValue}>+357 99 999999</Text>
          </View>

          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Χώρα</Text>
            <Text style={styles.infoValue}>🇨🇾 Κύπρος</Text>
          </View>

          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Μέλος από</Text>
            <Text style={styles.infoValue}>Δεκέμβριος 2025</Text>
          </View>
        </View>

        {/* Risk Profile */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚖️ Προφίλ Κινδύνου</Text>
          
          <View style={styles.riskCard}>
            <Text style={styles.riskLevel}>Μέτριο</Text>
            <Text style={styles.riskDescription}>
              Ισορροπημένη προσέγγιση με μέτριο κίνδυνο
            </Text>
            <View style={styles.riskBar}>
              <View style={[styles.riskFill, { width: '60%' }]} />
            </View>
          </View>

          <TouchableOpacity style={styles.actionButton}>
            <Text style={styles.actionButtonText}>Αλλαγή Προφίλ Κινδύνου</Text>
          </TouchableOpacity>
        </View>

        {/* Trading Preferences */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 Προτιμήσεις Trading</Text>
          
          <View style={styles.preferenceItem}>
            <Text style={styles.preferenceLabel}>Αγαπημένα Assets</Text>
            <Text style={styles.preferenceValue}>BTC, ETH, Gold, Silver</Text>
          </View>

          <View style={styles.preferenceItem}>
            <Text style={styles.preferenceLabel}>Στρατηγική</Text>
            <Text style={styles.preferenceValue}>Medium-term Swings</Text>
          </View>

          <View style={styles.preferenceItem}>
            <Text style={styles.preferenceLabel}>Max Position Size</Text>
            <Text style={styles.preferenceValue}>€1,000</Text>
          </View>
        </View>

        {/* Actions */}
        <View style={styles.section}>
          <TouchableOpacity style={styles.primaryButton}>
            <Text style={styles.primaryButtonText}>✏️ Επεξεργασία Προφίλ</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.secondaryButton}
            onPress={() => router.push('/settings')}
          >
            <Text style={styles.secondaryButtonText}>⚙️ Ρυθμίσεις</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>Όλα τα δεδομένα σου είναι κρυπτογραφημένα 🔒</Text>
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
    alignItems: 'center',
    marginBottom: 30,
    paddingVertical: 20,
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#4CAF50',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 15,
    borderWidth: 3,
    borderColor: '#2a2a2a',
  },
  avatarText: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#fff',
  },
  name: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  email: {
    fontSize: 14,
    color: '#999',
    marginBottom: 10,
  },
  badge: {
    backgroundColor: '#2a2a2a',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#4CAF50',
  },
  badgeText: {
    fontSize: 14,
    color: '#4CAF50',
    fontWeight: 'bold',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 30,
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
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  statLabel: {
    fontSize: 11,
    color: '#666',
    textAlign: 'center',
  },
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  infoItem: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  infoLabel: {
    fontSize: 14,
    color: '#999',
  },
  infoValue: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  riskCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  riskLevel: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFA726',
    marginBottom: 8,
  },
  riskDescription: {
    fontSize: 14,
    color: '#999',
    marginBottom: 15,
  },
  riskBar: {
    height: 8,
    backgroundColor: '#2a2a2a',
    borderRadius: 4,
    overflow: 'hidden',
  },
  riskFill: {
    height: '100%',
    backgroundColor: '#FFA726',
  },
  preferenceItem: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  preferenceLabel: {
    fontSize: 12,
    color: '#999',
    marginBottom: 5,
  },
  preferenceValue: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  actionButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3a3a3a',
  },
  actionButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  primaryButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  secondaryButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 16,
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
  },
});

