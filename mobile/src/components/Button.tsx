import React from 'react';
import { TouchableOpacity, Text, StyleSheet, ActivityIndicator, ViewStyle, TextStyle } from 'react-native';
import * as Haptics from 'expo-haptics';
import { theme } from '../constants/theme';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'gradient' | 'danger';
type ButtonSize = 'small' | 'medium' | 'large';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  fullWidth?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  icon,
  fullWidth = false,
  style,
  textStyle,
}) => {
  const handlePress = () => {
    if (!disabled && !loading) {
      try {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      } catch (error) {
        console.warn('Haptics not available:', error);
      }
      onPress();
    }
  };

  const getButtonStyle = (): ViewStyle => {
    const baseStyle: ViewStyle = {
      ...styles.button,
      ...styles[`button_${size}`],
    };

    if (fullWidth) {
      baseStyle.width = '100%';
    }

    switch (variant) {
      case 'primary':
        return { ...baseStyle, backgroundColor: theme.colors.brand.primary };
      case 'secondary':
        return { ...baseStyle, backgroundColor: theme.colors.ui.cardBackground, borderWidth: 1, borderColor: theme.colors.brand.primary };
      case 'ghost':
        return { ...baseStyle, backgroundColor: 'transparent' };
      case 'gradient':
        return { ...baseStyle, backgroundColor: theme.colors.brand.primary }; // Will add LinearGradient later
      case 'danger':
        return { ...baseStyle, backgroundColor: theme.colors.semantic.error };
      default:
        return baseStyle;
    }
  };

  const getTextStyle = (): TextStyle => {
    const baseTextStyle: TextStyle = {
      ...styles.text,
      ...styles[`text_${size}`],
    };

    if (variant === 'secondary') {
      return { ...baseTextStyle, color: theme.colors.brand.primary };
    }

    if (variant === 'ghost') {
      return { ...baseTextStyle, color: theme.colors.brand.primary };
    }

    return baseTextStyle;
  };

  return (
    <TouchableOpacity
      style={[
        getButtonStyle(),
        disabled && styles.disabled,
        style,
      ]}
      onPress={handlePress}
      disabled={disabled || loading}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'secondary' || variant === 'ghost' ? theme.colors.brand.primary : '#FFFFFF'} />
      ) : (
        <>
          {icon && <>{icon}</>}
          <Text style={[getTextStyle(), textStyle]}>{title}</Text>
        </>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: theme.borderRadius.large,
    gap: theme.spacing.xs,
  },
  button_small: {
    paddingVertical: theme.spacing.xs,
    paddingHorizontal: theme.spacing.md,
    minHeight: 36,
  },
  button_medium: {
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    minHeight: 48,
  },
  button_large: {
    paddingVertical: theme.spacing.md,
    paddingHorizontal: theme.spacing.xl,
    minHeight: 56,
  },
  text: {
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  text_small: {
    fontSize: theme.typography.sizes.sm,
  },
  text_medium: {
    fontSize: theme.typography.sizes.md,
  },
  text_large: {
    fontSize: theme.typography.sizes.lg,
  },
  disabled: {
    opacity: 0.5,
  },
});

