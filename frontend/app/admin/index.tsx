import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity, Modal, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, fonts, shadows, fmtUsd } from '@/src/utils/theme';
import { fmtSats } from '@/src/utils/sats';
import { confirmDialog, notify } from '@/src/utils/dialog';

export default function AdminAnalytics() {
  const router = useRouter();
  const { user } = useSession();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [fees, setFees] = useState<any>(null);
  const [aiAgents, setAiAgents] = useState<any[]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [feeBusy, setFeeBusy] = useState(false);
  const [editingAgent, setEditingAgent] = useState<any>(null);
  const [supportUnread, setSupportUnread] = useState(0);

  // Poll the support inbox unread count so the Operator Console badge is live.
  useEffect(() => {
    if (!user || !user.is_admin) return;
    let mounted = true;
    const fetch = async () => {
      try {
        const r = await api('/admin/support/unread');
        if (mounted) setSupportUnread(Number(r?.unread_admin_count || 0));
      } catch {}
    };
    fetch();
    const t = setInterval(fetch, 20_000);
    return () => { mounted = false; clearInterval(t); };
  }, [user]);

  const load = useCallback(async () => {
    if (!user || !user.is_admin) return;
    setLoading(true);
    try {
      const [analytics, feesSummary, agentSnap] = await Promise.allSettled([
        api('/admin/analytics'),
        api('/admin/fees/summary'),
        api('/admin/ai/agents'),
      ]);
      if (analytics.status === 'fulfilled') setData(analytics.value);
      if (feesSummary.status === 'fulfilled') setFees(feesSummary.value);
      if (agentSnap.status === 'fulfilled') setAiAgents(agentSnap.value?.agents || []);
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

  const onRegenerateAI = () => {
    confirmDialog(
      'Regenerate AI Agents?',
      'This replaces today\'s AI Trading Agents snapshot with a fresh randomized set. Any manual edits to the current snapshot will be lost.',
      async () => {
        setAiBusy(true);
        try {
          const r = await api('/admin/ai/regenerate', { method: 'POST' });
          setAiAgents(r?.agents || []);
          notify('AI Agents Regenerated', 'A fresh strategy snapshot is now live.');
        } catch (e: any) {
          notify('Regenerate failed', e?.message || 'Try again.');
        } finally {
          setAiBusy(false);
        }
      },
      'Regenerate'
    );
  };

  const onReinvestFees = () => {
    if (!fees || (fees.available_sats || 0) <= 0) {
      notify('No fees available', 'The unreinvested commission pool is currently empty.');
      return;
    }
    confirmDialog(
      'Reinvest commission fees?',
      `${fmtSats(fees.available_sats)} (${fmtUsd(fees.available_usd)}) will be credited to YOUR admin balance as a treasury reinvestment. This is recorded in the audit log.`,
      async () => {
        setFeeBusy(true);
        try {
          const r = await api('/admin/fees/reinvest', {
            method: 'POST',
            body: JSON.stringify({ note: 'Operator treasury reinvestment' }),
          });
          notify('Reinvested', `${fmtUsd(r.credited_usd || 0)} credited. Tx id: ${(r.tx_id || '').slice(0, 8)}…`);
          if (r.summary) setFees(r.summary);
        } catch (e: any) {
          notify('Reinvest failed', e?.message || 'Try again.');
        } finally {
          setFeeBusy(false);
        }
      },
      'Reinvest'
    );
  };

  const onSaveAgent = async (patch: any) => {
    if (!editingAgent) return;
    try {
      const r = await api(`/admin/ai/agents/${editingAgent.id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      setAiAgents((prev) => prev.map((a) => (a.id === editingAgent.id ? r.agent : a)));
      setEditingAgent(null);
      notify('Agent updated', `${r.agent.name} saved.`);
    } catch (e: any) {
      notify('Update failed', e?.message || 'Try again.');
    }
  };

  if (loading || !data) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      </SafeAreaView>
    );
  }

  const agents = aiAgents.length > 0 ? aiAgents : (data.ai_agents_today || []);

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
          <QuickBtn icon="chatbubbles" label="Support" badge={supportUnread} onPress={() => router.push('/admin/support' as any)} />
          <QuickBtn icon="analytics" label="Strategist" onPress={() => router.push('/admin/strategist' as any)} />
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
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionLabel}>AI TRADING AGENTS — TODAY</Text>
          <TouchableOpacity
            testID="admin-ai-regenerate-btn"
            onPress={onRegenerateAI}
            disabled={aiBusy}
            style={[styles.smallBtn, aiBusy && { opacity: 0.6 }]}
          >
            {aiBusy ? <ActivityIndicator color={colors.bg} /> : (
              <>
                <Ionicons name="refresh" size={12} color={colors.bg} />
                <Text style={styles.smallBtnText}>Regenerate</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
        <View style={styles.agentList}>
          {agents.length === 0 ? (
            <Text style={styles.muted}>Snapshot pending (refreshes nightly)…</Text>
          ) : (
            agents.map((a: any) => (
              <TouchableOpacity
                key={a.id}
                testID={`admin-ai-agent-${a.id}`}
                style={styles.agentRow}
                onPress={() => setEditingAgent(a)}
                activeOpacity={0.7}
              >
                <View style={styles.agentLeft}>
                  <View style={[styles.dot, { backgroundColor: a.signal_strength === 'high' ? colors.primary : a.signal_strength === 'medium' ? colors.warning : colors.textTertiary }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.agentName}>{a.name}{a.enabled === false ? ' (disabled)' : ''}</Text>
                    <Text style={styles.agentStrat} numberOfLines={1}>{a.strategy}</Text>
                  </View>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[styles.agentPct, { color: a.daily_pct >= 0 ? colors.primary : colors.warning }]}>
                    {a.daily_pct >= 0 ? '+' : ''}{(a.daily_pct * 100).toFixed(2)}%
                  </Text>
                  <Text style={styles.agentWin}>{(a.win_rate * 100).toFixed(0)}% wr · tap to edit</Text>
                </View>
              </TouchableOpacity>
            ))
          )}
        </View>

        {/* Commission fees — reinvest control */}
        <Text style={styles.sectionLabel}>COMMISSION FEES POOL</Text>
        <View style={styles.feeCard}>
          <View style={styles.feeRow}>
            <View>
              <Text style={styles.feeLabel}>Available to reinvest</Text>
              <Text style={styles.feeValue} testID="admin-fees-available">
                {fees ? `${fmtSats(fees.available_sats)}  ·  ${fmtUsd(fees.available_usd)}` : '—'}
              </Text>
            </View>
            <TouchableOpacity
              testID="admin-fees-reinvest-btn"
              onPress={onReinvestFees}
              disabled={feeBusy || !fees || (fees.available_sats || 0) <= 0}
              style={[styles.primaryBtn, (feeBusy || !fees || (fees.available_sats || 0) <= 0) && { opacity: 0.4 }]}
            >
              {feeBusy ? <ActivityIndicator color={colors.bg} /> : (
                <>
                  <Ionicons name="trending-up" size={14} color={colors.bg} />
                  <Text style={styles.primaryBtnText}>Reinvest</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
          {fees ? (
            <View style={styles.feeMetaRow}>
              <Text style={styles.feeMeta}>Total collected: {fmtSats(fees.fees_collected_sats)} · {fmtUsd(fees.fees_collected_usd)}</Text>
              <Text style={styles.feeMeta}>Already reinvested: {fmtSats(fees.fees_reinvested_sats)} · {fmtUsd(fees.fees_reinvested_usd)}</Text>
            </View>
          ) : null}
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

      {/* AI Agent edit modal */}
      <AgentEditorModal
        agent={editingAgent}
        onClose={() => setEditingAgent(null)}
        onSave={onSaveAgent}
      />
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────
// AgentEditorModal — operator can nudge a single AI agent today.
// ─────────────────────────────────────────────────────────────
function AgentEditorModal({
  agent,
  onClose,
  onSave,
}: {
  agent: any | null;
  onClose: () => void;
  onSave: (patch: any) => Promise<void>;
}) {
  const [dailyPctStr, setDailyPctStr] = useState('');
  const [winRateStr, setWinRateStr] = useState('');
  const [strength, setStrength] = useState<'high' | 'medium' | 'low'>('medium');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!agent) return;
    setDailyPctStr(((agent.daily_pct ?? 0) * 100).toFixed(2));
    setWinRateStr(((agent.win_rate ?? 0) * 100).toFixed(0));
    setStrength((agent.signal_strength as any) || 'medium');
    setEnabled(agent.enabled !== false);
  }, [agent]);

  const submit = async () => {
    if (!agent) return;
    const patch: any = {};
    const dp = parseFloat(dailyPctStr);
    if (!Number.isNaN(dp)) patch.daily_pct = dp / 100;
    const wr = parseFloat(winRateStr);
    if (!Number.isNaN(wr)) patch.win_rate = Math.max(0, Math.min(100, wr)) / 100;
    patch.signal_strength = strength;
    patch.enabled = enabled;
    setSaving(true);
    try {
      await onSave(patch);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      visible={!!agent}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{agent?.name || 'Edit Agent'}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <Text style={styles.modalSub}>{agent?.strategy}</Text>

          <Text style={styles.fieldLabel}>Daily % (e.g. 1.50)</Text>
          <TextInput
            testID="admin-agent-daily-pct"
            style={styles.input}
            value={dailyPctStr}
            onChangeText={setDailyPctStr}
            keyboardType="numeric"
            placeholder="1.50"
            placeholderTextColor={colors.textTertiary}
          />

          <Text style={styles.fieldLabel}>Win rate (0–100)</Text>
          <TextInput
            testID="admin-agent-win-rate"
            style={styles.input}
            value={winRateStr}
            onChangeText={setWinRateStr}
            keyboardType="numeric"
            placeholder="65"
            placeholderTextColor={colors.textTertiary}
          />

          <Text style={styles.fieldLabel}>Signal strength</Text>
          <View style={styles.segRow}>
            {(['high', 'medium', 'low'] as const).map((s) => (
              <TouchableOpacity
                key={s}
                onPress={() => setStrength(s)}
                style={[styles.segChip, strength === s && styles.segChipActive]}
              >
                <Text style={[styles.segChipText, strength === s && styles.segChipTextActive]}>
                  {s.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <TouchableOpacity
            onPress={() => setEnabled((v) => !v)}
            style={[styles.toggleRow, { marginTop: spacing.md }]}
            activeOpacity={0.7}
          >
            <Text style={styles.fieldLabel}>Visible to users</Text>
            <View style={[styles.toggleTrack, enabled && styles.toggleTrackOn]}>
              <View style={[styles.toggleThumb, enabled && styles.toggleThumbOn]} />
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            testID="admin-agent-save-btn"
            onPress={submit}
            disabled={saving}
            style={[styles.primaryBtn, { marginTop: spacing.lg, justifyContent: 'center' }, saving && { opacity: 0.6 }]}
          >
            {saving ? <ActivityIndicator color={colors.bg} /> : (
              <>
                <Ionicons name="save" size={14} color={colors.bg} />
                <Text style={styles.primaryBtnText}>Save changes</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
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

function QuickBtn({ icon, label, onPress, badge }: any) {
  return (
    <TouchableOpacity style={styles.quickBtn} onPress={onPress} activeOpacity={0.85}>
      <Ionicons name={icon} size={16} color={colors.primary} />
      <Text style={styles.quickBtnText}>{label}</Text>
      {badge && badge > 0 ? (
        <View style={styles.quickBadge}>
          <Text style={styles.quickBadgeText}>{badge > 99 ? '99+' : badge}</Text>
        </View>
      ) : null}
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
  quickBadge: {
    minWidth: 20,
    height: 20,
    paddingHorizontal: 6,
    borderRadius: 10,
    backgroundColor: '#ef4444',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 4,
  },
  quickBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },
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

  // Build #13 — additions for AI controls + Fees reinvest + Agent editor modal
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  smallBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  smallBtnText: { color: colors.bg, fontSize: 11, fontWeight: '800' },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.md,
  },
  primaryBtnText: { color: colors.bg, fontSize: 13, fontWeight: '800' },
  feeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.md,
  },
  feeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  feeLabel: { color: colors.textTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '800' },
  feeValue: { color: colors.primary, fontSize: 16, fontWeight: '800', marginTop: 4, fontFamily: fonts.mono },
  feeMetaRow: { marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.borderSoft, gap: 2 },
  feeMeta: { color: colors.textSecondary, fontSize: 11, fontFamily: fonts.mono },

  // Modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: spacing.lg,
    paddingBottom: spacing.xl,
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  modalTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  modalSub: { color: colors.textSecondary, fontSize: 12, marginBottom: spacing.md },
  fieldLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginTop: spacing.sm,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    color: colors.text,
    fontSize: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  segRow: { flexDirection: 'row', gap: 8 },
  segChip: {
    flex: 1,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  segChipActive: {
    backgroundColor: 'rgba(16,185,129,0.15)',
    borderColor: colors.primary,
  },
  segChipText: { color: colors.textSecondary, fontSize: 11, fontWeight: '800', letterSpacing: 0.8 },
  segChipTextActive: { color: colors.primary },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  toggleTrack: {
    width: 44,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.surface,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleTrackOn: { backgroundColor: 'rgba(16,185,129,0.3)', borderColor: colors.primary },
  toggleThumb: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.textTertiary,
  },
  toggleThumbOn: {
    backgroundColor: colors.primary,
    transform: [{ translateX: 18 }],
  },
});
