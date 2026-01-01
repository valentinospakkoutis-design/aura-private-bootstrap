import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from 'react-native';
import { useAppStore } from '@/stores/appStore';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/apiClient';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { NoPredictions } from '@/components/NoPredictions';
import { NoData } from '@/components/NoData';
import { theme } from '@/constants/theme';
import { useRouter } from 'expo-router';

interface Prediction {
  id: string;
  asset: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  price: number;
  targetPrice: number;
  timestamp: string;
  reasoning: string;
}

export default function AIPredictionsScreen() {
  const router = useRouter();
  const { predictions, setPredictions } = useAppStore();
  const [refreshing, setRefreshing] = useState(false);

  const {
    data,
    error,
    loading,
    execute: fetchPredictions,
  } = useApi(api.getPredictions);

  useEffect(() => {
    loadPredictions();
  }, []);

  const loadPredictions = async () => {
    try {
      const result = await fetchPredictions();
      setPredictions(result);
    } catch (err) {
      // Error handled by useApi
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadPredictions();
    setRefreshing(false);
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'buy':
        return theme.colors.market.bullish;
      case 'sell':
        return theme.colors.market.bearish;
      case 'hold':
        return theme.colors.market.neutral;
      default:
        return theme.colors.text.secondary;
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'buy':
        return '📈';
      case 'sell':
        return '📉';
      case 'hold':
        return '⏸️';
      default:
        return '❓';
    }
  };

  const renderPredictionCard = ({ item }: { item: Prediction }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/prediction-details?id=${item.id}`)}
      activeOpacity={0.8}
    >
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.assetContainer}>
          <Text style={styles.assetName}>{item.asset}</Text>
          <Text style={styles.timestamp}>
            {new Date(item.timestamp).toLocaleTimeString('el-GR', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </Text>
        </View>
        <View style={[styles.actionBadge, { backgroundColor: getActionColor(item.action) + '20' }]}>
          <Text style={styles.actionIcon}>{getActionIcon(item.action)}</Text>
          <Text style={[styles.actionText, { color: getActionColor(item.action) }]}>
            {item.action.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* Price Info */}
      <View style={styles.priceContainer}>
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Τρέχουσα Τιμή:</Text>
          <Text style={styles.priceValue}>${item.price.toLocaleString()}</Text>
        </View>
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Στόχος:</Text>
          <Text style={[styles.priceValue, { color: getActionColor(item.action) }]}>
            ${item.targetPrice.toLocaleString()}
          </Text>
        </View>
      </View>

      {/* Confidence */}
      <View style={styles.confidenceContainer}>
        <Text style={styles.confidenceLabel}>Βεβαιότητα AI:</Text>
        <View style={styles.confidenceBar}>
          <View
            style={[
              styles.confidenceFill,
              {
                width: `${item.confidence * 100}%`,
                backgroundColor: getActionColor(item.action),
              },
            ]}
          />
        </View>
        <Text style={styles.confidenceValue}>{(item.confidence * 100).toFixed(0)}%</Text>
      </View>

      {/* Reasoning Preview */}
      <Text style={styles.reasoning} numberOfLines={2}>
        {item.reasoning}
      </Text>

      {/* View Details */}
      <Text style={styles.viewDetails}>Δες Ανάλυση →</Text>
    </TouchableOpacity>
  );

  if (loading && !refreshing) {
    return <LoadingSpinner fullScreen message="Φόρτωση προβλέψεων..." />;
  }

  if (error && (!predictions || predictions.length === 0)) {
    return <NoData onRetry={loadPredictions} />;
  }

  if (!predictions || predictions.length === 0) {
    return <NoPredictions />;
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={predictions}
        keyExtractor={(item) => item.id}
        renderItem={renderPredictionCard}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.colors.brand.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  listContent: {
    padding: theme.spacing.md,
    gap: theme.spacing.md,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  assetContainer: {
    flex: 1,
  },
  assetName: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  timestamp: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  actionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.large,
    gap: theme.spacing.xs,
  },
  actionIcon: {
    fontSize: 16,
  },
  actionText: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
  },
  priceContainer: {
    marginBottom: theme.spacing.md,
    gap: theme.spacing.xs,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  priceLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  priceValue: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  confidenceContainer: {
    marginBottom: theme.spacing.md,
  },
  confidenceLabel: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xs,
  },
  confidenceBar: {
    height: 8,
    backgroundColor: theme.colors.ui.border,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: theme.spacing.xs,
  },
  confidenceFill: {
    height: '100%',
    borderRadius: 4,
  },
  confidenceValue: {
    fontSize: theme.typography.sizes.sm,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  reasoning: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
    marginBottom: theme.spacing.md,
  },
  viewDetails: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.brand.primary,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    textAlign: 'right',
  },
});

