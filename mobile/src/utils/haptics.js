// Haptic Feedback Utilities
// Provides haptic feedback for better UX

import * as Haptics from 'expo-haptics';

/**
 * Light impact feedback (for selections)
 */
export function lightImpact() {
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

