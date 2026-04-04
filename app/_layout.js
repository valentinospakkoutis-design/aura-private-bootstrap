import React, { useEffect, useState } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { Platform } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { GlobalProvider } from '../mobile/src/components/GlobalProvider';
import ErrorBoundary from '../mobile/src/components/ErrorBoundary';
import { ThemeProvider, useTheme } from '../mobile/src/context/ThemeContext';
// import { useNotifications } from '../mobile/src/hooks/useNotifications'; // Temporarily disabled to prevent crashes
import OfflineBanner from '../mobile/src/components/OfflineBanner';
import { StatusBar } from 'expo-status-bar';
import { initMonitoring } from '../mobile/src/services/monitoring';
import * as SplashScreen from 'expo-splash-screen';
import { useAppStore } from '../mobile/src/stores/appStore';

SplashScreen.preventAutoHideAsync();

function AuthGuard({ children }) {
  const { user, setUser } = useAppStore();
  const router = useRouter();
  const segments = useSegments();
  const [isRestoring, setIsRestoring] = useState(true);

  // On startup: restore session from stored token
  useEffect(() => {
    (async () => {
      try {
        let token = null;
        if (Platform.OS === 'web') {
          try { token = localStorage.getItem('auth_token'); } catch {}
        } else {
          const SecureStore = require('expo-secure-store');
          token = await SecureStore.getItemAsync('auth_token');
        }

        console.log('[AuthGuard] Token from storage:', token ? `found (${token.substring(0, 20)}...)` : 'not found');

        if (token) {
          // Use axios directly to avoid the 401 interceptor clearing our token during restore
          const axios = require('axios');
          const { getApiBaseUrl } = require('../mobile/src/config/environment');
          const baseURL = getApiBaseUrl();
          const meResponse = await axios.get(`${baseURL}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 10000,
          });
          const me = meResponse.data;
          console.log('[AuthGuard] Session restored for:', me.email);
          setUser({
            id: String(me.id || '1'),
            name: me.full_name || me.email.split('@')[0],
            email: me.email,
            voiceCloned: false,
            riskProfile: 'moderate',
          });
        }
      } catch (err) {
        console.log('[AuthGuard] Token restore failed:', err?.response?.status || err?.message);
        // Token invalid or expired — clear it and stay logged out
        if (Platform.OS === 'web') {
          try { localStorage.removeItem('auth_token'); } catch {}
        } else {
          try {
            const SecureStore = require('expo-secure-store');
            await SecureStore.deleteItemAsync('auth_token');
          } catch {}
        }
      } finally {
        setIsRestoring(false);
      }
    })();
  }, []);

  // Redirect logic — skip while restoring session
  useEffect(() => {
    if (isRestoring) return;

    const inLoginScreen = segments[0] === 'login';

    if (!user && !inLoginScreen) {
      router.replace('/login');
    } else if (user && inLoginScreen) {
      router.replace('/(tabs)');
    }
  }, [user, segments, isRestoring]);

  // Show nothing while checking token (splash screen is still visible)
  if (isRestoring) return null;

  return children;
}

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
      <AuthGuard>
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
        {/* Login Screen */}
        <Stack.Screen
          name="login"
          options={{
            headerShown: false,
            animation: 'fade',
          }}
        />

        {/* Tab Navigator */}
        <Stack.Screen
          name="(tabs)"
          options={{
            headerShown: false,
          }}
        />

        {/* Keep original screens for direct navigation */}
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
          name="auto-trading"
          options={{
            title: '🤖 Auto Trading',
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
          name="change-password"
          options={{
            headerShown: false,
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

        <Stack.Screen
          name="prediction-details"
          options={{
            title: '🔍 Prediction Details',
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
      </AuthGuard>
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
