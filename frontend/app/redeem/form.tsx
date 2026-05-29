import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, radius, spacing, fonts, fmtBtc, fmtSats, fmtUsd } from '@/src/utils/theme';

const WALLETS = [
  { id: 'speed', label: 'Speed', sub: 'user@speed.app', icon: 'flash' as const },
  { id: 'zbd', label: 'ZBD', sub: 'user@zbd.gg', icon: 'rocket' as const },
  { id: 'wos', label: 'Wallet of Satoshi', sub: 'user@walletofsatoshi.com', icon: 'wallet' as const },
  { id: 'bolt11', label: 'BOLT11 Invoice', sub: 'lnbc...', icon: 'document-text' as const },
];

export default function RedeemForm() {
  const router = useRouter();
  const [methods, setMethods] = useState<any>(null);
  const [earnings, setEarnings] = useState<any>(null);
  const [walletId, setWalletId] = useState<string>('speed');
  const [amount, setAmount] = useState<string>('');
  const [address, setAddress] = useState<string>('');
  const [quote, setQuote] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, e] = await Promise.allSettled([
        api('/withdraw/methods'),
        api('/earnings'),
      ]);
      if (m.status === 'fulfilled') setMethods(m.value);
      if (e.status === 'fulfilled') setEarnings(e.value);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const balanceSats = Math.floor((earnings?.indicative_balance_btc || 0) * 100_000_000);
  const minSats = methods?.min_sats || 25000;
  const maxSats = methods?.max_sats || 50000;
  const feeSats = methods?.fee_flat_sats || 0;

  const setAll = () => {
    const a = Math.max(0, Math.min(maxSats, balanceSats - feeSats));
    setAmount(String(a));
  };

  const fetchQuote = useCallback(async (n: number) => {
    if (!n || n <= 0) {
      setQuote(null);
      return;
    }
    try {
      const q = await api('/redeem/quote', { method: 'POST', body: JSON.stringify({ amount_sats: n }) });
      setQuote(q);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Unable to compute fee');
      setQuote(null);
    }
  }, []);

  useEffect(() => {
    const n = Math.floor(Number(amount));
    if (Number.isFinite(n) && n > 0) {
      const t = setTimeout(() => fetchQuote(n), 350);
      return () => clearTimeout(t);
    } else {
      setQuote(null);
    }
  }, [amount, fetchQuote]);

  const goConfirm = () => {
    if (!quote || !quote.ok) {
      setError(quote?.errors?.[0] || 'Fix the amount and try again');
      return;
    }
    if (!address.trim()) {
      setError('Enter a Lightning invoice or address');
      return;
    }
    router.push({
      pathname: '/redeem/confirm',
      params: {
        amount: String(quote.amount_sats),
        fee: String(quote.fee_sats),
        total: String(quote.total_debit_sats),
        address: address.trim(),
      },
    });
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.back}>
            <Ionicons name="chevron-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.title}>Redeem</Text>
          <View style={{ width: 32 }} />
        </View>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.label}>Total Balance</Text>
          <Text style={styles.balance}>{fmtBtc((earnings?.indicative_balance_btc || 0))} BTC</Text>
          <Text style={styles.balanceSub}>{fmtSats(balanceSats)} sats · {fmtUsd((earnings?.btc_usd || 0) * (earnings?.indicative_balance_btc || 0))}</Text>

          <Text style={styles.section}>Select collection wallet</Text>
          {WALLETS.map((w) => (
            <TouchableOpacity
              key={w.id}
              onPress={() => setWalletId(w.id)}
              style={[styles.walletRow, walletId === w.id && styles.walletRowActive]}
            >
              <View style={styles.walletIcon}><Ionicons name={w.icon} size={18} color={colors.primary} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.walletName}>{w.label}</Text>
                <Text style={styles.walletSub}>{w.sub}</Text>
              </View>
              {walletId === w.id ? <Ionicons name="checkmark-circle" size={20} color={colors.primary} /> : <Ionicons name="ellipse-outline" size={20} color={colors.textTertiary} />}
            </TouchableOpacity>
          ))}

          <Text style={styles.section}>Amount ({minSats.toLocaleString()} – {maxSats.toLocaleString()} sats)</Text>
          <View style={styles.amountRow}>
            <TextInput
              value={amount}
              onChangeText={setAmount}
              placeholder="0"
              placeholderTextColor={colors.textTertiary}
              keyboardType="number-pad"
              style={styles.amountInput}
              testID="redeem-amount-input"
            />
            <Text style={styles.amountUnit}>sats</Text>
            <TouchableOpacity onPress={setAll} style={styles.allBtn}>
              <Text style={styles.allText}>All</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.section}>Invoice / Lightning address</Text>
          <TextInput
            value={address}
            onChangeText={setAddress}
            placeholder={walletId === 'bolt11' ? 'lnbc...' : `user@${walletId === 'zbd' ? 'zbd.gg' : walletId === 'wos' ? 'walletofsatoshi.com' : 'speed.app'}`}
            placeholderTextColor={colors.textTertiary}
            style={styles.addressInput}
            autoCapitalize="none"
            autoCorrect={false}
            testID="redeem-address-input"
          />
          <Text style={styles.helper}>Make sure the amount entered when creating a BOLT11 invoice is 0 sats = 0 BTC.</Text>

          {/* Fee preview */}
          {quote ? (
            <View style={styles.previewCard}>
              <Row label="Amount" value={`${fmtSats(quote.amount_sats)} sats`} />
              <Row label="Network fee" value={`${fmtSats(quote.fee_sats)} sats`} warn />
              <Row label="Total debited" value={`${fmtSats(quote.total_debit_sats)} sats`} strong />
              <Row label="Remaining" value={`${fmtSats(quote.remaining_balance_sats)} sats`} />
            </View>
          ) : null}

          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          {!quote?.ok && quote?.errors?.length ? (
            <View style={styles.errorBox}>
              {quote.errors.map((e: string, i: number) => (
                <Text key={i} style={styles.errorText}>• {e}</Text>
              ))}
            </View>
          ) : null}

          <View style={{ height: spacing.lg }} />
          <TouchableOpacity
            onPress={goConfirm}
            disabled={busy || !quote?.ok || !address.trim()}
            style={[styles.cta, (!quote?.ok || !address.trim() || busy) && styles.ctaMuted]}
            testID="redeem-next-btn"
          >
            <Text style={[styles.ctaText, (!quote?.ok || !address.trim()) && { color: colors.textTertiary }]}>
              Review redeem
            </Text>
          </TouchableOpacity>

          <TouchableOpacity onPress={() => router.push('/legal?focus=redeem')} style={styles.readLink}>
            <Ionicons name="information-circle" size={14} color={colors.textSecondary} />
            <Text style={styles.readText}>Please read carefully before redeem  ›</Text>
          </TouchableOpacity>
          <View style={{ height: 80 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Row({ label, value, strong, warn }: any) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowL}>{label}</Text>
      <Text style={[styles.rowR, strong && { color: colors.text, fontWeight: '800' }, warn && { color: colors.warning }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  back: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  scroll: { padding: spacing.lg, paddingBottom: 80 },
  label: { color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  balance: { color: colors.primary, fontSize: 30, fontWeight: '800', fontFamily: fonts.mono, marginTop: 2 },
  balanceSub: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  section: { color: colors.text, fontSize: 14, fontWeight: '800', marginTop: spacing.lg, marginBottom: 6 },
  walletRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: spacing.md, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, marginBottom: 6 },
  walletRowActive: { borderColor: colors.primary },
  walletIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: 'rgba(0,255,163,0.15)', alignItems: 'center', justifyContent: 'center' },
  walletName: { color: colors.text, fontSize: 13, fontWeight: '700' },
  walletSub: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  amountRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, paddingHorizontal: 12, paddingVertical: 4 },
  amountInput: { flex: 1, color: colors.text, fontSize: 22, fontWeight: '800', fontFamily: fonts.mono, paddingVertical: 10 },
  amountUnit: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
  allBtn: { paddingHorizontal: 10, paddingVertical: 6, backgroundColor: colors.primary, borderRadius: 10 },
  allText: { color: colors.bg, fontWeight: '800', fontSize: 12 },
  addressInput: { backgroundColor: colors.surface, color: colors.text, fontSize: 13, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, fontFamily: fonts.mono },
  helper: { color: colors.textTertiary, fontSize: 11, marginTop: 6 },
  previewCard: { marginTop: spacing.md, padding: spacing.md, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, gap: 4 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  rowL: { color: colors.textSecondary, fontSize: 12 },
  rowR: { color: colors.text, fontSize: 13, fontFamily: fonts.mono, fontWeight: '600' },
  errorBox: { marginTop: spacing.sm, backgroundColor: 'rgba(255,51,102,0.08)', borderWidth: 1, borderColor: 'rgba(255,51,102,0.35)', borderRadius: radius.md, padding: spacing.sm },
  errorText: { color: colors.danger, fontSize: 12, marginVertical: 2 },
  cta: { backgroundColor: colors.primary, paddingVertical: 16, borderRadius: radius.md, alignItems: 'center', marginTop: spacing.md },
  ctaMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  ctaText: { color: colors.bg, fontSize: 15, fontWeight: '900' },
  readLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: spacing.md },
  readText: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
});
