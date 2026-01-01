import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { GlobalProvider } from '../mobile/src/components/GlobalProvider';
import { StatusBar } from 'expo-status-bar';
import { theme } from '../mobile/src/constants/theme';
import { ThemeProvider } from '../mobile/src/context/ThemeContext';
import ErrorBoundary from '../mobile/src/components/ErrorBoundary';
import OfflineBanner from '../mobile/src/components/OfflineBanner';
import { initMonitoring } from '../mobile/src/services/monitoring';
import * as SplashScreen from 'expo-splash-screen';

// Prevent auto-hide splash screen
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  useEffect(() => {
    // Initialize monitoring on app start (with error handling)
    try {
      initMonitoring();
    } catch (error) {
      console.error('Failed to initialize monitoring:', error);
      // Don't crash the app if monitoring fails
    }

    // Hide splash screen after app is ready
    setTimeout(() => {
      SplashScreen.hideAsync();
    }, 1000);
  }, []);

  return (
    <ThemeProvider>
      <GlobalProvider>
        <ErrorBoundary>
          <OfflineBanner />
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerStyle: {
                backgroundColor: theme.colors.ui.background,
              },
              headerTintColor: theme.colors.text.primary,
              headerTitleStyle: {
                fontWeight: '700',
                fontSize: 18,
              },
              headerShadowVisible: false,
              contentStyle: {
                backgroundColor: theme.colors.ui.background,
              },
            }}
          >
            <Stack.Screen 
              name="index" 
              options={{ 
                headerShown: false,
                title: 'Home',
              }} 
            />
            <Stack.Screen 
              name="ai-predictions" 
              options={{ 
                title: '🤖 AI Predictions',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="paper-trading" 
              options={{ 
                title: '📊 Paper Trading',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="live-trading" 
              options={{ 
                title: '💰 Live Trading',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="voice-briefing" 
              options={{ 
                title: '🎙️ Voice Briefing',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="brokers" 
              options={{ 
                title: '🔌 Brokers',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="settings" 
              options={{ 
                title: '⚙️ Settings',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="analytics" 
              options={{ 
                title: '📈 Analytics',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="profile" 
              options={{ 
                title: '👤 Profile',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="notifications" 
              options={{ 
                title: '🔔 Notifications',
                headerBackTitle: 'Πίσω',
              }} 
            />
            <Stack.Screen 
              name="admin-cms" 
              options={{ 
                title: 'CMS Admin',
                headerShown: false,
              }} 
            />
            <Stack.Screen 
              name="ml-status" 
              options={{ 
                title: 'ML Status',
                headerShown: false,
              }} 
            />
            <Stack.Screen 
              name="scheduled-briefings" 
              options={{ 
                title: 'Scheduled Briefings',
                headerShown: false,
              }} 
            />
          </Stack>
        </ErrorBoundary>
      </GlobalProvider>
    </ThemeProvider>
  );
}
