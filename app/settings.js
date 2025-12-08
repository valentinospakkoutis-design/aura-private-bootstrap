import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch } from 'react-native';
import { useRouter } from 'expo-router';

export default function SettingsScreen() {
  const router = useRouter();
  const [notifications, setNotifications] = React.useState(true);
  const [darkMode, setDarkMode] = React.useState(true);
  const [autoTrade, setAutoTrade] = React.useState(false);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        
        {/* Account Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>👤 Λογαριασμός</Text>
          
          <TouchableOpacity 
            style={styles.menuItem}
            onPress={() => router.push('/profile')}
          >
            <Text style={styles.menuText}>Προφίλ Χρήστη</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Ασφάλεια & 2FA</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Trading Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 Trading</Text>
          
          <View style={styles.menuItem}>
            <Text style={styles.menuText}>Auto Trading</Text>
            <Switch
              value={autoTrade}
              onValueChange={setAutoTrade}
              trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
              thumbColor={autoTrade ? '#fff' : '#f4f3f4'}
            />
          </View>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Brokers API Keys</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Προφίλ Κινδύνου</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* App Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚙️ Εφαρμογή</Text>
          
          <View style={styles.menuItem}>
            <Text style={styles.menuText}>Ειδοποιήσεις</Text>
            <Switch
              value={notifications}
              onValueChange={setNotifications}
              trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
              thumbColor={notifications ? '#fff' : '#f4f3f4'}
            />
          </View>

          <View style={styles.menuItem}>
            <Text style={styles.menuText}>Dark Mode</Text>
            <Switch
              value={darkMode}
              onValueChange={setDarkMode}
              trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
              thumbColor={darkMode ? '#fff' : '#f4f3f4'}
            />
          </View>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Γλώσσα</Text>
            <Text style={styles.menuValue}>Ελληνικά</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* AI Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🤖 AI Engine</Text>
          
          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Στρατηγικές AI</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Ρυθμίσεις Μάθησης</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Legal & Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📄 Νομικά</Text>
          
          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Όροι Χρήσης</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Πολιτική Απορρήτου</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuText}>Σχετικά με την AURA</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Danger Zone */}
        <View style={styles.dangerSection}>
          <TouchableOpacity style={styles.dangerButton}>
            <Text style={styles.dangerButtonText}>🚪 Αποσύνδεση</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>AURA v1.0.0</Text>
          <Text style={styles.footerText}>Expo SDK 52</Text>
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
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  menuItem: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  menuText: {
    fontSize: 16,
    color: '#fff',
    flex: 1,
  },
  menuValue: {
    fontSize: 14,
    color: '#999',
    marginRight: 8,
  },
  menuArrow: {
    fontSize: 24,
    color: '#666',
  },
  dangerSection: {
    marginTop: 20,
    marginBottom: 30,
  },
  dangerButton: {
    backgroundColor: '#3a1a1a',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#5a2a2a',
  },
  dangerButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ff6b6b',
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 5,
  },
});

