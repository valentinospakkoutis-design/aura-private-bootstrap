import React, { useEffect, useState } from 'react';
import { Text, TextStyle, StyleProp } from 'react-native';
import Animated, {
  useSharedValue,
  withTiming,
  Easing,
  runOnJS,
  useAnimatedReaction,
} from 'react-native-reanimated';
import { theme } from '../constants/theme';

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  style?: StyleProp<TextStyle>;
}

export const AnimatedCounter: React.FC<AnimatedCounterProps> = ({
  value,
  duration = 1000,
  decimals = 0,
  prefix = '',
  suffix = '',
  style,
}) => {
  const safeValue = typeof value === 'number' && isFinite(value) ? value : 0;
  const animatedValue = useSharedValue(safeValue);
  const [displayText, setDisplayText] = useState(`${prefix}${safeValue.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    animatedValue.value = withTiming(safeValue, {
      duration,
      easing: Easing.out(Easing.cubic),
    });
  }, [safeValue, duration]);

  useAnimatedReaction(
    () => animatedValue.value,
    (current) => {
      const formatted = `${prefix}${current.toFixed(decimals)}${suffix}`;
      runOnJS(setDisplayText)(formatted);
    },
    [prefix, suffix, decimals]
  );

  return (
    <Text
      style={[
        {
          fontSize: theme.typography.sizes['2xl'],
          fontFamily: theme.typography.fontFamily.mono,
          fontWeight: '700',
          color: theme.colors.text.primary,
        },
        style,
      ]}
    >
      {displayText}
    </Text>
  );
};
