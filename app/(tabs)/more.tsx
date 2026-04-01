import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../../mobile/src/constants/theme';

const MORE_ITEMS = [
  { icon: '📊', title: 'Analytics', href: '/analytics' },
  { icon: '🔗', title: 'Brokers', href: '/brokers' },
  { icon: '👤', title: 'Profile', href: '/profile' },
  { icon: '🔔', title: 'Notifications', href: '/notifications' },
  { icon: '🎙️', title: 'Voice Briefing', href: '/voice-briefing' },
  { icon: '📝', title: 'Paper Trading', href: '/paper-trading' },
  { icon: '💰', title: 'Live Trading', href: '/live-trading' },
  { icon: '⚙️', title: 'Settings', href: '/settings' },
];

export default function MoreScreen() {
  const router = useRouter();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>More</Text>
      {MORE_ITEMS.map((item) => (
        <TouchableOpacity
          key={item.href}
          style={styles.item}
          onPress={() => router.push({ pathname: item.href } as any)}
          activeOpacity={0.7}
        >
          <Text style={styles.icon}>{item.icon}</Text>
          <Text style={styles.label}>{item.title}</Text>
          <Text style={styles.arrow}>→</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xl,
    marginTop: theme.spacing.lg,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.ui.cardBackground,
    padding: theme.spacing.lg,
    borderRadius: theme.borderRadius.xl,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  icon: {
    fontSize: 24,
    marginRight: theme.spacing.md,
  },
  label: {
    flex: 1,
    fontSize: theme.typography.sizes.lg,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  arrow: {
    fontSize: 18,
    color: theme.colors.text.secondary,
  },
});
