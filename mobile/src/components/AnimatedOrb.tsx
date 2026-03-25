import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Dimensions, Animated } from 'react-native';
import { theme } from '../constants/theme';

const { width } = Dimensions.get('window');

interface AnimatedOrbProps {
  state?: 'calm' | 'bullish' | 'bearish' | 'thinking' | 'alert';
  size?: number;
}

export const AnimatedOrb: React.FC<AnimatedOrbProps> = ({
  state = 'calm',
  size = width * 0.6,
}) => {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const getOrbColor = () => {
    switch (state) {
      case 'bullish':
        return theme.colors.market.bullish;
      case 'bearish':
        return theme.colors.market.bearish;
      case 'thinking':
        return theme.colors.brand.secondary;
      case 'alert':
        return theme.colors.semantic.warning;
      case 'calm':
      default:
        return theme.colors.brand.primary;
    }
  };

  useEffect(() => {
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(scaleAnim, { toValue: 1.1, duration: 1500, useNativeDriver: true }),
        Animated.timing(scaleAnim, { toValue: 1.0, duration: 1500, useNativeDriver: true }),
      ])
    );
    breathe.start();
    return () => breathe.stop();
  }, []);

  const color = getOrbColor();

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Animated.View
        style={[
          styles.orb,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: color,
            transform: [{ scale: scaleAnim }],
            shadowColor: color,
            shadowOffset: { width: 0, height: 0 },
            shadowOpacity: 0.8,
            shadowRadius: size * 0.15,
          },
        ]}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
  },
  orb: {
    opacity: 0.9,
  },
});
