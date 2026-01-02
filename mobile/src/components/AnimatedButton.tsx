import React from 'react';
import { TouchableOpacity, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { theme } from '../constants/theme';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'gradient' | 'danger';
type ButtonSize = 'small' | 'medium' | 'large';

interface AnimatedButtonProps {
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

const AnimatedTouchable = Animated.createAnimatedComponent(TouchableOpacity);

export const AnimatedButton: React.FC<AnimatedButtonProps> = ({
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
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  const handlePressIn = () => {
    if (!disabled && !loading) {
      scale.value = withSpring(0.95, {
        damping: 15,
        stiffness: 300,
      });
      opacity.value = withTiming(0.8, { duration: 100 });
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  };

  const handlePressOut = () => {
    scale.value = withSpring(1, {
      damping: 15,
      stiffness: 300,
    });
    opacity.value = withTiming(1, { duration: 100 });
  };

  const handlePress = () => {
    if (!disabled && !loading) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      onPress();
    }
  };

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

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
        return { ...baseStyle, backgroundColor: theme.colors.brand.primary };
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

    if (variant === 'secondary' || variant === 'ghost') {
      return { ...baseTextStyle, color: theme.colors.brand.primary };
    }

    return baseTextStyle;
  };

  return (
    <AnimatedTouchable
      style={[
        getButtonStyle(),
        animatedStyle,
        disabled && styles.disabled,
        style,
      ]}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      onPress={handlePress}
      disabled={disabled || loading}
      activeOpacity={1}
    >
      {icon && <>{icon}</>}
      <Text style={[getTextStyle(), textStyle]}>{title}</Text>
    </AnimatedTouchable>
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

