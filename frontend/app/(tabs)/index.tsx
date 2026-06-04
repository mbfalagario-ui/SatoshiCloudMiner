import React, { useCallback, useEffect, useState, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  Image, Animated, Easing, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSession } from '@/src/ctx';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, media, shadows, fmtUsd, fmtGhs } from '@/src/utils/theme';
import CrossSellBanner from '@/src/components/CrossSellBanner';
import DailyCheckinCard from '@/src/components/DailyCheckinCard';
import WatchAdCard from '@/src/components/WatchAdCard';
import TickingBtc from '@/src/components/TickingBtc';

type EarningsPayload = {
  indicative_balance_btc: number;
  lifetime_earnings_btc: number;
  hashrate: { total_ghs: number; pack_ghs: number; checkin_ghs: number; ad_ghs: number };
  indicative_daily_btc?: number;
  indicative_daily_usd?: number;
  indicative_per_second_btc?: number;
  payout_multiplier?: number;
  btc_usd?: number;
  disclaimer?: string;
  min_redeem_sats?: number;
};

export default function Home() {
  const { user, refresh } = useSession();
  const router = useRouter();
  const [earnings, setEarnings] = useState<EarningsPayload | null>(null);
  const [crossSell, setCrossSell] = useState<any>(null);
  const [ticker, setTicker] = useState<string>('');
  const [refreshing, setRefreshing] = useState(false);
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 1400, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 0, duration: 1400, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const load = useCallback(async () => {
    try {
      const [e, c, t] = await Promise.allSettled([
        api('/earnings'),
        api('/store/cross-sell'),
        api('/ai/ticker'),
      ]);
      if (e.status === 'fulfilled') setEarnings(e.value);
      if (c.status === 'fulfilled') setCrossSell(c.value);
      if (t.status === 'fulfilled') setTicker(t.value?.text || '');
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

  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 1] });
  const totalGhs = earnings.hashrate?.total_ghs || 0;
  const isMining = totalGhs > 0;
  const btcUsd = earnings.btc_usd || 0;
  const balanceBtc = earnings.indicative_balance_btc || 0;
  const ratePerSecBtc = earnings.indicative_per_second_btc || 0;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.hello}>Welcome back</Text>
            <Text style={styles.email} numberOfLines={1}>{user?.email}</Text>
          </View>
          <TouchableOpacity
            testID="home-support-btn"
            onPress={() => router.push('/support')}
            style={styles.iconBtn}
          >
            <Ionicons name="chatbubble-ellipses" size={20} color={colors.primary} />
          </TouchableOpacity>
        </View>

        {/* Dynamic cross-sell banner */}
        <CrossSellBanner data={crossSell} />

        {/* ===== UNIFIED HERO CARD: Earnings + Hashrate ===== */}
        <LinearGradient
          colors={['#16202C', '#0E1620']}
          style={styles.heroCard}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Image source={{ uri: media.cryptoCoin }} style={styles.coinBg} />

          {/* top row: label + mining status pill */}
          <View style={styles.heroTopRow}>
            <Text style={styles.cardLabel}>INDICATIVE EARNINGS</Text>
            <View style={[styles.statusPill, !isMining && styles.statusPillIdle]}>
              <Animated.View style={[
                styles.statusDot,
                { backgroundColor: isMining ? colors.primary : colors.textTertiary },
                isMining && { opacity: pulseOpacity },
              ]} />
              <Text style={[styles.statusText, !isMining && styles.statusTextIdle]}>
                {isMining ? 'ACTIVE' : 'IDLE'}
              </Text>
            </View>
          </View>

          {/* hero metric: live-ticking sats */}
          <TickingBtc
            style={styles.heroSats}
            baseBtc={balanceBtc}
            ratePerSecondBtc={ratePerSecBtc}
            decimals={2}
            unit="sats"
            testID="home-balance-sats"
          />

          {/* secondary line: 8-decimal BTC · USD */}
          <View style={styles.secondaryRow}>
            <TickingBtc
              style={styles.secondaryBtc}
              baseBtc={balanceBtc}
              ratePerSecondBtc={ratePerSecBtc}
              decimals={8}
              unit="BTC"
              testID="home-balance-btc"
            />
            <Text style={styles.secondaryDot}> · </Text>
            <Text style={styles.secondaryUsd} testID="home-balance-usd">
              {fmtUsd(balanceBtc * btcUsd)}
            </Text>
          </View>

          {/* embedded hashrate panel */}
          <View style={styles.hashPanel}>
            <View style={styles.hashHeaderRow}>
              <View style={styles.hashHeaderLeft}>
                <Ionicons name="speedometer" size={14} color={colors.primary} />
                <Text style={styles.hashHeaderLabel}>ACTIVE HASHPOWER</Text>
              </View>
              <Text style={styles.hashTotalValue} testID="home-hash-rate">
                {fmtGhs(totalGhs)}
              </Text>
            </View>

            <View style={styles.hashCells}>
              <HashCell label="Plans" value={fmtGhs(earnings.hashrate?.pack_ghs || 0)} icon="layers" />
              <View style={styles.hashDivider} />
              <HashCell label="Check-in" value={fmtGhs(earnings.hashrate?.checkin_ghs || 0)} icon="calendar" />
              <View style={styles.hashDivider} />
              <HashCell label="Ads" value={fmtGhs(earnings.hashrate?.ad_ghs || 0)} icon="play" />
            </View>
          </View>

          {/* CTA */}
          <TouchableOpacity
            testID="home-go-store"
            onPress={() => router.push('/(tabs)/shop')}
            style={styles.boostBtn}
            activeOpacity={0.85}
          >
            <Ionicons name="flash" size={16} color={colors.bg} />
            <Text style={styles.boostBtnText}>Boost in Store</Text>
            <Ionicons name="arrow-forward" size={16} color={colors.bg} />
          </TouchableOpacity>
        </LinearGradient>

        {/* Daily check-in */}
        <DailyCheckinCard onClaim={load} />

        {/* Watch ad */}
        <WatchAdCard onClaim={load} />

        {/* Ticker */}
        {ticker ? (
          <View style={styles.tickerCard}>
            <Ionicons name="sparkles" size={14} color={colors.primary} />
            <Text style={styles.tickerText} numberOfLines={2}>{ticker}</Text>
          </View>
        ) : null}

        {/* Disclaimer */}
        <View style={styles.disclaimer}>
          <Ionicons name="information-circle" size={14} color={colors.textTertiary} />
          <Text style={styles.disclaimerText}>
            {earnings.disclaimer || 'Earnings are indicative and depend on real network hashrate. This app does not hold or manage on-chain assets; your wallet remains in your sole control.'}
          </Text>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function HashCell({ label, value, icon }: { label: string; value: string; icon: any }) {
  return (
    <View style={styles.hashCell}>
      <View style={styles.hashCellHeader}>
        <Ionicons name={icon} size={11} color={colors.textSecondary} />
        <Text style={styles.hashCellLabel}>{label}</Text>
      </View>
      <Text style={styles.hashCellValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  hello: { color: colors.textSecondary, fontSize: 13 },
  email: { color: colors.text, fontSize: 16, fontWeight: '700', maxWidth: 220 },
  iconBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },

  // === Hero Card ===
  heroCard: {
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    overflow: 'hidden',
    marginBottom: spacing.md,
    ...shadows.card,
  },
  coinBg: {
    position: 'absolute',
    right: -40,
    top: -20,
    width: 180,
    height: 180,
    opacity: 0.18,
  },
  heroTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.4,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: 'rgba(0,255,163,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(0,255,163,0.35)',
  },
  statusPillIdle: {
    backgroundColor: 'rgba(120,120,120,0.10)',
    borderColor: colors.borderSoft,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusText: { color: colors.primary, fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  statusTextIdle: { color: colors.textTertiary },

  // === Hero metric: live-ticking sats ===
  heroSats: {
    color: colors.primary,
    fontFamily: fonts.mono,
    fontSize: 42,
    fontWeight: '900',
    letterSpacing: -1,
    marginTop: spacing.md,
  },

  // === Secondary line: BTC · USD ===
  secondaryRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 4,
    flexWrap: 'wrap',
  },
  secondaryBtc: {
    color: colors.textSecondary,
    fontFamily: fonts.mono,
    fontSize: 13,
    fontWeight: '600',
  },
  secondaryDot: { color: colors.textTertiary, fontSize: 13 },
  secondaryUsd: {
    color: colors.textSecondary,
    fontFamily: fonts.mono,
    fontSize: 13,
    fontWeight: '600',
  },

  // === Embedded hashrate panel ===
  hashPanel: {
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderSoft,
  },
  hashHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  hashHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  hashHeaderLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.2,
  },
  hashTotalValue: {
    color: colors.text,
    fontFamily: fonts.mono,
    fontSize: 15,
    fontWeight: '800',
  },
  hashCells: {
    flexDirection: 'row',
    marginTop: spacing.md,
  },
  hashCell: { flex: 1, alignItems: 'center', gap: 4 },
  hashCellHeader: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  hashCellLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '600' },
  hashCellValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '700',
    fontFamily: fonts.mono,
  },
  hashDivider: { width: 1, backgroundColor: colors.borderSoft },

  // === CTA ===
  boostBtn: {
    marginTop: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: radius.md,
    ...shadows.glow,
  },
  boostBtnText: {
    color: colors.bg,
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.3,
  },

  // === Ticker / Disclaimer ===
  tickerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    marginBottom: spacing.md,
  },
  tickerText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 16 },
  disclaimer: {
    flexDirection: 'row',
    gap: 6,
    padding: spacing.sm,
    alignItems: 'flex-start',
  },
  disclaimerText: { flex: 1, color: colors.textTertiary, fontSize: 10, lineHeight: 14 },
});
