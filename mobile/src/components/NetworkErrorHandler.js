// Network Error Handler Component
// Displays network error state and retry functionality

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import api from '../services/api';
import { API_BASE_URL } from '../config/environment';

export default function NetworkErrorHandler({ 
  onRetry, 
  error,
  message,
  showRetry = true,
  showDebug = false,
  onShowDebug
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

  // Extract error details
  const getErrorDetails = () => {
    if (!error) return null;
    
    const errorMessage = error.message || error.userMessage || 'Unknown error';
    const isNetworkError = errorMessage.includes('Failed to fetch') || 
                          errorMessage.includes('Network') ||
                          errorMessage.includes('timeout');
    
    return {
      message: errorMessage,
      isNetworkError,
      isLocalIP: API_BASE_URL?.includes('192.168.') || API_BASE_URL?.includes('10.') || API_BASE_URL?.includes('172.'),
    };
  };

  const errorDetails = getErrorDetails();

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

      {/* Show API URL if it's local IP */}
      {errorDetails?.isLocalIP && (
        <View style={styles.warningBox}>
          <Text style={styles.warningText}>
            ⚠️ Το API URL είναι local IP ({API_BASE_URL})
          </Text>
          <Text style={styles.warningSubtext}>
            Βεβαιωθείτε ότι είστε στο ίδιο WiFi network
          </Text>
        </View>
      )}

      {/* Show error details in debug mode */}
      {showDebug && errorDetails && (
        <View style={styles.debugBox}>
          <Text style={styles.debugTitle}>Debug Info:</Text>
          <Text style={styles.debugText}>Error: {errorDetails.message}</Text>
          <Text style={styles.debugText}>API URL: {API_BASE_URL}</Text>
        </View>
      )}
      
      {isChecking && (
        <ActivityIndicator 
          size="small" 
          color="#4CAF50" 
          style={styles.loader}
        />
      )}
      
      <View style={styles.buttonRow}>
        {showRetry && !isChecking && (
          <TouchableOpacity
            style={styles.retryButton}
            onPress={handleRetry}
          >
            <Text style={styles.retryButtonText}>Δοκιμάστε Ξανά</Text>
          </TouchableOpacity>
        )}
        
        {onShowDebug && (
          <TouchableOpacity
            style={styles.debugButton}
            onPress={onShowDebug}
          >
            <Text style={styles.debugButtonText}>🔍 Debug Info</Text>
          </TouchableOpacity>
        )}
      </View>
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
  warningBox: {
    backgroundColor: '#3a2a1a',
    borderRadius: 8,
    padding: 12,
    marginTop: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#ff9800',
  },
  warningText: {
    color: '#ff9800',
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  warningSubtext: {
    color: '#ff9800',
    fontSize: 12,
    opacity: 0.8,
  },
  debugBox: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    marginTop: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  debugTitle: {
    color: '#4CAF50',
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  debugText: {
    color: '#999',
    fontSize: 11,
    marginBottom: 4,
    fontFamily: 'monospace',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'center',
  },
  debugButton: {
    backgroundColor: '#2a2a2a',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#4a4a4a',
  },
  debugButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
});

