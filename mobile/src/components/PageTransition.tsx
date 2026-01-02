import React, { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  Easing,
} from 'react-native-reanimated';

interface PageTransitionProps {
  children: React.ReactNode;
  type?: 'fade' | 'slide' | 'scale' | 'slideUp';
}

export const PageTransition: React.FC<PageTransitionProps> = ({
  children,
  type = 'fade',
}) => {
  const opacity = useSharedValue(0);
  const translateX = useSharedValue(50);
  const translateY = useSharedValue(50);
  const scale = useSharedValue(0.9);

  useEffect(() => {
    opacity.value = withTiming(1, {
      duration: 400,
      easing: Easing.out(Easing.cubic),
    });

    if (type === 'slide') {
      translateX.value = withSpring(0, {
        damping: 20,
        stiffness: 90,
      });
    }

    if (type === 'slideUp') {
      translateY.value = withSpring(0, {
        damping: 20,
        stiffness: 90,
      });
    }

    if (type === 'scale') {
      scale.value = withSpring(1, {
        damping: 15,
        stiffness: 100,
      });
    }
  }, [type]);

  const animatedStyle = useAnimatedStyle(() => {
    switch (type) {
      case 'slide':
        return {
          opacity: opacity.value,
          transform: [{ translateX: translateX.value }],
        };
      case 'slideUp':
        return {
          opacity: opacity.value,
          transform: [{ translateY: translateY.value }],
        };
      case 'scale':
        return {
          opacity: opacity.value,
          transform: [{ scale: scale.value }],
        };
      case 'fade':
      default:
        return {
          opacity: opacity.value,
        };
    }
  });

  return (
    <Animated.View style={[styles.container, animatedStyle]}>
      {children}
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});

