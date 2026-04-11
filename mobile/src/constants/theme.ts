// Theme Configuration
// Centralized theme system for AURA app

// Light theme colors
const lightColors = {
  brand: {
    primary: '#6C63FF',
    secondary: '#6C63FF',
    tertiary: '#6C63FF',
  },
  accent: {
    blue: '#6C63FF',
    purple: '#6C63FF',
    pink: '#6C63FF',
    orange: '#6C63FF',
  },
  market: {
    bullish: '#00C853',
    bearish: '#FF3B30',
    neutral: '#6B7280',
  },
  text: {
    primary: '#0A0A0A',
    secondary: '#6B7280',
    tertiary: '#9CA3AF',
    inverse: '#FFFFFF',
  },
  ui: {
    background: '#FFFFFF',
    cardBackground: '#F8F9FA',
    border: '#E5E7EB',
  },
  semantic: {
    success: '#00C853',
    error: '#FF3B30',
    warning: '#F59E0B',
    info: '#6C63FF',
  },
};

// Dark theme colors
const darkColors = {
  brand: {
    primary: '#6C63FF',
    secondary: '#6C63FF',
    tertiary: '#6C63FF',
  },
  accent: {
    blue: '#6C63FF',
    purple: '#6C63FF',
    pink: '#6C63FF',
    orange: '#6C63FF',
  },
  market: {
    bullish: '#00C853',
    bearish: '#FF3B30',
    neutral: '#9CA3AF',
  },
  text: {
    primary: '#FFFFFF',
    secondary: '#9CA3AF',
    tertiary: '#9CA3AF',
    inverse: '#0A0A0A',
  },
  ui: {
    background: '#0A0A0A',
    cardBackground: '#1A1A1A',
    border: '#2A2A2A',
  },
  semantic: {
    success: '#00C853',
    error: '#FF3B30',
    warning: '#FBBF24',
    info: '#6C63FF',
  },
};

// Shared theme properties
const sharedTheme = {
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
    '2xl': 48,
  },
  borderRadius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    small: 8,
    medium: 12,
    large: 16,
    xlarge: 20,
    full: 9999,
  },
  typography: {
    fontFamily: {
      regular: 'System',
      medium: 'System',
      bold: 'System',
      mono: 'Courier',
    },
    sizes: {
      hero: 42,
      h1: 28,
      h2: 22,
      h3: 18,
      body: 16,
      small: 14,
      micro: 12,
      xs: 12,
      sm: 14,
      md: 16,
      lg: 18,
      xl: 20,
      '2xl': 24,
      '3xl': 30,
      '4xl': 36,
    },
    weights: {
      regular: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
    },
  },
  shadows: {
    small: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0,
      shadowRadius: 0,
      elevation: 0,
    },
    medium: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0,
      shadowRadius: 0,
      elevation: 0,
    },
    large: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0,
      shadowRadius: 0,
      elevation: 0,
    },
  },
};

// Export themes
export const lightTheme = {
  colors: lightColors,
  ...sharedTheme,
};

export const darkTheme = {
  colors: darkColors,
  ...sharedTheme,
};

// Default export (for backward compatibility)
export const theme = lightTheme;
