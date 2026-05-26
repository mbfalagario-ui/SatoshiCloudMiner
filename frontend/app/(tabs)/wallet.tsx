import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, fonts, shadows } from '@/src/utils/theme';
import { notify } from '@/src/utils/dialog';
import {
  SATS_PER_BTC,
  fmtSats,
  WITHDRAW_MIN_SATS,
  WITHDRAW_MAX_SATS,
  WITHDRAW_FEE_PCT,
  WITHDRAW_FEE_FLAT_SATS,
} from '@/src/utils/sats';

type Method = { id: string; name: string; subtitle: string; icon: string };

export default function Wallet() {
  const router = useRouter();
  const { user, refresh } = useSession();
  const [methods, setMethods] = useState<Method[]>([]);
  const [address, setAddress] = useState('');
  const [amountSatsStr, setAmountSatsStr] = useState('');
  const [minSats, setMinSats] = useState(WITHDRAW_MIN_SATS);
  const [maxSats, setMaxSats] = useState(WITHDRAW_MAX_SATS);
  const [feePct, setFeePct] = useState(WITHDRAW_FEE_PCT);
  const [feeFlat, setFeeFlat] = useState(WITHDRAW_FEE_FLAT_SATS);
  const [adminUnlimited, setAdminUnlimited] = useState(false);
  const [btcUsd, setBtcUsd] = useState(65000);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api('/withdraw/methods');
      setMethods(r.methods || []);
      if (typeof r.min_sats === 'number') setMinSats(r.min_sats);
      if (typeof r.max_sats === 'number') setMaxSats(r.max_sats);
      if (typeof r.fee_pct === 'number') setFeePct(r.fee_pct);
      if (typeof r.fee_flat_sats === 'number') setFeeFlat(r.fee_flat_sats);
      if (typeof r.btc_usd_rate === 'number') setBtcUsd(r.btc_usd_rate);
      setAdminUnlimited(Boolean(r.admin_unlimited));
    } catch {
      // keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    refresh();
  }, [load, refresh]);

  const sats = useMemo(() => {
    const n = parseInt(amountSatsStr || '0', 10);
    return isFinite(n) ? n : 0;
  }, [amountSatsStr]);

  const fee = useMemo(() => {
    if (sats <= 0) return 0;
    return Math.max(feeFlat, Math.ceil(sats * feePct) + feeFlat);
  }, [sats, feePct, feeFlat]);

  const total = sats + fee;
  const balanceSats = user?.balance_sats ?? Math.round((user?.balance_btc ?? 0) * SATS_PER_BTC);
  const usdValue = (sats / SATS_PER_BTC) * btcUsd;

  const detected = useMemo(() => {
    const a = address.trim().toLowerCase();
    if (a.startsWith('lnbc') || a.startsWith('lntb') || a.startsWith('lnbcrt')) return 'BOLT11 invoice';
    if (/^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/.test(a)) return 'Lightning address';
    if (a.length > 0) return 'Unknown — Lightning only';
    return '';
  }, [address]);

  const submit = async () => {
    if (!address.trim()) return notify('Destination required', 'Paste a Lightning invoice (lnbc…) or address (you@host).');
    if (sats < minSats) return notify('Amount too low', `Minimum withdrawal is ${fmtSats(minSats)} (≈$${((minSats / SATS_PER_BTC) * btcUsd).toFixed(2)}).`);
    if (sats > maxSats) return notify('Amount too high', `Single withdrawal is capped at ${fmtSats(maxSats)} for safety.`);
    if (total > balanceSats) return notify('Insufficient balance', `You need ${fmtSats(total)} (incl. ${fmtSats(fee)} fee) but only have ${fmtSats(balanceSats)}.`);

    setSubmitting(true);
    try {
      await api('/withdraw', {
        method: 'POST',
        body: JSON.stringify({
          method_id: 'lightning',
          address: address.trim(),
          amount_sats: sats,
        }),
      });
      await refresh();
      setAddress('');
      setAmountSatsStr('');
      notify(
        'Withdrawal sent',
        `${fmtSats(sats)} on its way via Lightning. Fee charged: ${fmtSats(fee)}.`
      );
    } catch (e: any) {
      notify('Withdrawal failed', e?.message ?? 'Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />}
        >
          <Text style={styles.title}>Withdraw</Text>
          <Text style={styles.subtitle}>Lightning only · instant payout</Text>

          <View style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>AVAILABLE BALANCE</Text>
            <Text style={styles.balanceAmount} testID="wallet-balance-sats">
              {fmtSats(balanceSats)}
            </Text>
            <Text style={styles.balanceBtc}>₿ {(user?.balance_btc ?? 0).toFixed(8)} · ≈ ${(user?.balance_usd ?? 0).toFixed(2)}</Text>
            <View style={styles.limitRow}>
              <Ionicons
                name={adminUnlimited ? 'shield-checkmark' : 'information-circle-outline'}
                size={14}
                color={adminUnlimited ? colors.primary : colors.textTertiary}
              />
              <Text style={[styles.limitText, adminUnlimited && { color: colors.primary, fontWeight: '700' }]}>
                {adminUnlimited
                  ? 'OPERATOR — withdraw any amount · 0% fee'
                  : `Min ${fmtSats(minSats)} · No max · flat ${(feePct * 100).toFixed(0)}% network fee`}
              </Text>
            </View>
          </View>

          <Text style={styles.sectionLabel}>METHOD</Text>
          <View style={styles.methods}>
            {methods.map((m) => (
              <View
                key={m.id}
                testID={`withdraw-method-${m.id}`}
                style={[styles.methodRow, styles.methodRowOn]}
              >
                <View style={[styles.methodIcon, { backgroundColor: colors.primaryDim }]}>
                  <Ionicons name={m.icon as any} size={20} color={colors.primary} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.methodName}>{m.name}</Text>
                  <Text style={styles.methodSub}>{m.subtitle}</Text>
                </View>
                <Ionicons name="checkmark-circle" size={20} color={colors.primary} />
              </View>
            ))}
          </View>

          <Text style={styles.sectionLabel}>LIGHTNING DESTINATION</Text>
          <View style={styles.inputWrap}>
            <Ionicons name="flash" size={18} color={colors.textTertiary} />
            <TextInput
              testID="wallet-address-input"
              placeholder="lnbc1… invoice or you@wallet.com"
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              value={address}
              onChangeText={setAddress}
              style={styles.input}
              multiline={address.length > 60}
            />
          </View>
          {detected ? (
            <Text style={[styles.detected, detected.startsWith('Unknown') && { color: colors.danger }]}>
              {detected}
            </Text>
          ) : null}

          <Text style={styles.sectionLabel}>AMOUNT (SATS)</Text>
          <View style={styles.inputWrap}>
            <Text style={{ color: colors.textTertiary, fontSize: 13, fontWeight: '700', letterSpacing: 1 }}>SAT</Text>
            <TextInput
              testID="wallet-amount-input"
              placeholder={`Min ${minSats.toLocaleString()}`}
              placeholderTextColor={colors.textTertiary}
              keyboardType="number-pad"
              value={amountSatsStr}
              onChangeText={(t) => setAmountSatsStr(t.replace(/[^0-9]/g, ''))}
              style={[styles.input, { fontFamily: fonts.mono, fontSize: 18 }]}
            />
            <TouchableOpacity
              testID="wallet-max-btn"
              onPress={() => {
                // Send all available balance, leaving room for the 10% fee.
                const sendable = Math.floor(balanceSats / (1 + feePct));
                setAmountSatsStr(String(Math.max(0, sendable)));
              }}
              style={styles.maxBtn}
            >
              <Text style={styles.maxBtnText}>MAX</Text>
            </TouchableOpacity>
          </View>

          {/* Fee breakdown */}
          {sats > 0 ? (
            <View style={styles.feeCard}>
              <View style={styles.feeRow}>
                <Text style={styles.feeLabel}>You send</Text>
                <Text style={styles.feeValue}>{fmtSats(sats)}</Text>
              </View>
              <View style={styles.feeRow}>
                <Text style={styles.feeLabel}>Network fee</Text>
                <Text style={[styles.feeValue, { color: colors.warning }]}>+ {fmtSats(fee)}</Text>
              </View>
              <View style={[styles.feeRow, { borderTopWidth: 1, borderTopColor: colors.borderSoft, paddingTop: 10, marginTop: 4 }]}>
                <Text style={[styles.feeLabel, { color: colors.text, fontWeight: '800' }]}>Total debited</Text>
                <Text style={[styles.feeValue, { color: colors.text, fontWeight: '800' }]}>{fmtSats(total)}</Text>
              </View>
              <Text style={styles.feeUsd}>
                ≈ ${usdValue.toFixed(4)} USD at ${btcUsd.toLocaleString()}/BTC
              </Text>
            </View>
          ) : null}

          <TouchableOpacity
            testID="wallet-submit-btn"
            style={[styles.primaryBtn, submitting && { opacity: 0.6 }]}
            disabled={submitting || sats <= 0 || !address.trim()}
            onPress={submit}
            activeOpacity={0.85}
          >
            {submitting ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Text style={styles.primaryBtnText}>Send Lightning payment</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            testID="wallet-history-btn"
            style={styles.secondaryBtn}
            onPress={() => router.push('/transactions')}
          >
            <Ionicons name="time-outline" size={16} color={colors.primary} />
            <Text style={styles.secondaryBtnText}>Transaction history</Text>
          </TouchableOpacity>

          <View style={{ height: 100 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  title: { color: colors.text, fontSize: 26, fontWeight: '800', letterSpacing: -0.6 },
  subtitle: { color: colors.textSecondary, fontSize: 13, marginBottom: spacing.lg, marginTop: 4 },
  balanceCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.lg,
    ...shadows.card,
  },
  balanceLabel: { color: colors.textTertiary, fontSize: 11, fontWeight: '700', letterSpacing: 1.2 },
  balanceAmount: {
    color: colors.text,
    fontFamily: fonts.mono,
    fontSize: 28,
    fontWeight: '800',
    marginTop: 8,
    letterSpacing: -0.6,
  },
  balanceBtc: { color: colors.primary, fontSize: 12, fontFamily: fonts.mono, fontWeight: '600', marginTop: 2 },
  limitRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.sm, flexWrap: 'wrap' },
  limitText: { color: colors.textTertiary, fontSize: 11 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },
  methods: { gap: spacing.sm, marginBottom: spacing.md },
  methodRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
  },
  methodRowOn: { borderColor: colors.primary },
  methodIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.bg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  methodName: { color: colors.text, fontSize: 14, fontWeight: '700' },
  methodSub: { color: colors.textSecondary, fontSize: 11 },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    minHeight: 52,
    gap: spacing.sm,
    marginBottom: 6,
  },
  input: { flex: 1, color: colors.text, fontSize: 15, paddingVertical: 14 },
  detected: { color: colors.textTertiary, fontSize: 11, marginBottom: spacing.md, marginLeft: 4 },
  maxBtn: {
    backgroundColor: colors.primaryDim,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.sm,
  },
  maxBtnText: { color: colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1 },
  feeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.md,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    gap: 6,
  },
  feeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  feeLabel: { color: colors.textSecondary, fontSize: 13 },
  feeValue: { color: colors.text, fontSize: 14, fontWeight: '700', fontFamily: fonts.mono },
  feeUsd: { color: colors.textTertiary, fontSize: 11, marginTop: 4 },
  primaryBtn: {
    backgroundColor: colors.primary,
    height: 52,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.sm,
    ...shadows.glow,
  },
  primaryBtnText: { color: colors.bg, fontSize: 16, fontWeight: '800' },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
    gap: 6,
  },
  secondaryBtnText: { color: colors.primary, fontSize: 14, fontWeight: '700' },
});
