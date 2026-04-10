import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { theme } from '../../mobile/src/constants/theme';
import PaperTradingScreen from '../paper-trading';
import LiveTradingScreen from '../live-trading';

export default function TradingTab() {
  const [mode, setMode] = useState<'paper' | 'live'>('paper');

  return (
    <View style={styles.container}>
      {/* Mode Toggle */}
      <View style={styles.toggle}>
        <TouchableOpacity
          style={[styles.toggleBtn, mode === 'paper' && styles.toggleActive]}
          onPress={() => setMode('paper')}
        >
          <Text style={[styles.toggleText, mode === 'paper' && styles.toggleTextActive]}>
            📊 Paper
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.toggleBtn, mode === 'live' && styles.toggleActive]}
          onPress={() => setMode('live')}
        >
          <Text style={[styles.toggleText, mode === 'live' && styles.toggleTextActive]}>
            💰 Live
          </Text>
        </TouchableOpacity>
      </View>

      {/* Screen Content */}
      {mode === 'paper' ? <PaperTradingScreen /> : <LiveTradingScreen />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.ui.background },
  toggle: {
    flexDirection: 'row',
    margin: theme.spacing.md,
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.lg,
    padding: 4,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
    borderRadius: theme.borderRadius.md,
  },
  toggleActive: {
    backgroundColor: theme.colors.brand.primary,
  },
  toggleText: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  toggleTextActive: {
    color: '#FFFFFF',
  },
});

