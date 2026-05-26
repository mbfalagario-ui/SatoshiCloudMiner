import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Animated,
  Easing,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, shadows } from '@/src/utils/theme';
import { notify } from '@/src/utils/dialog';

type FreeForeverStatus = {
  active: boolean;
  expires_at: string | null;
  next_available_at: string | null;
  hash_rate_display: string;   // e.g. "500 GH/s"
  duration_hours: number;      // e.g. 24
  daily_yield_usd: number;
};

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function formatHMS(ms: number): string {
  if (ms <= 0) return '00:00:00';
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

type Props = {
  onActivated?: () => void;
};

export default function FreeForeverCard({ onActivated }: Props) {
  const [status, setStatus] = useState<FreeForeverStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [now, setNow] = useState<number>(Date.now());

  // Subtle pulse on the activation button when the card is idle / available.
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const load = useCallback(async () => {
    try {
      const r = await api('/free-forever/status');
      setStatus(r);
    } catch (e) {
      // Quiet fail — the rest of the dashboard still works.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Tick once a second so the countdown stays accurate without re-fetching.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Reload from backend at the moment we cross from active → inactive so the
  // UI flips back to the activation button without manual refresh.
  useEffect(() => {
    if (!status?.active || !status?.expires_at) return;
    const expiresMs = Date.parse(status.expires_at);
    if (Number.isNaN(expiresMs)) return;
    if (Date.now() >= expiresMs) {
      load();
    }
  }, [now, status, load]);

  const onActivate = async () => {
    setActivating(true);
    try {
      const r = await api('/free-forever/activate', { method: 'POST' });
      if (r?.status) setStatus(r.status);
      notify('Free Forever Activated', 'Your 24-hour complimentary plan is now mining. Come back tomorrow to reactivate it for free.');
      if (onActivated) onActivated();
    } catch (e: any) {
      notify('Activation Unavailable', e?.message || 'Please try again in a moment.');
    } finally {
      setActivating(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.cardLoading}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  if (!status) return null;

  const active = status.active && !!status.expires_at;
  const expiresMs = status.expires_at ? Date.parse(status.expires_at) : 0;
  const remainingMs = Math.max(0, expiresMs - now);

  return (
    <LinearGradient
      colors={['rgba(34, 211, 238, 0.12)', 'rgba(34, 211, 238, 0.04)']}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.card}
    >
      <View style={styles.headerRow}>
        <View style={styles.iconBadge}>
          <Ionicons name="gift" size={18} color={colors.bg} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Free Forever</Text>
          <Text style={styles.subtitle}>A complimentary mining plan for new users</Text>
        </View>
        {active ? (
          <View style={styles.activeBadge}>
            <View style={styles.activeDot} />
            <Text style={styles.activeBadgeText}>ACTIVE</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Hashpower</Text>
          <Text style={styles.statValue}>{status.hash_rate_display}</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Duration</Text>
          <Text style={styles.statValue}>24 Hours from Activation</Text>
        </View>
      </View>

      {active ? (
        <View style={styles.countdownBlock}>
          <Text style={styles.countdownLabel}>Plan resets in</Text>
          <Text style={styles.countdown}>{formatHMS(remainingMs)}</Text>
        </View>
      ) : (
        <TouchableOpacity
          testID="free-forever-activate-btn"
          onPress={onActivate}
          disabled={activating}
          activeOpacity={0.85}
        >
          <Animated.View
            style={[
              styles.activateBtn,
              activating && { opacity: 0.7 },
              {
                transform: [
                  {
                    scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.02] }),
                  },
                ],
              },
            ]}
          >
            {activating ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <>
                <Ionicons name="flash" size={18} color={colors.bg} style={{ marginRight: 8 }} />
                <Text style={styles.activateBtnText}>Activate Free Plan</Text>
              </>
            )}
          </Animated.View>
        </TouchableOpacity>
      )}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  cardLoading: {
    height: 140,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  card: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: 'rgba(34, 211, 238, 0.35)',
    ...shadows.card,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  iconBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#22d3ee',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  title: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.text,
  },
  subtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  activeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16,185,129,0.18)',
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: 'rgba(16,185,129,0.45)',
  },
  activeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10b981',
    marginRight: 6,
  },
  activeBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#10b981',
    letterSpacing: 0.5,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    backgroundColor: 'rgba(11,14,20,0.55)',
    borderRadius: radius.md,
    padding: spacing.sm,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stat: {
    flex: 1,
    paddingHorizontal: spacing.xs,
  },
  statDivider: {
    width: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.xs,
  },
  statLabel: {
    fontSize: 10,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  statValue: {
    fontSize: 14,
    color: colors.text,
    fontWeight: '700',
  },
  countdownBlock: {
    alignItems: 'center',
    paddingVertical: spacing.sm,
    backgroundColor: 'rgba(11,14,20,0.55)',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  countdownLabel: {
    fontSize: 11,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  countdown: {
    fontSize: 24,
    fontWeight: '800',
    color: '#22d3ee',
    letterSpacing: 1.5,
    fontVariant: ['tabular-nums'],
  },
  activateBtn: {
    flexDirection: 'row',
    backgroundColor: '#22d3ee',
    borderRadius: radius.md,
    paddingVertical: spacing.sm + 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  activateBtnText: {
    color: colors.bg,
    fontSize: 15,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
});
