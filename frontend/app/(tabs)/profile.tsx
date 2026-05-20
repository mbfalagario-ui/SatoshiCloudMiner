import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fonts, fmtUsd, fmtBtc } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { confirmDialog, notify } from '@/src/utils/dialog';

export default function Profile() {
  const router = useRouter();
  const { user, signOut } = useSession();

  const items: { icon: any; label: string; to?: string; testID: string; onPress?: () => void }[] = [
    { icon: 'hardware-chip-outline', label: 'My miners', to: '/machines', testID: 'profile-miners' },
    { icon: 'time-outline', label: 'Transaction history', to: '/transactions', testID: 'profile-history' },
    { icon: 'gift-outline', label: 'Daily check-in', to: '/daily', testID: 'profile-daily' },
    { icon: 'people-outline', label: 'Invite friends', to: '/referral', testID: 'profile-referral' },
    {
      icon: 'document-text-outline',
      label: 'Terms of Service',
      to: '/legal?doc=terms',
      testID: 'profile-terms',
    },
    {
      icon: 'shield-checkmark-outline',
      label: 'Privacy Policy',
      to: '/legal?doc=privacy',
      testID: 'profile-privacy',
    },
    {
      icon: 'mail-outline',
      label: 'Contact support',
      testID: 'profile-support',
      onPress: () =>
        notify(
          'Contact support',
          'Reach us at support@hashcloud.app — we typically respond within 24 hours.'
        ),
    },
  ];

  const onLogout = () => {
    confirmDialog('Sign out?', 'You will need to sign in again.', async () => {
      await signOut();
      router.replace('/');
    }, 'Sign out');
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>Profile</Text>

        <View style={styles.card}>
          <View style={styles.avatar}>
            <Ionicons name="person" size={28} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.email} numberOfLines={1} testID="profile-email">
              {user?.email}
            </Text>
            <Text style={styles.code}>Referral · {user?.referral_code ?? '—'}</Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>BALANCE</Text>
            <Text style={styles.statValue}>{fmtUsd(user?.balance_usd ?? 0)}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>LIFETIME</Text>
            <Text style={styles.statValue}>{fmtUsd(user?.lifetime_usd ?? 0)}</Text>
          </View>
        </View>

        <View style={styles.menu}>
          {items.map((it, i) => (
            <TouchableOpacity
              key={i}
              testID={it.testID}
              style={[styles.menuRow, i === items.length - 1 && { borderBottomWidth: 0 }]}
              activeOpacity={0.7}
              onPress={() => (it.onPress ? it.onPress() : it.to && router.push(it.to as any))}
            >
              <View style={styles.menuIcon}>
                <Ionicons name={it.icon} size={18} color={colors.text} />
              </View>
              <Text style={styles.menuLabel}>{it.label}</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          testID="profile-logout-btn"
          style={styles.logoutBtn}
          activeOpacity={0.8}
          onPress={onLogout}
        >
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={styles.logoutText}>Sign out</Text>
        </TouchableOpacity>

        <Text style={styles.appVersion}>HashCloud v1.0.0 (1)</Text>
        <Text style={styles.disclaimer}>
          HashCloud is a cloud computing simulation and monitoring tool. It is not a financial,
          investment, or trading platform. Outcomes depend on server status and operational
          conditions. Pricing reflects operational costs.
        </Text>

        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  title: { color: colors.text, fontSize: 26, fontWeight: '800', marginBottom: spacing.lg, letterSpacing: -0.6 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primaryDim,
    justifyContent: 'center',
    alignItems: 'center',
  },
  email: { color: colors.text, fontSize: 16, fontWeight: '700' },
  code: { color: colors.textSecondary, fontSize: 12, marginTop: 2, fontFamily: fonts.mono },
  statsRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  statCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  statLabel: { color: colors.textTertiary, fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  statValue: { color: colors.text, fontSize: 18, fontWeight: '800', fontFamily: fonts.mono, marginTop: 4 },
  menu: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    overflow: 'hidden',
  },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
    gap: spacing.md,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.bg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  menuLabel: { flex: 1, color: colors.text, fontSize: 14, fontWeight: '600' },
  logoutBtn: {
    flexDirection: 'row',
    backgroundColor: colors.dangerDim,
    borderRadius: radius.md,
    paddingVertical: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.md,
    gap: 8,
  },
  logoutText: { color: colors.danger, fontSize: 14, fontWeight: '700' },
  appVersion: { color: colors.textTertiary, fontSize: 11, textAlign: 'center', marginTop: spacing.lg },
  disclaimer: {
    color: colors.textTertiary,
    fontSize: 11,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
