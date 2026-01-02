import { Easing } from 'react-native-reanimated';

export const ANIMATION_PRESETS = {
  // Timing presets
  timing: {
    fast: 200,
    normal: 400,
    slow: 600,
    verySlow: 1000,
  },

  // Spring presets
  spring: {
    gentle: {
      damping: 20,
      stiffness: 90,
    },
    bouncy: {
      damping: 10,
      stiffness: 100,
    },
    stiff: {
      damping: 15,
      stiffness: 300,
    },
    slow: {
      damping: 30,
      stiffness: 50,
    },
  },

  // Easing presets
  easing: {
    easeIn: Easing.in(Easing.ease),
    easeOut: Easing.out(Easing.ease),
    easeInOut: Easing.inOut(Easing.ease),
    linear: Easing.linear,
    bounce: Easing.bounce,
    elastic: Easing.elastic(2),
    back: Easing.back(1.5),
    bezier: Easing.bezier(0.25, 0.1, 0.25, 1),
  },

  // Common animation configs
  configs: {
    fadeIn: {
      duration: 400,
      easing: Easing.out(Easing.cubic),
    },
    slideIn: {
      damping: 20,
      stiffness: 90,
    },
    scaleIn: {
      damping: 15,
      stiffness: 100,
    },
    button: {
      damping: 15,
      stiffness: 300,
    },
  },
};

// Stagger delay calculator
export const getStaggerDelay = (index: number, baseDelay: number = 100): number => {
  return index * baseDelay;
};

// Interpolation helpers
export const interpolateColor = (
  progress: number,
  inputRange: number[],
  outputRange: string[]
): string => {
  // Simple color interpolation (you can enhance this)
  const index = Math.floor(progress * (outputRange.length - 1));
  return outputRange[Math.min(index, outputRange.length - 1)];
};

