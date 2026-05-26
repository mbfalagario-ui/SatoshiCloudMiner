import React, { useRef } from 'react';
import { Tabs, Redirect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Platform, View, StyleSheet, ActivityIndicator } from 'react-native';
import { BlurView } from 'expo-blur';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { useAds } from '@/src/AdContext';

export default function TabsLayout() {
  const { user, loading } = useSession();
  const { showInterstitial } = useAds();
  const lastTabRef = useRef<string>('index');

  // Still hydrating session from storage — show a splash instead of swapping
  // the tree mid-render (the previous useEffect+render-swap caused a crash
  // on iOS when the user signed out from the Profile tab).
  if (loading) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  // Authenticated state lost (e.g. user just signed out). Redirect declares
  // the navigation as a render-side effect, which expo-router/React Navigation
  // handles without unmounting Tabs partway through.
  if (!user) {
    return <Redirect href="/" />;
  }

  const onTabPress = (name: string) => {
    if (name !== lastTabRef.current) {
      lastTabRef.current = name;
      showInterstitial(`tab:${name}`).catch(() => {});
    }
  };

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
        listeners={{ tabPress: () => onTabPress('index') }}
      />
      <Tabs.Screen
        name="shop"
        options={{
          title: 'Mine',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="hardware-chip" size={size} color={color} />
          ),
        }}
        listeners={{ tabPress: () => onTabPress('shop') }}
      />
      <Tabs.Screen
        name="wallet"
        options={{
          title: 'Wallet',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="wallet" size={size} color={color} />
          ),
        }}
        listeners={{ tabPress: () => onTabPress('wallet') }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-circle" size={size} color={color} />
          ),
        }}
        listeners={{ tabPress: () => onTabPress('profile') }}
      />
    </Tabs>
  );
}
