import React, { useEffect } from 'react';
import { Stack, useRouter } from 'expo-router';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';

export default function AdminLayout() {
  const { user, loading } = useSession();
  const router = useRouter();

  // CRITICAL — same iOS-native crash mitigation as (tabs)/_layout: defer the
  // unauthenticated-redirect to an effect (post-commit) so we don't mutate
  // the navigation stack during render of an already-committing Stack.
  useEffect(() => {
    if (loading) return;
    if (!user) {
      const t = setTimeout(() => { try { router.replace('/'); } catch {} }, 0);
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
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Admin' }} />
      <Stack.Screen name="users" options={{ title: 'Users' }} />
      <Stack.Screen name="transactions" options={{ title: 'Transactions' }} />
    </Stack>
  );
}
