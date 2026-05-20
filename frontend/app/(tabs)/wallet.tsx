import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, fonts, fmtUsd, shadows } from '@/src/utils/theme';

type Method = { id: string; name: string; subtitle: string; icon: string };

export default function Wallet() {
  const router = useRouter();
  const { user, refresh } = useSession();
  const [methods, setMethods] = useState<Method[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [address, setAddress] = useState('');
  const [amount, setAmount] = useState('');
  const [minUsd, setMinUsd] = useState(1);
  const [maxDaily, setMaxDaily] = useState(2);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api('/withdraw/methods');
      setMethods(r.methods);
      setMinUsd(r.min_usd);
      setMaxDaily(r.max_daily_usd);
    } catch {}
    finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    refresh();
  }, [load, refresh]);

  const submit = async () => {
    const n = parseFloat(amount);
    if (!selected) return Alert.alert('Choose method', 'Please select a withdrawal method.');
    if (!address.trim()) return Alert.alert('Address required', 'Enter wallet address or destination.');
    if (!n || n < minUsd) return Alert.alert('Amount too low', `Minimum withdrawal is ${fmtUsd(minUsd)}.`);
    if (n > (user?.balance_usd ?? 0)) return Alert.alert('Insufficient balance', 'You do not have enough balance.');

    setSubmitting(true);
    try {
      await api('/withdraw', {
        method: 'POST',
        body: JSON.stringify({ method_id: selected, address: address.trim(), amount_usd: n }),
      });
      await refresh();
      setAddress('');
      setAmount('');
      Alert.alert(
        'Withdrawal requested',
        'Your withdrawal is being processed. You can track it in the transaction history.'
      );
    } catch (e: any) {
      Alert.alert('Withdrawal failed', e?.message ?? 'Please try again.');
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
          <Text style={styles.subtitle}>Send your earnings to your wallet</Text>

          <View style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>AVAILABLE BALANCE</Text>
            <Text style={styles.balanceAmount} testID="wallet-balance-usd">
              {fmtUsd(user?.balance_usd ?? 0)}
            </Text>
            <Text style={styles.balanceBtc}>₿ {(user?.balance_btc ?? 0).toFixed(8)}</Text>
            <View style={styles.limitRow}>
              <Ionicons name="information-circle-outline" size={14} color={colors.textTertiary} />
              <Text style={styles.limitText}>
                Min {fmtUsd(minUsd)} · 24h cap {fmtUsd(maxDaily)}
              </Text>
            </View>
          </View>

          <Text style={styles.sectionLabel}>METHOD</Text>
          <View style={styles.methods}>
            {methods.map((m) => (
              <TouchableOpacity
                key={m.id}
                testID={`withdraw-method-${m.id}`}
                style={[styles.methodRow, selected === m.id && styles.methodRowOn]}
                activeOpacity={0.8}
                onPress={() => setSelected(m.id)}
              >
                <View
                  style={[
                    styles.methodIcon,
                    selected === m.id && { backgroundColor: colors.primaryDim },
                  ]}
                >
                  <Ionicons name={m.icon as any} size={20} color={colors.primary} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.methodName}>{m.name}</Text>
                  <Text style={styles.methodSub}>{m.subtitle}</Text>
                </View>
                <View style={[styles.radio, selected === m.id && styles.radioOn]}>
                  {selected === m.id && <View style={styles.radioInner} />}
                </View>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.sectionLabel}>DESTINATION</Text>
          <View style={styles.inputWrap}>
            <Ionicons name="location-outline" size={18} color={colors.textTertiary} />
            <TextInput
              testID="wallet-address-input"
              placeholder="Address, invoice or $cashtag"
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              value={address}
              onChangeText={setAddress}
              style={styles.input}
            />
          </View>

          <Text style={styles.sectionLabel}>AMOUNT (USD)</Text>
          <View style={styles.inputWrap}>
            <Text style={{ color: colors.textTertiary, fontSize: 16, fontWeight: '600' }}>$</Text>
            <TextInput
              testID="wallet-amount-input"
              placeholder={`${minUsd.toFixed(2)} - ${maxDaily.toFixed(2)}`}
              placeholderTextColor={colors.textTertiary}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
              style={[styles.input, { fontFamily: fonts.mono, fontSize: 18 }]}
            />
            <TouchableOpacity
              testID="wallet-max-btn"
              onPress={() => setAmount(Math.min(user?.balance_usd ?? 0, maxDaily).toFixed(2))}
              style={styles.maxBtn}
            >
              <Text style={styles.maxBtnText}>MAX</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            testID="wallet-submit-btn"
            style={[styles.primaryBtn, submitting && { opacity: 0.6 }]}
            disabled={submitting}
            onPress={submit}
            activeOpacity={0.85}
          >
            {submitting ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Text style={styles.primaryBtnText}>Request withdrawal</Text>
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
    fontSize: 32,
    fontWeight: '800',
    marginTop: 8,
    letterSpacing: -1,
  },
  balanceBtc: { color: colors.primary, fontSize: 13, fontFamily: fonts.mono, fontWeight: '600', marginTop: 2 },
  limitRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.sm },
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
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioOn: { borderColor: colors.primary },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    height: 52,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  input: { flex: 1, color: colors.text, fontSize: 15, paddingVertical: 0 },
  maxBtn: {
    backgroundColor: colors.primaryDim,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.sm,
  },
  maxBtnText: { color: colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1 },
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
