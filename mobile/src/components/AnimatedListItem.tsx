import React, { useEffect, useRef } from 'react';
import { TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { Platform } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withDelay,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { theme } from '../constants/theme';

interface AnimatedListItemProps {
  children: React.ReactNode;
  index: number;
  onPress?: () => void;
  style?: ViewStyle;
  skipEntrance?: boolean;
}

const AnimatedTouchable = Animated.createAnimatedComponent(TouchableOpacity);

export const AnimatedListItem: React.FC<AnimatedListItemProps> = ({
  children,
  index,
  onPress,
  style,
  skipEntrance,
}) => {
  const hasAnimated = useRef(false);
  const opacity = useSharedValue(skipEntrance || hasAnimated.current ? 1 : 0);
  const translateY = useSharedValue(skipEntrance || hasAnimated.current ? 0 : 20);
  const scale = useSharedValue(1);

  useEffect(() => {
    if (hasAnimated.current || skipEntrance) {
      // Already animated once or skip requested — show immediately
      opacity.value = 1;
      translateY.value = 0;
      return;
    }

    const delay = Math.min(index * 80, 400); // Cap total stagger at 400ms

    opacity.value = withDelay(
      delay,
      withTiming(1, {
        duration: 300,
        easing: Easing.out(Easing.ease),
      })
    );

    translateY.value = withDelay(
      delay,
      withSpring(0, {
        damping: 15,
        stiffness: 100,
      })
    );

    hasAnimated.current = true;
  }, [index]);

  const handlePressIn = () => {
    scale.value = withSpring(0.98, {
      damping: 15,
      stiffness: 300,
    });
    Platform.OS !== 'web' && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  const handlePressOut = () => {
    scale.value = withSpring(1, {
      damping: 15,
      stiffness: 300,
    });
  };

  const handlePress = () => {
    Platform.OS !== 'web' && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onPress?.();
  };

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [
      { translateY: translateY.value },
      { scale: scale.value },
    ],
  }));

  return (
    <AnimatedTouchable
      style={[styles.item, animatedStyle, style]}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      onPress={handlePress}
      disabled={!onPress}
      activeOpacity={1}
    >
      {children}
    </AnimatedTouchable>
  );
};

const styles = StyleSheet.create({
  item: {
    marginBottom: theme.spacing.md,
  },
});

