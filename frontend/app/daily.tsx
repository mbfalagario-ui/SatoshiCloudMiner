import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, shadows, fmtUsd } from '@/src/utils/theme';

export default function Daily() {
  const router = useRouter();
  const { refresh } = useSession();
  const [status, setStatus] = useState<{ available: boolean; streak: number; reward_usd: number; next_available_at: string | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api('/daily-checkin/status');
      setStatus(r);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const claim = async () => {
    setBusy(true);
    try {
      const r = await api('/daily-checkin', { method: 'POST' });
      await refresh();
      Alert.alert('Claimed!', `You received ${fmtUsd(r.awarded_usd)}\nCurrent streak: ${r.streak}`);
      load();
    } catch (e: any) {
      Alert.alert('Try again later', e?.message ?? 'Could not claim now.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-btn" onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Daily Check-in</Text>
        <View style={{ width: 40 }} />
      </View>

      {loading || !status ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : (
        <View style={styles.content}>
          <View style={styles.bigCard}>
            <View style={styles.iconBubble}>
              <Ionicons name="gift" size={40} color={colors.primary} />
            </View>
            <Text style={styles.streak}>Day {status.streak + (status.available ? 1 : 0)}</Text>
            <Text style={styles.bigLabel}>
              {status.available ? 'Claim your reward' : 'Come back later for your next reward'}
            </Text>
            <Text style={styles.reward}>{fmtUsd(status.reward_usd)}</Text>

            <View style={styles.streakRow}>
              {[1, 2, 3, 4, 5, 6, 7].map((d) => {
                const claimed = d <= status.streak;
                return (
                  <View key={d} style={[styles.streakBox, claimed && styles.streakBoxOn]}>
                    <Text style={[styles.streakDay, claimed && { color: colors.bg }]}>{d}</Text>
                  </View>
                );
              })}
            </View>
            <Text style={styles.bonus}>Bonus +20% per consecutive day (max 7x)</Text>

            <TouchableOpacity
              testID="daily-claim-btn"
              style={[styles.claimBtn, (!status.available || busy) && { opacity: 0.5 }]}
              disabled={!status.available || busy}
              onPress={claim}
              activeOpacity={0.85}
            >
              {busy ? <ActivityIndicator color={colors.bg} /> : <Text style={styles.claimText}>{status.available ? 'Claim now' : 'Already claimed'}</Text>}
            </TouchableOpacity>

            {!status.available && status.next_available_at && (
              <Text style={styles.next}>
                Next: {new Date(status.next_available_at).toLocaleString()}
              </Text>
            )}
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.sm,
  },
  back: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface,
    justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  content: { flex: 1, padding: spacing.lg, justifyContent: 'center' },
  bigCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderSoft,
    ...shadows.card,
  },
  iconBubble: {
    width: 80, height: 80, borderRadius: 40, backgroundColor: colors.primaryDim,
    justifyContent: 'center', alignItems: 'center', marginBottom: spacing.md,
  },
  streak: { color: colors.primary, fontSize: 12, fontWeight: '800', letterSpacing: 1.2 },
  bigLabel: { color: colors.text, fontSize: 16, fontWeight: '700', marginTop: 8, textAlign: 'center' },
  reward: { color: colors.text, fontSize: 40, fontWeight: '800', marginTop: spacing.md, letterSpacing: -1 },
  streakRow: { flexDirection: 'row', gap: 6, marginTop: spacing.lg, marginBottom: spacing.sm },
  streakBox: {
    width: 32, height: 32, borderRadius: radius.sm,
    backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border,
    justifyContent: 'center', alignItems: 'center',
  },
  streakBoxOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  streakDay: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
  bonus: { color: colors.textTertiary, fontSize: 11, marginTop: spacing.sm },
  claimBtn: {
    width: '100%',
    height: 52,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.lg,
    ...shadows.glow,
  },
  claimText: { color: colors.bg, fontSize: 16, fontWeight: '800' },
  next: { color: colors.textSecondary, fontSize: 12, marginTop: spacing.md },
});
