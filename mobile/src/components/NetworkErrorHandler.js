// Network Error Handler Component
// Displays network error state and retry functionality

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import api from '../services/api';

export default function NetworkErrorHandler({ 
  onRetry, 
  error,
  message,
  showRetry = true 
}) {
  const [isChecking, setIsChecking] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    setIsChecking(true);
    const online = await api.isOnline();
    setIsOnline(online);
    setIsChecking(false);
  };

  const handleRetry = async () => {
    await checkConnection();
    if (onRetry) {
      onRetry();
    }
  };

  if (!error && isOnline) {
    return null;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.emoji}>📡</Text>
      <Text style={styles.title}>
        {isOnline ? 'Σφάλμα Σύνδεσης' : 'Χωρίς Σύνδεση'}
      </Text>
      <Text style={styles.message}>
        {message || (isOnline 
          ? 'Δεν ήταν δυνατή η σύνδεση με τον διακομιστή.'
          : 'Δεν υπάρχει σύνδεση στο διαδίκτυο. Ελέγξτε τη σύνδεσή σας.')}
      </Text>
      
      {isChecking && (
        <ActivityIndicator 
          size="small" 
          color="#4CAF50" 
          style={styles.loader}
        />
      )}
      
      {showRetry && !isChecking && (
        <TouchableOpacity
          style={styles.retryButton}
          onPress={handleRetry}
        >
          <Text style={styles.retryButtonText}>Δοκιμάστε Ξανά</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
    backgroundColor: '#0f0f0f',
    minHeight: 300,
  },
  emoji: {
    fontSize: 48,
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 12,
    textAlign: 'center',
  },
  message: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  loader: {
    marginTop: 16,
  },
  retryButton: {
    backgroundColor: '#4CAF50',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

