import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Share, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, fmtUsd, shadows } from '@/src/utils/theme';

export default function Referral() {
  const router = useRouter();
  const [info, setInfo] = useState<{ code: string; invited_count: number; bonus_per_invite_usd: number; share_text: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await api('/referral');
      setInfo(r);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onShare = async () => {
    if (!info) return;
    try {
      await Share.share({ message: info.share_text });
    } catch (e: any) {
      Alert.alert('Sharing failed', e?.message ?? 'Try again');
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-btn" onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Invite friends</Text>
        <View style={{ width: 40 }} />
      </View>

      {loading || !info ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : (
        <View style={styles.content}>
          <View style={styles.bubble}>
            <Ionicons name="people" size={36} color={colors.primary} />
          </View>
          <Text style={styles.h1}>Earn {fmtUsd(info.bonus_per_invite_usd)} per friend</Text>
          <Text style={styles.h2}>Share your code with friends. When they sign up, you both earn rewards.</Text>

          <View style={styles.codeCard}>
            <Text style={styles.codeLabel}>YOUR CODE</Text>
            <Text style={styles.code} testID="referral-code">{info.code}</Text>
          </View>

          <View style={styles.statRow}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{info.invited_count}</Text>
              <Text style={styles.statLabel}>Friends invited</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{fmtUsd(info.invited_count * info.bonus_per_invite_usd)}</Text>
              <Text style={styles.statLabel}>Earned</Text>
            </View>
          </View>

          <TouchableOpacity testID="referral-share-btn" style={styles.share} onPress={onShare} activeOpacity={0.85}>
            <Ionicons name="share-social" size={18} color={colors.bg} />
            <Text style={styles.shareText}>Share invitation</Text>
          </TouchableOpacity>
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
  content: { padding: spacing.lg, alignItems: 'center' },
  bubble: {
    width: 76, height: 76, borderRadius: 38, backgroundColor: colors.primaryDim,
    justifyContent: 'center', alignItems: 'center', marginTop: spacing.lg,
  },
  h1: { color: colors.text, fontSize: 22, fontWeight: '800', marginTop: spacing.md, textAlign: 'center', letterSpacing: -0.5 },
  h2: { color: colors.textSecondary, fontSize: 13, marginTop: 6, textAlign: 'center', paddingHorizontal: spacing.md },
  codeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1, borderColor: colors.borderSoft,
    width: '100%', marginTop: spacing.lg, alignItems: 'center',
  },
  codeLabel: { color: colors.textTertiary, fontSize: 11, fontWeight: '700', letterSpacing: 1.2 },
  code: { color: colors.primary, fontSize: 34, fontWeight: '800', fontFamily: fonts.mono, marginTop: 8, letterSpacing: 4 },
  statRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md, width: '100%' },
  stat: {
    flex: 1, backgroundColor: colors.surface, borderRadius: radius.md,
    padding: spacing.md, borderWidth: 1, borderColor: colors.borderSoft, alignItems: 'center',
  },
  statValue: { color: colors.text, fontSize: 20, fontWeight: '800', fontFamily: fonts.mono },
  statLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '600', marginTop: 4 },
  share: {
    flexDirection: 'row',
    width: '100%', height: 52, marginTop: spacing.lg,
    backgroundColor: colors.primary, borderRadius: radius.md,
    justifyContent: 'center', alignItems: 'center', gap: 8, ...shadows.glow,
  },
  shareText: { color: colors.bg, fontSize: 15, fontWeight: '800' },
});
