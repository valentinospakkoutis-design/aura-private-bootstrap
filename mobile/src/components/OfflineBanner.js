// Offline Banner Component
// Displays a banner when device is offline

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { useNetworkStatus } from '../hooks/useNetworkStatus';

export default function OfflineBanner() {
  const { isOnline, isChecking, checkConnection } = useNetworkStatus({
    checkInterval: 3000
  });

  if (isOnline || isChecking) {
    return null;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.text}>📡 Χωρίς σύνδεση στο διαδίκτυο</Text>
      <TouchableOpacity
        style={styles.button}
        onPress={checkConnection}
      >
        <Text style={styles.buttonText}>Ελέγξτε ξανά</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#ff6b6b',
    paddingVertical: 8,
    paddingHorizontal: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    zIndex: 1000,
  },
  text: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  button: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    borderRadius: 4,
  },
  buttonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
});

