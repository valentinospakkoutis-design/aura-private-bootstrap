import { useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { ANIMATION_PRESETS } from '../utils/AnimationPresets';

export function useAnimation() {
  const animatedValue = useSharedValue(0);

  const animateWithSpring = (
    toValue: number,
    preset: keyof typeof ANIMATION_PRESETS.spring = 'gentle'
  ) => {
    animatedValue.value = withSpring(toValue, ANIMATION_PRESETS.spring[preset]);
  };

  const animateWithTiming = (
    toValue: number,
    duration: number = ANIMATION_PRESETS.timing.normal,
    easing: keyof typeof ANIMATION_PRESETS.easing = 'easeOut'
  ) => {
    animatedValue.value = withTiming(toValue, {
      duration,
      easing: ANIMATION_PRESETS.easing[easing],
    });
  };

  const reset = () => {
    animatedValue.value = 0;
  };

  return {
    animatedValue,
    animateWithSpring,
    animateWithTiming,
    reset,
  };
}

