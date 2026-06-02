import React, { useEffect } from 'react';
import { Stack, useRouter } from 'expo-router';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';

export default function AdminLayout() {
  const { user, loading } = useSession();
  const router = useRouter();

  // signOut() in ctx.tsx now navigates BEFORE clearing user state, so by the
  // time we observe `user === null` here, the (admin) tree has already been
  // popped. This effect is a defensive safety net for session-expiry edge
  // cases — runs post-commit via setTimeout(0), never during render.
  useEffect(() => {
    if (loading) return;
    if (!user) {
      const t = setTimeout(() => { try { router.replace('/sign-in'); } catch {} }, 0);
      return () => clearTimeout(t);
    }
    if (!user.is_admin) {
      const t = setTimeout(() => { try { router.replace('/(tabs)/profile'); } catch {} }, 0);
      return () => clearTimeout(t);
    }
  }, [user, loading, router]);

  if (loading || !user || !user.is_admin) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        // Native iOS look for any screen that opts into a header
        headerStyle: { backgroundColor: colors.bg },
        headerTitleStyle: { color: colors.text, fontWeight: '800', fontSize: 17 },
        headerTintColor: colors.primary,         // chevron + tappable text colour
        headerShadowVisible: false,
        headerBackTitle: 'Back',
      }}
    >
      {/* Root dashboard — no native header (it has its own in-screen title) */}
      <Stack.Screen name="index" />

      {/* Sub-screens get a native iOS header bar with chevron-back + title.
          This also fixes the "content under Dynamic Island" bug because the
          native header lives in the safe area. */}
      <Stack.Screen
        name="users"
        options={{ headerShown: true, title: 'Users' }}
      />
      <Stack.Screen
        name="transactions"
        options={{ headerShown: true, title: 'Transactions' }}
      />
      <Stack.Screen
        name="support"
        options={{ headerShown: true, title: 'Support' }}
      />
      <Stack.Screen
        name="strategist"
        options={{ headerShown: true, title: 'AI Strategist' }}
      />
    </Stack>
  );
}
