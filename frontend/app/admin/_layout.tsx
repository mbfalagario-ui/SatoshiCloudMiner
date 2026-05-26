import React from 'react';
import { Stack, Redirect } from 'expo-router';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';

export default function AdminLayout() {
  const { user, loading } = useSession();

  // Hydrating session — show a splash to avoid rendering admin screens
  // (which call /api/admin/*) before we know who the user is.
  if (loading) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  // Not signed in, OR not an admin — bail out instead of crashing the
  // /admin/* screens (this fixes the "App crashes when logging out of the
  // Admin account" report from TestFlight Build #10).
  if (!user) {
    return <Redirect href="/" />;
  }
  if (!user.is_admin) {
    return <Redirect href="/(tabs)/profile" />;
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
