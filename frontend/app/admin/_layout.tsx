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
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Screen name="users" />
      <Stack.Screen name="transactions" />
      <Stack.Screen name="support" />
      <Stack.Screen name="strategist" />
    </Stack>
  );
}
