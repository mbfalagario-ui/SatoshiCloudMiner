import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { api } from '@/src/utils/api';
import { colors, radius, spacing, fonts, fmtGhs } from '@/src/utils/theme';

type Status = {
  available: boolean;
  streak: number;
  next_step: number;
  ladder_ghs: number[];
  next_reward_ghs: number;
  boost_duration_hours: number;
};

export default function DailyCheckinCard({ onClaim }: { onClaim?: () => void }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await api('/daily-checkin/status');
      setStatus(s);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const claim = async () => {
    if (!status?.available) {
      router.push('/daily');
      return;
    }
    setBusy(true);
    try {
      const r = await api('/daily-checkin', { method: 'POST' });
      await load();
      onClaim?.();
      Alert.alert(
        'Reward claimed',
        `Day ${r.streak} +${status.next_reward_ghs} GH/s for 24 hours`,
      );
    } catch (e: any) {
      Alert.alert('Try again later', e?.message || 'Already claimed today');
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  return (
    <TouchableOpacity activeOpacity={0.9} onPress={() => router.push('/daily')} style={styles.wrap} testID="daily-card">
      <LinearGradient
        colors={['#11334D', '#0F4F6E']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.card}
      >
        <View style={styles.row}>
          <View style={styles.iconBox}>
            <Ionicons name="gift" size={22} color="#00FFA3" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Daily Check-In</Text>
            <Text style={styles.sub} numberOfLines={2}>
              {status.available
                ? `Tap to claim Day ${status.next_step}: +${fmtGhs(status.next_reward_ghs)} for 24h`
                : `Day ${status.streak} claimed · Come back tomorrow for Day ${status.next_step} (+${fmtGhs(status.next_reward_ghs)})`}
            </Text>
            <Text style={styles.streak}> Streak: {status.streak}/7 days</Text>
          </View>
          <TouchableOpacity
            onPress={claim}
            disabled={busy || !status.available}
            style={[styles.btn, !status.available && styles.btnMuted]}
            testID="daily-claim-btn"
          >
            <Text style={styles.btnText}>{status.available ? (busy ? '...' : 'Claim') : 'Claimed'}</Text>
          </TouchableOpacity>
        </View>
      </LinearGradient>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md },
  card: { borderRadius: radius.lg, padding: spacing.md, borderWidth: 1, borderColor: colors.borderSoft },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconBox: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(0,255,163,0.15)',
    justifyContent: 'center', alignItems: 'center',
  },
  title: { color: '#fff', fontSize: 15, fontWeight: '800' },
  sub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 3 },
  streak: { color: '#00FFA3', fontSize: 11, fontWeight: '700', marginTop: 4, fontFamily: fonts.mono },
  btn: {
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: '#00FFA3',
  },
  btnMuted: { backgroundColor: 'rgba(255,255,255,0.15)' },
  btnText: { color: '#0B0E14', fontSize: 13, fontWeight: '800' },
});
