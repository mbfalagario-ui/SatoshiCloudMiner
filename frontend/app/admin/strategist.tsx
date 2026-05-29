import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  ActivityIndicator, TextInput, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, radius, spacing, fonts, fmtUsd } from '@/src/utils/theme';

// Admin Strategist console — AI Trading Agents + profitability knobs in
// one place. Relocated from the home page so the consumer surface stays
// focused on the hashrate / AdMob model.
export default function Strategist() {
  const router = useRouter();
  const [agents, setAgents] = useState<any[]>([]);
  const [ticker, setTicker] = useState<string>('');
  const [config, setConfig] = useState<any>(null);
  const [edited, setEdited] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, t, c] = await Promise.allSettled([
        api('/ai/agents'),
        api('/ai/ticker'),
        api('/admin/config'),
      ]);
      if (a.status === 'fulfilled') setAgents(a.value?.agents || []);
      if (t.status === 'fulfilled') setTicker(t.value?.text || '');
      if (c.status === 'fulfilled') {
        setConfig(c.value);
        setEdited({});
      }
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const saveConfig = async () => {
    const patch: Record<string, number> = {};
    Object.entries(edited).forEach(([k, v]) => {
      const n = Number(v);
      if (Number.isFinite(n)) patch[k] = n;
    });
    if (Object.keys(patch).length === 0) return;
    setBusy(true);
    try {
      await api('/admin/config', { method: 'PATCH', body: JSON.stringify(patch) });
      await load();
      Alert.alert('Saved', 'Profitability knobs updated.');
    } catch (e: any) {
      Alert.alert('Save failed', e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  if (!config) {
    return (
      <SafeAreaView style={styles.safe}><View style={styles.center}><ActivityIndicator color={colors.primary} size="large" /></View></SafeAreaView>
    );
  }

  const knobs = [
    { key: 'payout_multiplier', label: 'Payout multiplier (lower = more profit)', step: 0.05 },
    { key: 'redeem_fee_sats', label: 'Redeem fee (sats)' },
    { key: 'redeem_min_sats', label: 'Min redeem (sats)' },
    { key: 'redeem_max_sats', label: 'Max redeem (sats)' },
    { key: 'redeem_cooldown_hours', label: 'Redeem cooldown (h)' },
    { key: 'ad_daily_cap', label: 'Daily ad cap' },
    { key: 'cross_sell_discount_pct', label: 'Cross-sell discount (%)' },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Reserve Strategist</Text>
        <View style={{ width: 32 }} />
      </View>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        {ticker ? (
          <View style={styles.tickerCard}>
            <Ionicons name="sparkles" size={14} color={colors.primary} />
            <Text style={styles.tickerText} numberOfLines={3}>{ticker}</Text>
          </View>
        ) : null}

        <Text style={styles.section}>AI Trading Agents</Text>
        <View style={styles.agentGrid}>
          {agents.map((a) => (
            <View key={a.id} style={styles.agentCard}>
              <View style={styles.agentTop}>
                <View style={[styles.agentDot, { backgroundColor: a.signal_strength === 'high' ? colors.primary : a.signal_strength === 'medium' ? colors.warning : colors.textTertiary }]} />
                <Text style={styles.agentN}>{a.name}</Text>
              </View>
              <Text style={styles.agentS}>{a.strategy}</Text>
              <View style={styles.agentBottom}>
                <Text style={[styles.agentP, { color: a.daily_pct >= 0 ? colors.primary : colors.warning }]}>
                  {a.daily_pct >= 0 ? '+' : ''}{(a.daily_pct * 100).toFixed(2)}%
                </Text>
                <Text style={styles.agentW}>{(a.win_rate * 100).toFixed(0)}% wr</Text>
              </View>
            </View>
          ))}
        </View>

        <Text style={styles.section}>Profitability Knobs</Text>
        {knobs.map(({ key, label }) => (
          <View key={key} style={styles.knobRow}>
            <Text style={styles.knobLabel}>{label}</Text>
            <TextInput
              value={edited[key] !== undefined ? edited[key] : String(config[key] ?? '')}
              onChangeText={(v) => setEdited((prev) => ({ ...prev, [key]: v }))}
              keyboardType="decimal-pad"
              style={styles.knobInput}
              testID={`knob-${key}`}
            />
          </View>
        ))}

        <TouchableOpacity disabled={busy} onPress={saveConfig} style={styles.cta} testID="strategist-save">
          <Text style={styles.ctaText}>{busy ? 'Saving...' : 'Save changes'}</Text>
        </TouchableOpacity>

        <View style={{ height: 80 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  back: { width: 32, height: 32, justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 17, fontWeight: '800' },
  scroll: { padding: spacing.lg, paddingBottom: 100 },
  tickerCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, padding: spacing.md, marginBottom: spacing.lg },
  tickerText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  section: { color: colors.text, fontSize: 16, fontWeight: '800', marginTop: spacing.sm, marginBottom: spacing.sm },
  agentGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: spacing.md },
  agentCard: { width: '48%', backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, padding: spacing.md, gap: 4 },
  agentTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  agentDot: { width: 8, height: 8, borderRadius: 4 },
  agentN: { color: colors.text, fontSize: 13, fontWeight: '800' },
  agentS: { color: colors.textSecondary, fontSize: 10 },
  agentBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 },
  agentP: { fontSize: 14, fontWeight: '800', fontFamily: fonts.mono },
  agentW: { color: colors.textTertiary, fontSize: 10, fontFamily: fonts.mono },
  knobRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, padding: spacing.md, marginBottom: 6 },
  knobLabel: { flex: 1, color: colors.text, fontSize: 12, fontWeight: '600' },
  knobInput: { color: colors.primary, fontSize: 14, fontWeight: '800', fontFamily: fonts.mono, minWidth: 70, textAlign: 'right' },
  cta: { backgroundColor: colors.primary, paddingVertical: 14, borderRadius: radius.md, alignItems: 'center', marginTop: spacing.lg },
  ctaText: { color: colors.bg, fontSize: 14, fontWeight: '900' },
});
