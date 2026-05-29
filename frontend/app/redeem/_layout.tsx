import { Stack } from 'expo-router';
import React from 'react';

export default function RedeemLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, animation: 'slide_from_right' }}>
      <Stack.Screen name="network" options={{ presentation: 'modal' }} />
      <Stack.Screen name="form" />
      <Stack.Screen name="confirm" options={{ presentation: 'modal' }} />
    </Stack>
  );
}
