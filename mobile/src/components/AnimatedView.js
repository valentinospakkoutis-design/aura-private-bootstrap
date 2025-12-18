// Animated View Component
// Provides smooth animations and transitions

import React, { useEffect, useRef } from 'react';
import { Animated, View, StyleSheet } from 'react-native';

/**
 * Animated View with fade-in animation
 */
export function AnimatedFadeIn({ children, duration = 300, delay = 0, style }) {
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration,
      delay,
      useNativeDriver: true,
    }).start();
  }, []);

  return (
    <Animated.View style={[style, { opacity: fadeAnim }]}>
      {children}
    </Animated.View>
  );
}

/**
 * Animated View with slide-in from bottom
 */
export function AnimatedSlideUp({ children, duration = 400, delay = 0, style }) {
  const slideAnim = useRef(new Animated.Value(100)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideAnim, {
        toValue: 0,
        duration,
        delay,
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration,
        delay,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <Animated.View
      style={[
        style,
        {
          transform: [{ translateY: slideAnim }],
          opacity: fadeAnim,
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/**
 * Animated View with scale animation
 */
export function AnimatedScale({ children, duration = 300, delay = 0, style, scaleFrom = 0.8 }) {
  const scaleAnim = useRef(new Animated.Value(scaleFrom)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1,
        delay,
        useNativeDriver: true,
        tension: 50,
        friction: 7,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration,
        delay,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <Animated.View
      style={[
        style,
        {
          transform: [{ scale: scaleAnim }],
          opacity: fadeAnim,
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/**
 * Animated Pressable with scale feedback
 */
export function AnimatedPressable({ children, onPress, style, disabled = false }) {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    Animated.spring(scaleAnim, {
      toValue: 0.95,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      useNativeDriver: true,
    }).start();
  };

  return (
    <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
      <View
        onStartShouldSetResponder={() => !disabled}
        onResponderGrant={handlePressIn}
        onResponderRelease={handlePressOut}
        onResponderTerminate={handlePressOut}
        style={style}
      >
        {children}
      </View>
    </Animated.View>
  );
}

