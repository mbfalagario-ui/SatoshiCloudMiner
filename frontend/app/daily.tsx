import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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
  next_available_at: string;
};

export default function DailyCheckin() {
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
    if (!status?.available) return;
    setBusy(true);
    try {
      const r = await api('/daily-checkin', { method: 'POST' });
      await load();
      Alert.alert(
        'Reward claimed',
        `Day ${r.streak} · +${fmtGhs(status.next_reward_ghs)} active for 24 hours`,
      );
    } catch (e: any) {
      Alert.alert('Try again later', e?.message || 'Already claimed today');
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return (
      <SafeAreaView style={styles.safe}><View style={styles.center}><ActivityIndicator color={colors.primary} size="large" /></View></SafeAreaView>
    );
  }

  const ladder = status.ladder_ghs || [];
  const currentStreak = status.streak;
  const todaysStep = status.next_step;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Daily Check-In</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.subtitle}>Sign in to receive rewards</Text>
        <Text style={styles.subline}>Bigger boosts every consecutive day. Miss a day and the streak resets.</Text>

        <View style={styles.grid}>
          {ladder.map((ghs, idx) => {
            const day = idx + 1;
            const isToday = status.available && day === todaysStep;
            const isClaimedToday = !status.available && day === currentStreak;
            const isPast = day < currentStreak || isClaimedToday;
            const isFuture = day > todaysStep && !isPast;
            return (
              <View
                key={day}
                style={[
                  styles.dayCard,
                  isToday && styles.dayToday,
                  isPast && styles.dayPast,
                  isFuture && styles.dayFuture,
                ]}
                testID={`day-card-${day}`}
              >
                <Text style={[styles.dayLabel, isToday && { color: colors.bg }]}>Day {day}</Text>
                <View style={styles.dayIcon}>
                  {isPast ? (
                    <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
                  ) : (
                    <Ionicons name="flash" size={24} color={isToday ? colors.bg : colors.primary} />
                  )}
                </View>
                <Text style={[styles.dayReward, isToday && { color: colors.bg }]}>{ghs} GH/s</Text>
                {isToday ? (
                  <View style={styles.availablePill}>
                    <Text style={styles.availableText}>Available</Text>
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>

        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={18} color={colors.textSecondary} />
          <Text style={styles.infoText}>Each reward lasts 24 hours. Come back the next day to keep your streak going.</Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          onPress={claim}
          disabled={!status.available || busy}
          style={[styles.cta, !status.available && styles.ctaMuted]}
          testID="daily-claim-btn"
        >
          <LinearGradient
            colors={status.available ? ['#00FFA3', '#00D1FF'] : ['#1F2633', '#1F2633']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.ctaInner}
          >
            <Text style={[styles.ctaText, !status.available && { color: colors.textTertiary }]}>
              {status.available
                ? (busy ? 'Claiming...' : `Claim Day ${todaysStep} · +${fmtGhs(status.next_reward_ghs)}`)
                : 'Check in tomorrow'}
            </Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  back: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  scroll: { padding: spacing.lg, paddingBottom: 120 },
  subtitle: { color: colors.text, fontSize: 22, fontWeight: '800' },
  subline: { color: colors.textSecondary, fontSize: 13, marginTop: 6, marginBottom: spacing.lg },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, justifyContent: 'space-between' },
  dayCard: {
    width: '47%',
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    alignItems: 'flex-start',
    gap: 6,
  },
  dayToday: { backgroundColor: colors.primary, borderColor: colors.primary },
  dayPast: { opacity: 0.55 },
  dayFuture: { opacity: 0.9 },
  dayLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '800', letterSpacing: 1 },
  dayIcon: { marginVertical: 6 },
  dayReward: { color: colors.text, fontSize: 18, fontWeight: '800', fontFamily: fonts.mono },
  availablePill: { backgroundColor: 'rgba(0,0,0,0.18)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginTop: 4 },
  availableText: { color: colors.bg, fontSize: 10, fontWeight: '800' },
  infoCard: {
    marginTop: spacing.lg,
    flexDirection: 'row',
    gap: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.md,
    borderRadius: radius.md,
  },
  infoText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 16 },
  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: spacing.lg, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  cta: { borderRadius: radius.md, overflow: 'hidden' },
  ctaMuted: {},
  ctaInner: { paddingVertical: 16, alignItems: 'center' },
  ctaText: { color: colors.bg, fontSize: 15, fontWeight: '800' },
});
