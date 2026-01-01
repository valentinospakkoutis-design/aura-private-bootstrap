// Theme Configuration
// Centralized theme system for AURA app

export const theme = {
  colors: {
    brand: {
      primary: '#4CAF50',
      secondary: '#2196F3',
      accent: '#FFA726',
    },
    semantic: {
      success: '#4CAF50',
      error: '#ff6b6b',
      warning: '#FFA726',
      info: '#2196F3',
    },
    ui: {
      background: '#0f0f0f',
      surface: '#1a1a1a',
      cardBackground: '#2a2a2a',
      border: '#2a2a2a',
    },
    text: {
      primary: '#ffffff',
      secondary: '#999999',
      tertiary: '#666666',
      inverse: '#000000',
    },
  },
  typography: {
    fontFamily: {
      primary: 'System',
      secondary: 'System',
    },
    sizes: {
      xs: 10,
      sm: 12,
      md: 14,
      lg: 16,
      xl: 18,
      '2xl': 20,
      '3xl': 24,
      '4xl': 32,
      '5xl': 40,
    },
    weights: {
      normal: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
    },
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    '2xl': 24,
    '3xl': 32,
    '4xl': 40,
  },
  borderRadius: {
    small: 4,
    medium: 8,
    large: 12,
    xl: 16,
    full: 9999,
  },
  shadows: {
    small: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.1,
      shadowRadius: 2,
      elevation: 2,
    },
    medium: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.15,
      shadowRadius: 4,
      elevation: 4,
    },
    large: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.2,
      shadowRadius: 8,
      elevation: 8,
    },
  },
};

