// errorHandler MUST be imported first — installs `global.ErrorUtils`
// override before any other code can throw.
import { installErrorHandlers, drainPendingErrors } from '@/src/utils/errorHandler';
installErrorHandlers();

import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SessionProvider } from '@/src/ctx';
import { AdProvider } from '@/src/AdContext';
import { colors } from '@/src/utils/theme';
import ErrorBoundary from '@/src/components/ErrorBoundary';

export default function RootLayout() {
  // On every fresh launch, drain any crash reports persisted to
  // AsyncStorage by the previous session (which may have died from a
  // crash before its network POST completed). This is what gives us
  // symbolicated crash data for future investigations — the very point
  // of Build #33 per GPT's "prioritize getting a symbolicated crash"
  // requirement.
  useEffect(() => {
    drainPendingErrors().catch((e) => {
      // eslint-disable-next-line no-console
      console.warn('[RootLayout] drainPendingErrors failed:', e);
    });
  }, []);

  return (
    <ErrorBoundary>
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
                <Stack.Screen name="support" />
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
    </ErrorBoundary>
  );
}
