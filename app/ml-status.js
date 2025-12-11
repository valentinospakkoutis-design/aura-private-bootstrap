import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function MLStatusScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [mlStatus, setMlStatus] = useState(null);
  const [models, setModels] = useState([]);
  const [trainingConfigs, setTrainingConfigs] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load ML status
      const status = await api.get('/api/ml/status');
      setMlStatus(status);
      
      // Load models
      const modelsData = await api.get('/api/ml/models');
      setModels(modelsData.models || []);
      
      // Load training configs
      const configsData = await api.get('/api/ml/training/configs');
      setTrainingConfigs(configsData.configs || []);
    } catch (error) {
      console.error('Error loading ML data:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const formatBytes = (bytes) => {
    if (!bytes) return 'N/A';
    return `${bytes.toFixed(2)} MB`;
  };

  const formatTime = (ms) => {
    if (!ms) return 'N/A';
    return `${ms.toFixed(2)} ms`;
  };

  if (loading && !mlStatus) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση ML Status...</Text>
        </View>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>🤖 ML Status</Text>
        </View>

        {/* Overall Status */}
        {mlStatus && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 ML System Status</Text>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Total Models</Text>
              <Text style={styles.statusValue}>{mlStatus.models.total_models}</Text>
            </View>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Ready Models</Text>
              <Text style={[styles.statusValue, { color: '#4CAF50' }]}>
                {mlStatus.models.ready_models}
              </Text>
            </View>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Deployed Models</Text>
              <Text style={[styles.statusValue, { color: '#4CAF50' }]}>
                {mlStatus.models.deployed_models}
              </Text>
            </View>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>MLX Models (iOS)</Text>
              <Text style={styles.statusValue}>{mlStatus.models.mlx_models}</Text>
            </View>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>ONNX Models (Android)</Text>
              <Text style={styles.statusValue}>{mlStatus.models.onnx_models}</Text>
            </View>
            
            <View style={styles.platformsSection}>
              <Text style={styles.platformsTitle}>Supported Platforms:</Text>
              {mlStatus.platforms_supported.map((platform, index) => (
                <Text key={index} style={styles.platformText}>• {platform}</Text>
              ))}
            </View>
          </View>
        )}

        {/* Models List */}
        {models.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📦 ML Models</Text>
            
            {models.map((model, index) => (
              <View key={index} style={styles.modelCard}>
                <View style={styles.modelHeader}>
                  <Text style={styles.modelName}>{model.model_id}</Text>
                  <View style={[styles.statusBadge, { backgroundColor: getStatusColor(model.status) }]}>
                    <Text style={styles.statusBadgeText}>{model.status.toUpperCase()}</Text>
                  </View>
                </View>
                
                <Text style={styles.modelDescription}>{model.description}</Text>
                
                <View style={styles.modelDetails}>
                  <View style={styles.modelDetail}>
                    <Text style={styles.modelDetailLabel}>Type:</Text>
                    <Text style={styles.modelDetailValue}>{model.type}</Text>
                  </View>
                  
                  <View style={styles.modelDetail}>
                    <Text style={styles.modelDetailLabel}>Format:</Text>
                    <Text style={styles.modelDetailValue}>{model.format.toUpperCase()}</Text>
                  </View>
                  
                  <View style={styles.modelDetail}>
                    <Text style={styles.modelDetailLabel}>Version:</Text>
                    <Text style={styles.modelDetailValue}>{model.version}</Text>
                  </View>
                  
                  {model.size_mb && (
                    <View style={styles.modelDetail}>
                      <Text style={styles.modelDetailLabel}>Size:</Text>
                      <Text style={styles.modelDetailValue}>{formatBytes(model.size_mb)}</Text>
                    </View>
                  )}
                  
                  {model.metrics.accuracy && (
                    <View style={styles.modelDetail}>
                      <Text style={styles.modelDetailLabel}>Accuracy:</Text>
                      <Text style={[styles.modelDetailValue, { color: '#4CAF50' }]}>
                        {(model.metrics.accuracy * 100).toFixed(1)}%
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Training Status */}
        {mlStatus && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>🎓 Training Preparation</Text>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Training Configs</Text>
              <Text style={styles.statusValue}>
                {mlStatus.training.total_configs}
              </Text>
            </View>
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Ready Configs</Text>
              <Text style={[styles.statusValue, { color: '#4CAF50' }]}>
                {mlStatus.training.ready_configs}
              </Text>
            </View>
            
            <View style={styles.datasetsSection}>
              <Text style={styles.datasetsTitle}>Supported Datasets:</Text>
              {mlStatus.training.supported_datasets.map((dataset, index) => (
                <Text key={index} style={styles.datasetText}>• {dataset}</Text>
              ))}
            </View>
          </View>
        )}

        {/* Info */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ On-Device ML</Text>
          <Text style={styles.infoText}>
            Το AURA υποστηρίζει on-device ML για:
          </Text>
          <Text style={styles.infoText}>• Price predictions (MLX/ONNX)</Text>
          <Text style={styles.infoText}>• Sentiment analysis</Text>
          <Text style={styles.infoText}>• Trading signal classification</Text>
          <Text style={styles.infoText}>• 100% privacy - όλα on-device</Text>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            🤖 ML Status - On-Device AI Preparation
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const getStatusColor = (status) => {
  switch (status) {
    case 'ready':
      return '#4CAF50';
    case 'deployed':
      return '#2196F3';
    case 'training':
      return '#FFA726';
    case 'archived':
      return '#999';
    default:
      return '#3a3a3a';
  }
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  content: {
    padding: 20,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    color: '#999',
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
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  statusLabel: {
    fontSize: 14,
    color: '#999',
  },
  statusValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  platformsSection: {
    marginTop: 15,
    paddingTop: 15,
    borderTopWidth: 1,
    borderTopColor: '#2a2a2a',
  },
  platformsTitle: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
  },
  platformText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  modelCard: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 12,
  },
  modelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  modelName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#fff',
  },
  modelDescription: {
    fontSize: 12,
    color: '#999',
    marginBottom: 12,
  },
  modelDetails: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  modelDetail: {
    flexDirection: 'row',
    marginRight: 15,
  },
  modelDetailLabel: {
    fontSize: 12,
    color: '#999',
    marginRight: 5,
  },
  modelDetailValue: {
    fontSize: 12,
    color: '#fff',
    fontWeight: 'bold',
  },
  datasetsSection: {
    marginTop: 15,
    paddingTop: 15,
    borderTopWidth: 1,
    borderTopColor: '#2a2a2a',
  },
  datasetsTitle: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
  },
  datasetText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
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
    marginBottom: 5,
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

