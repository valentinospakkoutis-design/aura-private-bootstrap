import React, { useEffect } from 'react';
import { Text, TextStyle } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { theme } from '../constants/theme';

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  style?: TextStyle;
}

const AnimatedText = Animated.createAnimatedComponent(Text);

export const AnimatedCounter: React.FC<AnimatedCounterProps> = ({
  value,
  duration = 1000,
  decimals = 0,
  prefix = '',
  suffix = '',
  style,
}) => {
  const animatedValue = useSharedValue(0);

  useEffect(() => {
    animatedValue.value = withTiming(value, {
      duration,
      easing: Easing.out(Easing.cubic),
    });
  }, [value, duration]);

  const animatedProps = useAnimatedProps(() => {
    const displayValue = animatedValue.value.toFixed(decimals);
    return {
      text: `${prefix}${displayValue}${suffix}`,
    } as any;
  });

  return (
    <AnimatedText
      animatedProps={animatedProps}
      style={[
        {
          fontSize: theme.typography.sizes['2xl'],
          fontFamily: theme.typography.fontFamily.mono,
          fontWeight: '700',
          color: theme.colors.text.primary,
        },
        style,
      ]}
    />
  );
};

