import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  ActivityIndicator, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, spacing, radius, fonts, media, shadows, fmtUsd, fmtBtc, fmtSats } from '@/src/utils/theme';
import CrossSellBanner from '@/src/components/CrossSellBanner';
import TickingBtc from '@/src/components/TickingBtc';

type EarningsPayload = {
  indicative_balance_btc: number;
  lifetime_earnings_btc: number;
  hashrate: { total_ghs: number; pack_ghs: number; checkin_ghs: number; ad_ghs: number };
  indicative_daily_btc?: number;
  indicative_per_second_btc?: number;
  payout_multiplier?: number;
  btc_usd?: number;
  disclaimer?: string;
  min_redeem_sats?: number;
};

export default function Earnings() {
  const { user, refresh } = useSession();
  const router = useRouter();
  const [earnings, setEarnings] = useState<EarningsPayload | null>(null);
  const [crossSell, setCrossSell] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [e, c] = await Promise.allSettled([
        api('/earnings'),
        api('/store/cross-sell'),
      ]);
      if (e.status === 'fulfilled') setEarnings(e.value);
      if (c.status === 'fulfilled') setCrossSell(c.value);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([load(), refresh()]);
    setRefreshing(false);
  };

  if (!earnings) {
    return (
      <SafeAreaView style={styles.safe}><View style={styles.center}><ActivityIndicator color={colors.primary} size="large" /></View></SafeAreaView>
    );
  }

  const balanceBtc = earnings.indicative_balance_btc || 0;
  const balanceUsd = (earnings.btc_usd || 0) * balanceBtc;
  const balanceSats = Math.floor(balanceBtc * 100_000_000);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        <Text style={styles.title}>Earnings</Text>

        {/* Cross-sell banner */}
        <CrossSellBanner data={crossSell} />

        {/* Indicative balance */}
        <LinearGradient colors={['#16202C', '#0E1620']} style={styles.balanceCard}>
          <Image source={{ uri: media.cryptoCoin }} style={styles.coinBg} />
          <View style={styles.coinRow}>
            <Ionicons name="logo-bitcoin" size={28} color={colors.primary} />
            <Text style={styles.balanceLabel}>Indicative Earnings</Text>
          </View>
          <TickingBtc
            style={styles.balanceBtc}
            baseBtc={balanceBtc}
            ratePerSecondBtc={earnings.indicative_per_second_btc || 0}
            suffix=""
            testID="earnings-balance-tick"
          />
          <View style={styles.satsRow}>
            <Text style={styles.balanceUsd}>≈ {fmtUsd(balanceUsd)}</Text>
            <Text style={styles.balanceUsd}>{'  ·  '}</Text>
            <TickingBtc
              style={styles.balanceSats}
              baseBtc={balanceBtc}
              ratePerSecondBtc={earnings.indicative_per_second_btc || 0}
              decimals={4}
              unit="sats"
            />
          </View>
        </LinearGradient>

        {/* Redeem CTA */}
        <TouchableOpacity
          onPress={() => router.push('/redeem/network')}
          style={styles.redeemBtn}
          testID="redeem-cta"
        >
          <LinearGradient colors={['#00FFA3', '#00D1FF']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.redeemInner}>
            <Ionicons name="arrow-forward-circle" size={22} color={colors.bg} />
            <Text style={styles.redeemText}>Redeem</Text>
          </LinearGradient>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.recordsBtn}
          onPress={() => router.push('/transactions')}
          testID="redeem-records-btn"
        >
          <Text style={styles.recordsText}>Redeem Records  ››</Text>
        </TouchableOpacity>

        {/* Disclaimer (matches MeMiner screenshot wording) */}
        <View style={styles.disclaimer}>
          <Text style={styles.disclaimerText}>
            {earnings.disclaimer || 'Please be advised that this application itself does not hold or manage any on-chain assets; it is not a wallet, trading platform, or fund manager. Your assets are entirely controlled by your connected wallet address. All displayed earnings are estimations for your reference, and the final data is subject to server records.'}
          </Text>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: spacing.lg },
  title: { color: colors.text, fontSize: 28, fontWeight: '800', marginBottom: spacing.md },
  balanceCard: {
    borderRadius: radius.lg, padding: spacing.lg,
    borderWidth: 1, borderColor: colors.borderSoft,
    overflow: 'hidden', marginBottom: spacing.lg,
    alignItems: 'center',
    ...shadows.card,
  },
  coinBg: { position: 'absolute', right: -30, top: -10, width: 160, height: 160, opacity: 0.18 },
  coinRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm },
  balanceLabel: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  balanceBtc: { color: colors.text, fontFamily: fonts.mono, fontSize: 30, fontWeight: '800', letterSpacing: -0.5 },
  balanceUsd: { color: colors.textSecondary, fontSize: 12, fontFamily: fonts.mono },
  satsRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: 6, flexWrap: 'wrap', justifyContent: 'center' },
  balanceSats: { color: colors.primary, fontSize: 13, fontFamily: fonts.mono, fontWeight: '700' },
  redeemBtn: { borderRadius: radius.md, overflow: 'hidden', marginBottom: spacing.md, ...shadows.glow },
  redeemInner: { paddingVertical: 18, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  redeemText: { color: colors.bg, fontSize: 17, fontWeight: '900' },
  recordsBtn: { alignSelf: 'center', paddingVertical: 12, paddingHorizontal: 18 },
  recordsText: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  disclaimer: { padding: spacing.md, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, marginTop: spacing.lg },
  disclaimerText: { color: colors.textTertiary, fontSize: 11, lineHeight: 16 },
});
