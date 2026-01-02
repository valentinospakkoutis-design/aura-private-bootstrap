import React, { useEffect } from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  withDelay,
  Easing,
} from 'react-native-reanimated';
import { theme } from '../constants/theme';

interface AnimatedCardProps {
  children: React.ReactNode;
  delay?: number;
  style?: ViewStyle;
  animationType?: 'fade' | 'slide' | 'scale' | 'slideUp';
}

export const AnimatedCard: React.FC<AnimatedCardProps> = ({
  children,
  delay = 0,
  style,
  animationType = 'slideUp',
}) => {
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(30);
  const translateX = useSharedValue(50);
  const scale = useSharedValue(0.9);

  useEffect(() => {
    // Fade animation
    opacity.value = withDelay(
      delay,
      withTiming(1, {
        duration: 600,
        easing: Easing.out(Easing.cubic),
      })
    );

    // Slide up animation
    if (animationType === 'slideUp') {
      translateY.value = withDelay(
        delay,
        withSpring(0, {
          damping: 20,
          stiffness: 90,
        })
      );
    }

    // Slide from right animation
    if (animationType === 'slide') {
      translateX.value = withDelay(
        delay,
        withSpring(0, {
          damping: 20,
          stiffness: 90,
        })
      );
    }

    // Scale animation
    if (animationType === 'scale') {
      scale.value = withDelay(
        delay,
        withSpring(1, {
          damping: 15,
          stiffness: 100,
        })
      );
    }
  }, [delay, animationType]);

  const animatedStyle = useAnimatedStyle(() => {
    switch (animationType) {
      case 'fade':
        return {
          opacity: opacity.value,
        };
      case 'slide':
        return {
          opacity: opacity.value,
          transform: [{ translateX: translateX.value }],
        };
      case 'scale':
        return {
          opacity: opacity.value,
          transform: [{ scale: scale.value }],
        };
      case 'slideUp':
      default:
        return {
          opacity: opacity.value,
          transform: [{ translateY: translateY.value }],
        };
    }
  });

  return (
    <Animated.View style={[styles.card, animatedStyle, style]}>
      {children}
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
});

