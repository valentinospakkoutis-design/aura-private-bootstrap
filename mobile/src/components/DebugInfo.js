// Debug Info Component
// Shows API URL, environment, and connection status for troubleshooting

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import Constants from 'expo-constants';
import { API_BASE_URL, config, appInfo } from '../config/environment';
import api from '../services/api';

export default function DebugInfo({ visible = false, onClose }) {
  const [isOnline, setIsOnline] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (visible) {
      checkStatus();
    }
  }, [visible]);

  const checkStatus = async () => {
    setChecking(true);
    try {
      const online = await api.isOnline();
      setIsOnline(online);
      
      if (online) {
        try {
          const health = await api.checkHealth();
          setHealthStatus(health);
        } catch (err) {
          setHealthStatus({ error: err.message });
        }
      } else {
        setHealthStatus(null);
      }
    } catch (err) {
      setIsOnline(false);
      setHealthStatus({ error: err.message });
    } finally {
      setChecking(false);
    }
  };

  if (!visible) return null;

  return (
    <View style={styles.overlay}>
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>🔍 Debug Information</Text>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <Text style={styles.closeText}>✕</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Environment</Text>
          <InfoRow label="Environment" value={config.environment} />
          <InfoRow label="Is Development" value={config.isDevelopment ? 'Yes' : 'No'} />
          <InfoRow label="Is Production" value={config.isProduction ? 'Yes' : 'No'} />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>API Configuration</Text>
          <InfoRow label="API Base URL" value={API_BASE_URL} />
          <InfoRow label="API Timeout" value={`${config.apiTimeout}ms`} />
          <InfoRow label="Cache Enabled" value={config.enableCache ? 'Yes' : 'No'} />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>App Info</Text>
          <InfoRow label="Version" value={appInfo.version} />
          <InfoRow label="Build Number" value={appInfo.buildNumber} />
          <InfoRow label="Expo SDK" value={Constants.expoConfig?.sdkVersion || 'N/A'} />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Connection Status</Text>
          <TouchableOpacity 
            onPress={checkStatus} 
            disabled={checking}
            style={styles.checkButton}
          >
            <Text style={styles.checkButtonText}>
              {checking ? 'Checking...' : '🔄 Check Status'}
            </Text>
          </TouchableOpacity>
          
          {isOnline !== null && (
            <>
              <InfoRow 
                label="Online Status" 
                value={isOnline ? '✅ Online' : '❌ Offline'} 
              />
              
              {healthStatus && (
                <View style={styles.healthContainer}>
                  <Text style={styles.healthLabel}>Health Check:</Text>
                  {healthStatus.error ? (
                    <Text style={styles.healthError}>❌ {healthStatus.error}</Text>
                  ) : (
                    <Text style={styles.healthSuccess}>
                      ✅ Backend is reachable
                    </Text>
                  )}
                </View>
              )}
            </>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Troubleshooting</Text>
          <Text style={styles.troubleshootText}>
            • If API URL is local IP (192.168.x.x), ensure you're on the same WiFi network
          </Text>
          <Text style={styles.troubleshootText}>
            • If backend is not reachable, check if backend server is running
          </Text>
          <Text style={styles.troubleshootText}>
            • For production, update API URL in environment.js
          </Text>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            This debug info helps identify connection issues
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

function InfoRow({ label, value }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}:</Text>
      <Text style={styles.infoValue} numberOfLines={2}>{value || 'N/A'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    zIndex: 9999,
  },
  container: {
    flex: 1,
    padding: 20,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 30,
    paddingTop: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  closeButton: {
    padding: 8,
  },
  closeText: {
    fontSize: 24,
    color: '#fff',
  },
  section: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4CAF50',
    marginBottom: 12,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  infoLabel: {
    fontSize: 14,
    color: '#999',
    flex: 1,
  },
  infoValue: {
    fontSize: 14,
    color: '#fff',
    flex: 2,
    textAlign: 'right',
    fontWeight: '500',
  },
  checkButton: {
    backgroundColor: '#4CAF50',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  checkButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  healthContainer: {
    marginTop: 8,
    padding: 12,
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
  },
  healthLabel: {
    fontSize: 14,
    color: '#999',
    marginBottom: 4,
  },
  healthSuccess: {
    fontSize: 14,
    color: '#4CAF50',
  },
  healthError: {
    fontSize: 14,
    color: '#ff6b6b',
  },
  troubleshootText: {
    fontSize: 12,
    color: '#999',
    marginBottom: 8,
    lineHeight: 18,
  },
  footer: {
    marginTop: 20,
    marginBottom: 40,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
});

