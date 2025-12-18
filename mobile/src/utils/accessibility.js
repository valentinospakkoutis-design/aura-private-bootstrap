// Accessibility Utilities
// Provides accessibility helpers and constants

/**
 * Accessibility labels for common actions
 */
export const a11yLabels = {
  // Navigation
  backButton: 'Πίσω',
  homeButton: 'Αρχική',
  settingsButton: 'Ρυθμίσεις',
  profileButton: 'Προφίλ',
  
  // Trading
  buyButton: 'Αγορά',
  sellButton: 'Πώληση',
  placeOrder: 'Τοποθέτηση παραγγελίας',
  cancelOrder: 'Ακύρωση παραγγελίας',
  
  // Forms
  emailInput: 'Email',
  passwordInput: 'Κωδικός πρόσβασης',
  apiKeyInput: 'API Key',
  apiSecretInput: 'API Secret',
  quantityInput: 'Ποσότητα',
  priceInput: 'Τιμή',
  
  // Status
  loading: 'Φόρτωση',
  error: 'Σφάλμα',
  success: 'Επιτυχία',
  emptyState: 'Δεν υπάρχουν δεδομένα',
  
  // Notifications
  notificationBadge: 'Μη διαβασμένες ειδοποιήσεις',
  markAsRead: 'Σήμανση ως διαβασμένη',
  deleteNotification: 'Διαγραφή ειδοποιήσης',
  
  // Theme
  toggleTheme: 'Εναλλαγή θέματος',
  darkMode: 'Σκοτεινό θέμα',
  lightMode: 'Φωτεινό θέμα',
};

/**
 * Accessibility hints for actions
 */
export const a11yHints = {
  backButton: 'Επιστροφή στην προηγούμενη οθόνη',
  toggleTheme: 'Εναλλαγή μεταξύ φωτεινού και σκοτεινού θέματος',
  refresh: 'Ανανέωση δεδομένων',
  delete: 'Διαγραφή στοιχείου',
  edit: 'Επεξεργασία στοιχείου',
  save: 'Αποθήκευση αλλαγών',
  cancel: 'Ακύρωση',
};

/**
 * Get accessibility props for a component
 */
export function getA11yProps(label, hint = null, role = 'button') {
  return {
    accessible: true,
    accessibilityLabel: label,
    accessibilityHint: hint,
    accessibilityRole: role,
  };
}

/**
 * Get accessibility props for input fields
 */
export function getA11yInputProps(label, hint = null, required = false) {
  return {
    accessible: true,
    accessibilityLabel: label,
    accessibilityHint: hint,
    accessibilityRole: 'text',
    accessibilityRequired: required,
  };
}

/**
 * Get accessibility props for images
 */
export function getA11yImageProps(label, decorative = false) {
  return {
    accessible: !decorative,
    accessibilityLabel: decorative ? undefined : label,
    accessibilityRole: decorative ? 'none' : 'image',
  };
}

/**
 * Screen reader announcements
 */
export function announce(message, priority = 'polite') {
  // This would integrate with screen reader APIs
  // For React Native, you might use AccessibilityInfo
  if (__DEV__) {
    console.log(`[A11y Announcement] ${message}`);
  }
}

