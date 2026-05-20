import React from 'react';
import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Platform, View, StyleSheet, ActivityIndicator } from 'react-native';
import { BlurView } from 'expo-blur';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { useEffect } from 'react';

export default function TabsLayout() {
  const { user, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/');
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: {
          position: 'absolute',
          backgroundColor: Platform.OS === 'ios' ? 'transparent' : 'rgba(11,14,20,0.96)',
          borderTopColor: colors.border,
          borderTopWidth: 0.5,
          height: Platform.OS === 'ios' ? 88 : 64,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          marginTop: 2,
        },
        tabBarBackground:
          Platform.OS === 'ios'
            ? () => (
                <BlurView
                  tint="dark"
                  intensity={80}
                  style={StyleSheet.absoluteFill}
                />
              )
            : undefined,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="shop"
        options={{
          title: 'Mine',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="hardware-chip" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="wallet"
        options={{
          title: 'Wallet',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="wallet" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-circle" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
