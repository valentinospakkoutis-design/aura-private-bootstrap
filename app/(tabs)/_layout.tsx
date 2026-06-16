import { Tabs } from 'expo-router';
import { Platform, Text } from 'react-native';
import { theme } from '../../mobile/src/constants/theme';

export default function TabLayout() {
  return (
    <Tabs
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
        tabBarStyle: {
          backgroundColor: theme.colors.ui.cardBackground,
          borderTopColor: theme.colors.ui.border,
          borderTopWidth: 1,
          paddingBottom: 6,
          paddingTop: 6,
          height: 54,
          // Pin the tab bar to the bottom of the viewport on web so it stays
          // visible. `position: 'fixed'` is web-only (native layout has no such
          // value), so it is applied only on web.
          ...(Platform.OS === 'web'
            ? ({ position: 'fixed', bottom: 0, left: 0, right: 0 } as any)
            : {}),
        },
        tabBarActiveTintColor: theme.colors.brand.primary,
        tabBarInactiveTintColor: theme.colors.text.secondary,
        tabBarShowLabel: true,
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ focused }) => <Text style={{ fontSize: 18 }}>{focused ? '● Dashboard' : '○'}</Text>,
        }}
      />
      <Tabs.Screen
        name="ai-predictions"
        options={{
          title: 'AI',
          tabBarIcon: ({ focused }) => <Text style={{ fontSize: 18 }}>{focused ? '● AI' : '○'}</Text>,
        }}
      />
      <Tabs.Screen
        name="trading"
        options={{
          title: 'Trading',
          tabBarIcon: ({ focused }) => <Text style={{ fontSize: 18 }}>{focused ? '● Trading' : '○'}</Text>,
        }}
      />
      <Tabs.Screen
        name="auto-trading"
        options={{
          title: 'Auto',
          tabBarIcon: ({ focused }) => <Text style={{ fontSize: 18 }}>{focused ? '● Auto' : '○'}</Text>,
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarIcon: ({ focused }) => <Text style={{ fontSize: 18 }}>{focused ? '● More' : '○'}</Text>,
        }}
      />
    </Tabs>
  );
}
