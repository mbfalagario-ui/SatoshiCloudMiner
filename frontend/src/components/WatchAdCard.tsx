import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
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
  const { showRewarded, isRewardedLoaded, rewardedError } = useAds();

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
    if (!isRewardedLoaded) {
      Alert.alert(
        rewardedError ? 'Ad service unavailable' : 'Ad not ready',
        rewardedError
          ? rewardedError + ' The next ad is being requested in the background.'
          : 'The ad is still loading — please try again in a few seconds.',
      );
      return;
    }
    setBusy(true);
    try {
      // Apple Guideline 2.1(a): this MUST trigger a real Google AdMob
      // rewarded video. `showRewarded` is wired to RewardedAd.show()
      // in src/utils/ads.ts. Resolves true if the user watched the ad
      // to completion (EARNED_REWARD fired), false if they closed early.
      const earned = await showRewarded('home-watch-ad');
      if (!earned) {
        // User closed without earning — do NOT credit. Silent exit.
        return;
      }
      // User earned: credit the boost server-side. AdMob's SSV callback
      // will also hit /api/ads/ssv_callback in parallel for backend
      // cryptographic verification (defence-in-depth).
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
  const noneLeft = left <= 0;
  const hasError = !!rewardedError && !isRewardedLoaded;
  const adNotReady = !isRewardedLoaded && !noneLeft && !hasError;
  const buttonLabel = busy
    ? '…'
    : noneLeft
    ? 'Done'
    : hasError
    ? 'Retry'
    : adNotReady
    ? 'Loading…'
    : 'Watch';
  const buttonDisabled = busy || noneLeft || adNotReady;

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
            disabled={buttonDisabled}
            style={[
              styles.btn,
              (noneLeft || adNotReady) && styles.btnMuted,
            ]}
            testID="watch-ad-btn"
          >
            <Text style={[styles.btnText, (noneLeft || adNotReady) && styles.btnTextMuted]}>
              {buttonLabel}
            </Text>
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
    minWidth: 72,
    alignItems: 'center',
  },
  btnMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  btnText: { color: '#0B0E14', fontSize: 13, fontWeight: '800' },
  btnTextMuted: { color: colors.textTertiary },
});
