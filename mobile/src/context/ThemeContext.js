// Theme Context
// Provides theme management (dark mode, colors, etc.)

import React, { createContext, useContext, useState, useEffect } from 'react';
import { useColorScheme } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const ThemeContext = createContext();

// Color schemes
const lightTheme = {
  name: 'light',
  colors: {
    primary: '#4CAF50',
    secondary: '#2196F3',
    background: '#ffffff',
    surface: '#f5f5f5',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    error: '#ff6b6b',
    success: '#4CAF50',
    warning: '#FFA726',
    info: '#2196F3',
  },
};

const darkTheme = {
  name: 'dark',
  colors: {
    primary: '#4CAF50',
    secondary: '#2196F3',
    background: '#0f0f0f',
    surface: '#1a1a1a',
    text: '#ffffff',
    textSecondary: '#999999',
    border: '#2a2a2a',
    error: '#ff6b6b',
    success: '#4CAF50',
    warning: '#FFA726',
    info: '#2196F3',
  },
};

const THEME_STORAGE_KEY = '@aura_theme';

export function ThemeProvider({ children }) {
  const systemColorScheme = useColorScheme();
  const [theme, setTheme] = useState(darkTheme); // Default to dark
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTheme();
  }, []);

  const loadTheme = async () => {
    try {
      const savedTheme = await SecureStore.getItemAsync(THEME_STORAGE_KEY);
      if (savedTheme) {
        setTheme(savedTheme === 'light' ? lightTheme : darkTheme);
      } else {
        // Use system preference if no saved theme
        setTheme(systemColorScheme === 'light' ? lightTheme : darkTheme);
      }
    } catch (error) {
      console.error('Error loading theme:', error);
      setTheme(darkTheme); // Fallback to dark
    } finally {
      setIsLoading(false);
    }
  };

  const toggleTheme = async () => {
    const newTheme = theme.name === 'dark' ? lightTheme : darkTheme;
    setTheme(newTheme);
    
    try {
      await SecureStore.setItemAsync(THEME_STORAGE_KEY, newTheme.name);
    } catch (error) {
      console.error('Error saving theme:', error);
    }
  };

  const setThemeMode = async (themeName) => {
    const newTheme = themeName === 'light' ? lightTheme : darkTheme;
    setTheme(newTheme);
    
    try {
      await SecureStore.setItemAsync(THEME_STORAGE_KEY, newTheme.name);
    } catch (error) {
      console.error('Error saving theme:', error);
    }
  };

  const value = {
    theme,
    isDark: theme.name === 'dark',
    isLight: theme.name === 'light',
    toggleTheme,
    setThemeMode,
    colors: theme.colors,
  };

  if (isLoading) {
    return null; // Or a loading spinner
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}

// Export theme objects for direct use
export { lightTheme, darkTheme };

