import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SessionProvider } from '@/src/ctx';
import { AdProvider } from '@/src/AdContext';
import { colors } from '@/src/utils/theme';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaProvider>
        <SessionProvider>
          <AdProvider>
            <StatusBar style="light" />
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: colors.bg },
                animation: 'fade',
              }}
            >
              <Stack.Screen name="index" />
              <Stack.Screen name="sign-in" />
              <Stack.Screen name="sign-up" />
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="admin" />
              <Stack.Screen name="machines" />
              <Stack.Screen name="transactions" />
              <Stack.Screen name="daily" />
              <Stack.Screen name="referral" />
              <Stack.Screen name="legal" />
            </Stack>
          </AdProvider>
        </SessionProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
