import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, fonts, shadows, fmtUsd } from '@/src/utils/theme';
import { fmtSats } from '@/src/utils/sats';

export default function AdminAnalytics() {
  const router = useRouter();
  const { user } = useSession();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!user || !user.is_admin) return;
    setLoading(true);
    try {
      const r = await api('/admin/analytics');
      setData(r);
    } catch (e) {
      // unauthorized → bounce back. We use a soft fallback so a brief
      // session-null window during sign-out doesn't crash the screen.
      try { router.replace('/'); } catch {}
    } finally {
      setLoading(false);
    }
  }, [router, user]);

  useEffect(() => {
    if (!user) return;                  // _layout will redirect; do nothing here
    if (!user.is_admin) return;         // _layout will redirect; do nothing here
    load();
  }, [user, load]);

  if (loading || !data) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      </SafeAreaView>
    );
  }

  const agents = data.ai_agents_today || [];

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
      >
        <Text style={styles.h1}>Operator Console</Text>
        <Text style={styles.sub}>Live revenue, users, AI agents & payouts</Text>

        {/* Quick links */}
        <View style={styles.quickRow}>
          <QuickBtn icon="people" label="Users" onPress={() => router.push('/admin/users')} />
          <QuickBtn icon="swap-horizontal" label="Txns" onPress={() => router.push('/admin/transactions')} />
        </View>

        {/* Headline cards */}
        <View style={styles.cards}>
          <KPI label="Revenue" value={fmtUsd(data.revenue_usd)} icon="trending-up" tone="primary" />
          <KPI label="Paid out" value={fmtUsd(data.paid_out_usd)} sub={fmtSats(data.paid_out_sats || 0)} icon="send" tone="warning" />
          <KPI label="Margin" value={`${data.profit_margin_pct}%`} sub={fmtUsd(data.gross_margin_usd)} icon="stats-chart" tone="primary" />
          <KPI label="Fees earned" value={fmtUsd(data.fees_collected_usd)} sub={fmtSats(data.fees_collected_sats || 0)} icon="cash" tone="secondary" />
        </View>

        {/* Users / machines */}
        <View style={styles.statGrid}>
          <Stat label="Total users" value={String(data.users?.total ?? 0)} />
          <Stat label="Banned" value={String(data.users?.banned ?? 0)} />
          <Stat label="Active machines" value={String(data.machines?.active ?? 0)} />
          <Stat label="Expired" value={String(data.machines?.expired ?? 0)} />
        </View>

        {/* AI agents */}
        <Text style={styles.sectionLabel}>AI TRADING AGENTS — TODAY</Text>
        <View style={styles.agentList}>
          {agents.length === 0 ? (
            <Text style={styles.muted}>Snapshot pending (refreshes nightly)…</Text>
          ) : (
            agents.map((a: any) => (
              <View key={a.id} style={styles.agentRow}>
                <View style={styles.agentLeft}>
                  <View style={[styles.dot, { backgroundColor: a.signal_strength === 'high' ? colors.primary : a.signal_strength === 'medium' ? colors.warning : colors.textTertiary }]} />
                  <View>
                    <Text style={styles.agentName}>{a.name}</Text>
                    <Text style={styles.agentStrat}>{a.strategy}</Text>
                  </View>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[styles.agentPct, { color: a.daily_pct >= 0 ? colors.primary : colors.warning }]}>
                    {a.daily_pct >= 0 ? '+' : ''}{(a.daily_pct * 100).toFixed(2)}%
                  </Text>
                  <Text style={styles.agentWin}>{(a.win_rate * 100).toFixed(0)}% wr</Text>
                </View>
              </View>
            ))
          )}
        </View>

        {/* Latest withdrawals */}
        <Text style={styles.sectionLabel}>LATEST WITHDRAWALS</Text>
        <View style={styles.txList}>
          {(data.latest_withdrawals || []).map((tx: any) => (
            <View key={tx.id} style={styles.txRow}>
              <View>
                <Text style={styles.txTitle}>{tx.user_email || tx.user_id?.slice(0, 8)}</Text>
                <Text style={styles.txSub}>{new Date(tx.created_at).toLocaleString()}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.txAmt}>{fmtSats(tx.amount_sats || 0)}</Text>
                <Text style={[styles.txStatus, tx.status === 'completed' ? { color: colors.primary } : tx.status === 'failed' ? { color: colors.danger } : { color: colors.warning }]}>
                  {tx.status?.toUpperCase()}
                </Text>
              </View>
            </View>
          ))}
          {(!data.latest_withdrawals || data.latest_withdrawals.length === 0) && (
            <Text style={styles.muted}>No withdrawals yet.</Text>
          )}
        </View>

        <View style={{ height: 60 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function KPI({ label, value, sub, icon, tone }: any) {
  const accent = tone === 'warning' ? colors.warning : tone === 'secondary' ? colors.secondary : colors.primary;
  return (
    <View style={styles.kpi}>
      <Ionicons name={icon} size={16} color={accent} />
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={[styles.kpiValue, { color: accent }]}>{value}</Text>
      {sub ? <Text style={styles.kpiSub}>{sub}</Text> : null}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

function QuickBtn({ icon, label, onPress }: any) {
  return (
    <TouchableOpacity style={styles.quickBtn} onPress={onPress} activeOpacity={0.85}>
      <Ionicons name={icon} size={16} color={colors.primary} />
      <Text style={styles.quickBtnText}>{label}</Text>
      <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: spacing.lg },
  h1: { color: colors.text, fontSize: 24, fontWeight: '800' },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: spacing.lg },
  quickRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  quickBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  quickBtnText: { flex: 1, color: colors.text, fontWeight: '700', fontSize: 13 },
  cards: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  kpi: {
    flexBasis: '48%',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: 4,
    ...shadows.card,
  },
  kpiLabel: { color: colors.textTertiary, fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  kpiValue: { color: colors.text, fontSize: 18, fontWeight: '800', fontFamily: fonts.mono },
  kpiSub: { color: colors.textSecondary, fontSize: 11, fontFamily: fonts.mono },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  stat: {
    flexBasis: '48%',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  statLabel: { color: colors.textTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700' },
  statValue: { color: colors.text, fontSize: 18, fontWeight: '800', marginTop: 4, fontFamily: fonts.mono },
  sectionLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '800', letterSpacing: 1.4, marginTop: spacing.md, marginBottom: spacing.sm },
  agentList: { gap: 6 },
  agentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  agentLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  agentName: { color: colors.text, fontSize: 14, fontWeight: '800' },
  agentStrat: { color: colors.textSecondary, fontSize: 11 },
  agentPct: { fontSize: 14, fontWeight: '800', fontFamily: fonts.mono },
  agentWin: { color: colors.textTertiary, fontSize: 10, fontFamily: fonts.mono },
  txList: { gap: 6, marginBottom: spacing.md },
  txRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  txTitle: { color: colors.text, fontSize: 13, fontWeight: '700' },
  txSub: { color: colors.textTertiary, fontSize: 11 },
  txAmt: { color: colors.text, fontSize: 13, fontWeight: '800', fontFamily: fonts.mono },
  txStatus: { fontSize: 10, fontWeight: '800', letterSpacing: 1, marginTop: 2 },
  muted: { color: colors.textTertiary, fontSize: 12, padding: spacing.md, textAlign: 'center' },
});
