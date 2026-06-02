import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, radius, spacing, fonts, fmtSats } from '@/src/utils/theme';

export default function RedeemConfirm() {
  const router = useRouter();
  const params = useLocalSearchParams<{ amount: string; fee: string; total: string; address: string }>();
  const amount = Number(params.amount || '0');
  const fee = Number(params.fee || '0');
  const total = Number(params.total || '0');
  const address = String(params.address || '');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api('/withdraw', {
        method: 'POST',
        body: JSON.stringify({
          method_id: 'lightning',
          address,
          amount_sats: amount,
        }),
      });
      Alert.alert(
        'Redeem submitted',
        `Your Lightning payout is on its way.\nStatus: ${r.transaction?.status || 'pending'}`,
        [{ text: 'OK', onPress: () => router.replace('/(tabs)/wallet') }],
      );
    } catch (e: any) {
      Alert.alert('Redeem failed', e?.message || 'Please try again');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.close}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Confirm redeem</Text>
        <View style={{ width: 32 }} />
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.alertCard}>
          <Ionicons name="warning" size={18} color={colors.warning} />
          <Text style={styles.alertText}>
            Once submitted, your Lightning payout is irreversible. Double-check the amount and address.
          </Text>
        </View>

        <View style={styles.card}>
          <Row label="You will receive" value={`${fmtSats(amount)} sats`} big />
          <Row label="Network fee" value={`${fmtSats(fee)} sats`} warn />
          <Row label="Total debited from balance" value={`${fmtSats(total)} sats`} strong />
        </View>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Sending to</Text>
          <Text style={styles.addr} numberOfLines={2}>{address}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.bulletTitle}>Please read carefully before redeem</Text>
          <Bullet text="This app does not custody on-chain assets; your wallet remains in your sole control." />
          <Bullet text="Amount limits: 25,000 – 50,000 sats per redeem." />
          <Bullet text="Address format: lnbc... BOLT11 invoice or LN address (e.g. user@speed.app, user@zbd.gg)." />
          <Bullet text="Network fees: deducted from your balance at redeem time. Not subsidized." />
          <Bullet text="Processing: instant via Lightning Network." />
          <Bullet text="Cooldown: only one redeem per 24 hours." />
          <Bullet text="Security: never share your private keys or seed phrase with anyone." />
          <Bullet text="Support: open the Support screen in the app and submit a ticket from your registered account." />
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          disabled={busy}
          onPress={submit}
          style={[styles.cta, busy && styles.ctaMuted]}
          testID="redeem-confirm-btn"
        >
          <Text style={styles.ctaText}>{busy ? 'Sending...' : `Redeem ${fmtSats(amount)} sats`}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function Row({ label, value, big, strong, warn }: any) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowL}>{label}</Text>
      <Text style={[styles.rowR, big && { fontSize: 18 }, strong && { color: colors.text, fontWeight: '900' }, warn && { color: colors.warning }]}>{value}</Text>
    </View>
  );
}
function Bullet({ text }: { text: string }) {
  return (
    <View style={styles.bullet}>
      <View style={styles.bulletDot} />
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  close: { width: 32, height: 32, justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  scroll: { padding: spacing.lg, paddingBottom: 120 },
  alertCard: { flexDirection: 'row', gap: 8, padding: spacing.md, backgroundColor: 'rgba(255,184,0,0.08)', borderWidth: 1, borderColor: 'rgba(255,184,0,0.35)', borderRadius: radius.md, marginBottom: spacing.md },
  alertText: { flex: 1, color: colors.warning, fontSize: 12, lineHeight: 16 },
  card: { padding: spacing.md, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, marginBottom: spacing.md, gap: 6 },
  cardLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  addr: { color: colors.text, fontSize: 13, fontFamily: fonts.mono, marginTop: 6 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  rowL: { color: colors.textSecondary, fontSize: 12 },
  rowR: { color: colors.text, fontSize: 14, fontFamily: fonts.mono, fontWeight: '700' },
  bulletTitle: { color: colors.text, fontSize: 13, fontWeight: '800', marginBottom: 6 },
  bullet: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingVertical: 3 },
  bulletDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.primary, marginTop: 8 },
  bulletText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 16 },
  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: spacing.lg, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  cta: { backgroundColor: colors.primary, paddingVertical: 16, borderRadius: radius.md, alignItems: 'center' },
  ctaMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  ctaText: { color: colors.bg, fontSize: 15, fontWeight: '900' },
});
