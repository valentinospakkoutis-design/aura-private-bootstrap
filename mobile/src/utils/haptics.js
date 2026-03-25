// Haptic Feedback Utilities
// Provides haptic feedback for better UX

import { Platform } from 'react-native';
import * as Haptics from 'expo-haptics';

const isNative = Platform.OS !== 'web';

/**
 * Light impact feedback (for selections)
 */
export function lightImpact() {
  if (!isNative) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Medium impact feedback (for actions)
 */
export function mediumImpact() {
  if (!isNative) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Heavy impact feedback (for important actions)
 */
export function heavyImpact() {
  if (!isNative) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Success feedback (for successful actions)
 */
export function successFeedback() {
  if (!isNative) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Error feedback (for errors)
 */
export function errorFeedback() {
  if (!isNative) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Warning feedback (for warnings)
 */
export function warningFeedback() {
  if (!isNative) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
  } catch (error) {
    // Haptics not available
  }
}

/**
 * Selection feedback (for pickers, toggles)
 */
export function selectionFeedback() {
  lightImpact();
}

/**
 * Button press feedback
 */
export function buttonPressFeedback() {
  mediumImpact();
}

/**
 * Long press feedback
 */
export function longPressFeedback() {
  heavyImpact();
}

