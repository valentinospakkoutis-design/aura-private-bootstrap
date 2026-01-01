import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { useEffect } from 'react';
import ErrorBoundary from '../mobile/src/components/ErrorBoundary';
import OfflineBanner from '../mobile/src/components/OfflineBanner';
import { ThemeProvider } from '../mobile/src/context/ThemeContext';
import { GlobalProvider } from '../mobile/src/components/GlobalProvider';
import { initMonitoring } from '../mobile/src/services/monitoring';

export default function RootLayout() {
  useEffect(() => {
    // Initialize monitoring on app start (with error handling)
    try {
      initMonitoring();
    } catch (error) {
      console.error('Failed to initialize monitoring:', error);
      // Don't crash the app if monitoring fails
    }
  }, []);

  return (
    <ThemeProvider>
      <GlobalProvider>
        <ErrorBoundary>
          <View style={{ flex: 1 }}>
            <OfflineBanner />
            <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: '#1a1a1a',
          },
          headerTintColor: '#fff',
          headerTitleStyle: {
            fontWeight: 'bold',
          },
          contentStyle: {
            backgroundColor: '#1a1a1a',
          },
        }}
      >
        <Stack.Screen 
          name="index" 
          options={{ 
            title: 'AURA',
            headerShown: true,
          }} 
        />
        <Stack.Screen 
          name="settings" 
          options={{ 
            title: 'Ρυθμίσεις',
            headerShown: true,
          }} 
        />
        <Stack.Screen 
          name="profile" 
          options={{ 
            title: 'Προφίλ',
            headerShown: true,
          }} 
        />
        <Stack.Screen 
          name="paper-trading" 
          options={{ 
            title: 'Paper Trading',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="brokers" 
          options={{ 
            title: 'Brokers',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="ai-predictions" 
          options={{ 
            title: 'AI Predictions',
            headerShown: false,
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
          name="voice-briefing" 
          options={{ 
            title: 'Voice Briefing',
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
          name="live-trading" 
          options={{ 
            title: 'Live Trading',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="analytics" 
          options={{ 
            title: 'Analytics',
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
        <Stack.Screen 
          name="notifications" 
          options={{ 
            title: 'Notifications',
            headerShown: false,
          }} 
        />
          </Stack>
          <StatusBar style="light" />
        </View>
      </ErrorBoundary>
      </GlobalProvider>
    </ThemeProvider>
  );
}

