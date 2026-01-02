import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  Easing,
} from 'react-native-reanimated';
import { theme } from '../constants/theme';

interface AnimatedProgressBarProps {
  progress: number; // 0 to 1
  color?: string;
  backgroundColor?: string;
  height?: number;
  showLabel?: boolean;
  animated?: boolean;
}

export const AnimatedProgressBar: React.FC<AnimatedProgressBarProps> = ({
  progress,
  color = theme.colors.brand.primary,
  backgroundColor = theme.colors.ui.border,
  height = 8,
  showLabel = false,
  animated = true,
}) => {
  const width = useSharedValue(0);

  useEffect(() => {
    if (animated) {
      width.value = withSpring(progress * 100, {
        damping: 20,
        stiffness: 90,
      });
    } else {
      width.value = progress * 100;
    }
  }, [progress, animated]);

  const animatedStyle = useAnimatedStyle(() => ({
    width: `${width.value}%`,
  }));

  return (
    <View style={styles.container}>
      <View style={[styles.track, { height, backgroundColor }]}>
        <Animated.View
          style={[
            styles.fill,
            { height, backgroundColor: color },
            animatedStyle,
          ]}
        />
      </View>
      {showLabel && (
        <Text style={styles.label}>{Math.round(progress * 100)}%</Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  track: {
    width: '100%',
    borderRadius: theme.borderRadius.medium,
    overflow: 'hidden',
  },
  fill: {
    borderRadius: theme.borderRadius.medium,
  },
  label: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginTop: theme.spacing.xs,
    textAlign: 'right',
  },
});

