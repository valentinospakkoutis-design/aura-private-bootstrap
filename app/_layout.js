import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

export default function RootLayout() {
  return (
    <>
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
      </Stack>
      <StatusBar style="light" />
    </>
  );
}

