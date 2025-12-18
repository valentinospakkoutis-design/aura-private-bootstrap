// Accessible Button Component
// Button with accessibility and haptic feedback

import React from 'react';
import { TouchableOpacity, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { getA11yProps } from '../utils/accessibility';
import { buttonPressFeedback } from '../utils/haptics';

export default function AccessibleButton({
  children,
  onPress,
  label,
  hint,
  loading = false,
  disabled = false,
  variant = 'primary', // primary, secondary, danger
  style,
  textStyle,
  ...props
}) {
  const { colors } = useTheme();

  const handlePress = () => {
    if (!disabled && !loading) {
      buttonPressFeedback();
      onPress?.();
    }
  };

  const getVariantStyles = () => {
    switch (variant) {
      case 'secondary':
        return {
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderWidth: 1,
        };
      case 'danger':
        return {
          backgroundColor: colors.error + '20',
          borderColor: colors.error,
          borderWidth: 1,
        };
      default:
        return {
          backgroundColor: colors.primary,
        };
    }
  };

  const getTextColor = () => {
    switch (variant) {
      case 'secondary':
        return colors.text;
      case 'danger':
        return colors.error;
      default:
        return '#fff';
    }
  };

  return (
    <TouchableOpacity
      style={[
        styles.button,
        getVariantStyles(),
        disabled && styles.disabled,
        style,
      ]}
      onPress={handlePress}
      disabled={disabled || loading}
      activeOpacity={0.7}
      {...getA11yProps(label || children, hint)}
      {...props}
    >
      {loading ? (
        <ActivityIndicator color={getTextColor()} size="small" />
      ) : (
        <Text style={[styles.text, { color: getTextColor() }, textStyle]}>
          {children}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
  },
  disabled: {
    opacity: 0.5,
  },
  text: {
    fontSize: 16,
    fontWeight: 'bold',
  },
});

