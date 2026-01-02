import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { GlobalProvider } from '../mobile/src/components/GlobalProvider';
import ErrorBoundary from '../mobile/src/components/ErrorBoundary';
import { ThemeProvider, useTheme } from '../mobile/src/context/ThemeContext';
// import { useNotifications } from '../mobile/src/hooks/useNotifications'; // Temporarily disabled to prevent crashes
import OfflineBanner from '../mobile/src/components/OfflineBanner';
import { StatusBar } from 'expo-status-bar';
import { initMonitoring } from '../mobile/src/services/monitoring';
import * as SplashScreen from 'expo-splash-screen';

SplashScreen.preventAutoHideAsync();

function AppContent() {
  const { theme, isDark } = useTheme();

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
      SplashScreen.hideAsync().catch((err) => {
        console.error('Failed to hide splash screen:', err);
      });
    }, 1000);
  }, []);

  return (
    <>
      <OfflineBanner />
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: theme.colors.ui.cardBackground,
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
          animation: 'slide_from_right',
        }}
      >
        {/* Main Screens */}
        <Stack.Screen 
          name="index" 
          options={{ 
            title: 'AURA',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="ai-predictions" 
          options={{ 
            title: '🤖 AI Predictions',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="paper-trading" 
          options={{ 
            title: '📊 Paper Trading',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="live-trading" 
          options={{ 
            title: '💰 Live Trading',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="voice-briefing" 
          options={{ 
            title: '🎙️ Voice Briefing',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="analytics" 
          options={{ 
            title: '📈 Analytics',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="notifications" 
          options={{ 
            title: '🔔 Notifications',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="settings" 
          options={{ 
            title: '⚙️ Settings',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="profile" 
          options={{ 
            title: '👤 Edit Profile',
            headerShown: true,
          }} 
        />
        
        <Stack.Screen 
          name="brokers" 
          options={{ 
            title: '🔗 Brokers',
            headerShown: true,
          }} 
        />

        {/* Dev/Test Screens */}
        <Stack.Screen 
          name="dev-test" 
          options={{ 
            title: '🧪 Dev Test',
            headerShown: true,
            presentation: 'modal',
          }} 
        />
        
        <Stack.Screen 
          name="animation-test" 
          options={{ 
            title: '🎨 Animation Test',
            headerShown: true,
            presentation: 'modal',
          }} 
        />

        {/* Admin Screens */}
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
    </>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <ErrorBoundary>
        <ThemeProvider>
          <GlobalProvider>
            <AppContent />
          </GlobalProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}
