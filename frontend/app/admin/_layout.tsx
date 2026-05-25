import { Stack } from 'expo-router';
import { colors } from '@/src/utils/theme';

export default function AdminLayout() {
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
