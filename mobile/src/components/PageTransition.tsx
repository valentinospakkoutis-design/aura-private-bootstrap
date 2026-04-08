import React, { useEffect, useRef } from 'react';
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
  const hasAnimated = useRef(false);
  const opacity = useSharedValue(hasAnimated.current ? 1 : 0);
  const translateX = useSharedValue(hasAnimated.current ? 0 : 50);
  const translateY = useSharedValue(hasAnimated.current ? 0 : 30);
  const scale = useSharedValue(hasAnimated.current ? 1 : 0.9);

  useEffect(() => {
    if (hasAnimated.current) {
      opacity.value = 1;
      translateX.value = 0;
      translateY.value = 0;
      scale.value = 1;
      return;
    }

    opacity.value = withTiming(1, {
      duration: 300,
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

    hasAnimated.current = true;
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

