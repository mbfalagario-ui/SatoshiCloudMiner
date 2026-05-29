import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, radius, spacing, fonts, fmtGhs } from '@/src/utils/theme';
import { useAds } from '@/src/AdContext';

type Status = {
  ads_today: number;
  daily_cap: number;
  remaining_today: number;
  active_ad_hashrate_ghs: number;
  next_reward_ghs: number;
  boost_duration_hours: number;
};

export default function WatchAdCard({ onClaim }: { onClaim?: () => void }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const { showRewarded } = useAds();

  const load = useCallback(async () => {
    try {
      const s = await api('/ads/status');
      setStatus(s);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const onWatch = async () => {
    if (!status || status.remaining_today <= 0) {
      Alert.alert('All caught up!', 'You’ve watched all rewarded ads available today. New ads tomorrow.');
      return;
    }
    setBusy(true);
    try {
      // Show real AdMob rewarded video when available, otherwise simulate.
      try {
        await showRewarded?.('home-watch-ad');
      } catch {}
      const r = await api('/ads/claim_dev', { method: 'POST' });
      await load();
      onClaim?.();
      Alert.alert(
        'Boost activated!',
        `+${r.reward_ghs} GH/s for 24h. ${r.remaining_today} more ad${r.remaining_today === 1 ? '' : 's'} available today.`,
      );
    } catch (e: any) {
      Alert.alert('Try again', e?.message || 'Reward failed');
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;
  const left = status.remaining_today;
  const next = status.next_reward_ghs;

  return (
    <View style={styles.wrap}>
      <LinearGradient
        colors={['#1F2633', '#151A22']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.card}
      >
        <View style={styles.row}>
          <View style={styles.iconBox}>
            <Ionicons name="play-circle" size={22} color={colors.secondary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Watch ad — free hashrate</Text>
            <Text style={styles.sub}>
              Next reward: +{fmtGhs(next)} for 24h · {left} of {status.daily_cap} available
            </Text>
            <Text style={styles.active} numberOfLines={1}>
              Active ad hashrate: {fmtGhs(status.active_ad_hashrate_ghs)}
            </Text>
          </View>
          <TouchableOpacity
            onPress={onWatch}
            disabled={busy || left <= 0}
            style={[styles.btn, left <= 0 && styles.btnMuted]}
            testID="watch-ad-btn"
          >
            <Text style={styles.btnText}>{busy ? '...' : left <= 0 ? 'Done' : 'Watch'}</Text>
          </TouchableOpacity>
        </View>
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md },
  card: { borderRadius: radius.lg, padding: spacing.md, borderWidth: 1, borderColor: colors.borderSoft },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconBox: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(0,209,255,0.15)',
    justifyContent: 'center', alignItems: 'center',
  },
  title: { color: colors.text, fontSize: 14, fontWeight: '700' },
  sub: { color: colors.textSecondary, fontSize: 11, marginTop: 3 },
  active: { color: colors.primary, fontSize: 11, fontWeight: '700', marginTop: 2, fontFamily: fonts.mono },
  btn: {
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: colors.secondary,
  },
  btnMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  btnText: { color: '#0B0E14', fontSize: 13, fontWeight: '800' },
});
