// Theme Configuration
// Centralized theme system for AURA app

// Light theme colors
const lightColors = {
  brand: {
    primary: '#6366F1',
    secondary: '#8B5CF6',
    tertiary: '#EC4899',
  },
  accent: {
    blue: '#3B82F6',
    purple: '#A855F7',
    pink: '#F472B6',
    orange: '#F97316',
  },
  market: {
    bullish: '#10B981',
    bearish: '#EF4444',
    neutral: '#6B7280',
  },
  text: {
    primary: '#111827',
    secondary: '#6B7280',
    tertiary: '#9CA3AF',
    inverse: '#FFFFFF',
  },
  ui: {
    background: '#F9FAFB',
    cardBackground: '#FFFFFF',
    border: '#E5E7EB',
  },
  semantic: {
    success: '#10B981',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
  },
};

// Dark theme colors
const darkColors = {
  brand: {
    primary: '#818CF8',
    secondary: '#A78BFA',
    tertiary: '#F472B6',
  },
  accent: {
    blue: '#60A5FA',
    purple: '#C084FC',
    pink: '#F9A8D4',
    orange: '#FB923C',
  },
  market: {
    bullish: '#34D399',
    bearish: '#F87171',
    neutral: '#9CA3AF',
  },
  text: {
    primary: '#F9FAFB',
    secondary: '#D1D5DB',
    tertiary: '#9CA3AF',
    inverse: '#0F172A',
  },
  ui: {
    background: '#0F172A',
    cardBackground: '#1E293B',
    border: '#334155',
  },
  semantic: {
    success: '#34D399',
    error: '#F87171',
    warning: '#FBBF24',
    info: '#60A5FA',
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
    '2xl': 48,
  },
  borderRadius: {
    small: 8,
    medium: 12,
    large: 16,
    xlarge: 24,
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
      xs: 12,
      sm: 14,
      md: 16,
      lg: 18,
      xl: 20,
      '2xl': 24,
      '3xl': 30,
      '4xl': 36,
    },
  },
  shadows: {
    small: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 2,
    },
    medium: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.15,
      shadowRadius: 8,
      elevation: 4,
    },
    large: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.2,
      shadowRadius: 16,
      elevation: 8,
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
