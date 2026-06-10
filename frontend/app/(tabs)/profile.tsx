import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fonts, fmtUsd, fmtBtc } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { confirmDialog, notify } from '@/src/utils/dialog';
import { api } from '@/src/utils/api';

type FAQ = { id: string; q: string; a: string };

export default function Profile() {
  const router = useRouter();
  const { user, signOut, refresh } = useSession();
  const [autoCheckin, setAutoCheckin] = useState(true);
  const [autoReinvest, setAutoReinvest] = useState(false);
  const [supportUnread, setSupportUnread] = useState(0);
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api('/auto/settings');
        setAutoCheckin(!!r.auto_checkin);
        setAutoReinvest(!!r.auto_reinvest);
      } catch {}
    })();
  }, []);

  // Poll the unread support badge — cheap endpoint, light interval.
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await api('/support/unread');
        if (mounted) setSupportUnread(Number(r?.unread_user_count || 0));
      } catch {
        /* quiet */
      }
    };
    load();
    const t = setInterval(load, 20_000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  // FAQ list — public endpoint, no auth header.
  useEffect(() => {
    (async () => {
      try {
        const r = await api('/faqs', { auth: false });
        setFaqs(r.faqs || []);
      } catch {}
    })();
  }, []);

  const toggle = async (k: 'auto_checkin' | 'auto_reinvest', v: boolean) => {
    if (k === 'auto_checkin') setAutoCheckin(v); else setAutoReinvest(v);
    try {
      await api('/auto/settings', { method: 'POST', body: JSON.stringify({ [k]: v }) });
      await refresh();
    } catch (e: any) {
      notify('Update failed', e?.message ?? 'Try again.');
    }
  };

  const items: { icon: any; label: string; to?: string; testID: string; onPress?: () => void; badge?: number }[] = [
    { icon: 'hardware-chip-outline', label: 'My Boosts', to: '/machines', testID: 'profile-miners' },
    { icon: 'time-outline', label: 'Transaction history', to: '/transactions', testID: 'profile-history' },
    { icon: 'gift-outline', label: 'Daily check-in', to: '/daily', testID: 'profile-daily' },
    { icon: 'people-outline', label: 'Invite Friends', to: '/referral', testID: 'profile-referral' },
    { icon: 'help-circle-outline', label: 'Help & FAQs', to: '/faq', testID: 'profile-faq' },
    {
      icon: 'chatbubbles',
      label: 'Premium Support',
      to: '/support',
      testID: 'profile-premium-support',
      badge: supportUnread,
    },
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
  ];

  const onLogout = () => {
    confirmDialog('Sign out?', 'You will need to sign in again.', async () => {
      // signOut() clears the session token + sets user → null. The (tabs)
      // layout watches `user` and renders <Redirect href="/" /> as a render-
      // side effect, which is the safe expo-router pattern. Calling
      // router.replace('/') here in addition was racing the <Redirect>
      // unmount and crashing iOS native on TestFlight build #10 (admin
      // logout). Leaving navigation entirely to the layout is the fix.
      await signOut();
    }, 'Sign out');
  };

  // Apple Guideline 5.1.1(v): users must be able to permanently delete
  // their account from within the app — no email, no phone, no extra
  // steps. Confirm twice (because this is irreversible) then call the
  // backend DELETE /api/auth/me, then sign out.
  const onDeleteAccount = () => {
    confirmDialog(
      'Delete account?',
      'This permanently erases your account, balance, boosts, transactions, and all data. This cannot be undone.',
      () => {
        confirmDialog(
          'Are you sure?',
          'Type "delete" mentally — there is no recovery. Your sats balance will be forfeited.',
          async () => {
            try {
              await api('/auth/me', { method: 'DELETE' });
              notify(
                'Account deleted',
                'Your account and all data have been permanently deleted.',
              );
              await signOut();
            } catch (e: any) {
              notify(
                'Deletion failed',
                e?.message ?? 'Please try again or contact support if this persists.',
              );
            }
          },
          'Delete forever',
        );
      },
      'Continue',
    );
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
              {it.badge && it.badge > 0 ? (
                <View style={styles.menuBadge}>
                  <Text style={styles.menuBadgeText}>{it.badge > 99 ? '99+' : it.badge}</Text>
                </View>
              ) : null}
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          ))}
        </View>

        {/* Automation settings */}
        <Text style={styles.sectionLabel}>AUTOMATION</Text>
        <View style={styles.menu}>
          <View style={[styles.menuRow]}>
            <View style={styles.menuIcon}><Ionicons name="sync" size={18} color={colors.primary} /></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.menuLabel}>Auto daily check-in</Text>
              <Text style={styles.menuSub}>Server claims streak rewards for you every 24h</Text>
            </View>
            <Switch
              testID="toggle-auto-checkin"
              value={autoCheckin}
              onValueChange={(v) => toggle('auto_checkin', v)}
              trackColor={{ false: colors.border, true: colors.primary }}
            />
          </View>
          <View style={[styles.menuRow, { borderBottomWidth: 0 }]}>
            <View style={styles.menuIcon}><Ionicons name="rocket" size={18} color={colors.primary} /></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.menuLabel}>Auto-reinvest yield</Text>
              <Text style={styles.menuSub}>Buy the next tier automatically when balance hits the threshold</Text>
            </View>
            <Switch
              testID="toggle-auto-reinvest"
              value={autoReinvest}
              onValueChange={(v) => toggle('auto_reinvest', v)}
              trackColor={{ false: colors.border, true: colors.primary }}
            />
          </View>
        </View>

        {user?.is_admin ? (
          <TouchableOpacity
            testID="profile-admin-btn"
            style={styles.adminBtn}
            activeOpacity={0.85}
            onPress={() => router.push('/admin')}
          >
            <Ionicons name="shield-checkmark" size={18} color={colors.primary} />
            <Text style={styles.adminBtnText}>Open Operator Console</Text>
            <Ionicons name="chevron-forward" size={18} color={colors.primary} />
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity
          testID="profile-contact-support-btn"
          style={styles.contactSupportBtn}
          activeOpacity={0.85}
          onPress={() => router.push('/support')}
        >
          <Ionicons name="chatbubble-ellipses" size={18} color={colors.primary} />
          <Text style={styles.contactSupportText}>Still need help? Chat with support</Text>
          <Ionicons name="chevron-forward" size={18} color={colors.primary} />
        </TouchableOpacity>

        <TouchableOpacity
          testID="profile-logout-btn"
          style={styles.logoutBtn}
          activeOpacity={0.8}
          onPress={onLogout}
        >
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={styles.logoutText}>Sign out</Text>
        </TouchableOpacity>

        {/* Apple 5.1.1(v): in-app permanent account deletion. */}
        <TouchableOpacity
          testID="profile-delete-account-btn"
          style={styles.deleteAccountBtn}
          activeOpacity={0.8}
          onPress={onDeleteAccount}
        >
          <Ionicons name="trash-outline" size={18} color={colors.danger} />
          <Text style={styles.deleteAccountText}>Delete account</Text>
        </TouchableOpacity>
        <Text style={styles.deleteAccountHint}>
          Permanently erases your account and all associated data from our servers.
          Action is immediate and cannot be undone.
        </Text>

        <Text style={styles.appVersion}>Hashrate Cloud Miner v1.0.1 (23)</Text>
        <Text style={styles.disclaimer}>
          Hashrate Cloud Miner is a cloud computing simulation and monitoring tool. It is not a financial,
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
  menuBadge: {
    minWidth: 22,
    height: 22,
    paddingHorizontal: 6,
    borderRadius: 11,
    backgroundColor: '#ef4444',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.xs,
  },
  menuBadgeText: { color: '#fff', fontSize: 11, fontWeight: '800', letterSpacing: 0.3 },
  menuSub: { color: colors.textTertiary, fontSize: 11, marginTop: 2 },
  sectionLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '800', letterSpacing: 1.4, marginTop: spacing.lg, marginBottom: spacing.sm },
  adminBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.primaryDim,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    marginTop: spacing.md,
  },
  adminBtnText: { flex: 1, color: colors.primary, fontWeight: '800', fontSize: 14 },
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
  deleteAccountBtn: {
    flexDirection: 'row',
    backgroundColor: 'transparent',
    borderRadius: radius.md,
    paddingVertical: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.sm,
    gap: 8,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  deleteAccountText: { color: colors.danger, fontSize: 13, fontWeight: '700' },
  deleteAccountHint: {
    color: colors.textTertiary,
    fontSize: 10,
    lineHeight: 14,
    textAlign: 'center',
    marginTop: 6,
    paddingHorizontal: spacing.md,
  },
  contactSupportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginTop: spacing.sm,
  },
  contactSupportText: { flex: 1, color: colors.primary, fontWeight: '800', fontSize: 13 },
  appVersion: { color: colors.textTertiary, fontSize: 11, textAlign: 'center', marginTop: spacing.lg },
  disclaimer: {
    color: colors.textTertiary,
    fontSize: 11,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
ign: 'center',
    marginTop: 6,
    paddingHorizontal: spacing.md,
  },
  faqWrap: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    overflow: 'hidden',
  },
  faqEmpty: { color: colors.textTertiary, fontSize: 12, padding: spacing.md, textAlign: 'center' },
  faqRow: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
  },
  faqHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  faqQ: { flex: 1, color: colors.text, fontSize: 13, fontWeight: '700', lineHeight: 18 },
  faqA: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: 8, marginLeft: 28 },
  contactSupportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginTop: spacing.sm,
  },
  contactSupportText: { flex: 1, color: colors.primary, fontWeight: '800', fontSize: 13 },
  appVersion: { color: colors.textTertiary, fontSize: 11, textAlign: 'center', marginTop: spacing.lg },
  disclaimer: {
    color: colors.textTertiary,
    fontSize: 11,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
