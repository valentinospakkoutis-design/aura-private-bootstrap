// Theme Toggle Component
// Button to toggle between light and dark mode

import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../context/ThemeContext';

export default function ThemeToggle() {
  const { isDark, toggleTheme, colors } = useTheme();

  return (
    <TouchableOpacity
      style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.border }]}
      onPress={toggleTheme}
    >
      <Text style={[styles.icon, { color: colors.text }]}>
        {isDark ? '☀️' : '🌙'}
      </Text>
      <Text style={[styles.text, { color: colors.textSecondary }]}>
        {isDark ? 'Light Mode' : 'Dark Mode'}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    gap: 8,
  },
  icon: {
    fontSize: 20,
  },
  text: {
    fontSize: 14,
    fontWeight: '500',
  },
});

