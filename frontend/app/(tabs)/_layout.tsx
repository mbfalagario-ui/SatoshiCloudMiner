import React, { useEffect, useRef } from 'react';
import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Platform, View, StyleSheet, ActivityIndicator } from 'react-native';
import { BlurView } from 'expo-blur';
import { colors } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { useAds } from '@/src/AdContext';

export default function TabsLayout() {
  const { user, loading } = useSession();
  const { showInterstitial } = useAds();
  const router = useRouter();
  const lastTabRef = useRef<string>('index');

  // signOut() in ctx.tsx now navigates to /sign-in BEFORE clearing user state,
  // so by the time we observe `user === null` here, expo-router has already
  // unmounted the (tabs) tree. This effect is only a defensive safety net
  // for session-expiry edge cases (e.g. a 401 from /auth/me marks user=null
  // while we're still mounted) — we redirect to /sign-in from a microtask
  // post-commit, never during render.
  useEffect(() => {
    if (!loading && !user) {
      const t = setTimeout(() => {
        try {
          router.replace('/sign-in');
        } catch {
          // navigation can throw if the layout already unmounted — safe to ignore.
        }
      }, 0);
      return () => clearTimeout(t);
    }
  }, [user, loading, router]);

  // Still hydrating session from storage — show a splash instead of swapping
  // the tree mid-render.
  if (loading) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  // While the effect above runs `router.replace('/')`, render an empty splash
  // so we don't access user.* on a null session and don't trigger Tabs to
  // mount a brand-new screen tree against null data.
  if (!user) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
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
