import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  Image, Animated, Easing, ActivityIndicator,
} from 'react-native';
import { useRef } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSession } from '@/src/ctx';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, media, shadows, fmtUsd, fmtBtc, fmtGhs } from '@/src/utils/theme';
import CrossSellBanner from '@/src/components/CrossSellBanner';
import DailyCheckinCard from '@/src/components/DailyCheckinCard';
import WatchAdCard from '@/src/components/WatchAdCard';
import HashrateBreakdown from '@/src/components/HashrateBreakdown';

type EarningsPayload = {
  indicative_balance_btc: number;
  lifetime_earnings_btc: number;
  hashrate: { total_ghs: number; pack_ghs: number; checkin_ghs: number; ad_ghs: number };
  indicative_daily_btc?: number;
  indicative_daily_usd?: number;
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

  const pulseScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] });
  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.4, 0.9] });
  const totalGhs = earnings.hashrate?.total_ghs || 0;
  const isMining = totalGhs > 0;

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
          <View>
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

        {/* Indicative Earnings card */}
        <LinearGradient colors={['#16202C', '#0E1620']} style={styles.balanceCard} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
          <Image source={{ uri: media.cryptoCoin }} style={styles.coinBg} />
          <Text style={styles.cardLabel}>INDICATIVE EARNINGS</Text>
          <Text style={styles.balanceBtc} testID="home-balance-btc">{fmtBtc(earnings.indicative_balance_btc)} BTC</Text>
          <Text style={styles.balanceUsd} testID="home-balance-usd">{fmtUsd(earnings.indicative_balance_btc * (earnings.btc_usd || 0))}</Text>
          <View style={styles.balanceRow}>
            <View style={styles.balanceCell}>
              <Text style={styles.cellLabel}>Daily est.</Text>
              <Text style={styles.cellValue}>{fmtBtc(earnings.indicative_daily_btc || 0)} BTC</Text>
            </View>
            <View style={styles.balanceDivider} />
            <TouchableOpacity style={styles.balanceCell} onPress={() => router.push('/(tabs)/wallet')}>
              <Text style={styles.cellLabel}>Redeem</Text>
              <Text style={[styles.cellValue, { color: colors.primary }]}>Tap ›</Text>
            </TouchableOpacity>
          </View>
        </LinearGradient>

        {/* Daily check-in */}
        <DailyCheckinCard onClaim={load} />

        {/* Watch ad */}
        <WatchAdCard onClaim={load} />

        {/* Hashrate breakdown */}
        <HashrateBreakdown data={earnings.hashrate} />

        {/* Mining card */}
        <View style={styles.miningCard}>
          <View style={{ flex: 1 }}>
            <View style={styles.miningHeader}>
              <View style={[styles.statusDot, { backgroundColor: isMining ? colors.primary : colors.textTertiary }]} />
              <Text style={styles.miningStatus}>{isMining ? 'MINING ACTIVE' : 'IDLE'}</Text>
            </View>
            <Text style={styles.hashRate} testID="home-hash-rate">{fmtGhs(totalGhs)}</Text>
            <Text style={styles.hashUnit}>Virtual cloud hashpower</Text>
            <TouchableOpacity testID="home-go-store" onPress={() => router.push('/(tabs)/shop')} style={styles.viewBtn}>
              <Text style={styles.viewBtnText}>Boost in Store</Text>
              <Ionicons name="arrow-forward" size={14} color={colors.primary} />
            </TouchableOpacity>
          </View>
          <View style={styles.rigWrap}>
            <Animated.View style={[styles.pulseRing, { transform: [{ scale: pulseScale }], opacity: pulseOpacity }]} />
            <Image source={{ uri: media.miningHardware }} style={styles.rig} />
          </View>
        </View>

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

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md },
  hello: { color: colors.textSecondary, fontSize: 13 },
  email: { color: colors.text, fontSize: 16, fontWeight: '700', maxWidth: 220 },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  balanceCard: { borderRadius: radius.lg, padding: spacing.lg, borderWidth: 1, borderColor: colors.borderSoft, overflow: 'hidden', marginBottom: spacing.md, ...shadows.card },
  coinBg: { position: 'absolute', right: -30, top: -10, width: 160, height: 160, opacity: 0.3 },
  cardLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 1.4 },
  balanceUsd: { color: colors.textSecondary, fontFamily: fonts.mono, fontSize: 14, fontWeight: '600', marginTop: 2 },
  balanceBtc: { color: colors.primary, fontFamily: fonts.mono, fontSize: 32, fontWeight: '800', marginTop: spacing.sm, letterSpacing: -0.5 },
  balanceRow: { flexDirection: 'row', marginTop: spacing.lg, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  balanceCell: { flex: 1 },
  balanceDivider: { width: 1, backgroundColor: colors.borderSoft, marginHorizontal: spacing.sm },
  cellLabel: { color: colors.textTertiary, fontSize: 11, fontWeight: '600', letterSpacing: 0.8 },
  cellValue: { color: colors.text, fontFamily: fonts.mono, fontSize: 14, fontWeight: '700', marginTop: 2 },
  miningCard: { flexDirection: 'row', backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.md, borderWidth: 1, borderColor: colors.borderSoft, marginBottom: spacing.md, overflow: 'hidden' },
  miningHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  miningStatus: { color: colors.textSecondary, fontSize: 10, fontWeight: '700', letterSpacing: 1.4 },
  hashRate: { color: colors.primary, fontFamily: fonts.mono, fontSize: 30, fontWeight: '800', marginTop: 4, letterSpacing: -1 },
  hashUnit: { color: colors.textSecondary, fontSize: 11, fontWeight: '600' },
  viewBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.md },
  viewBtnText: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  rigWrap: { width: 110, height: 110, justifyContent: 'center', alignItems: 'center' },
  pulseRing: { position: 'absolute', width: 110, height: 110, borderRadius: 55, backgroundColor: colors.primaryGlow },
  rig: { width: 100, height: 100, resizeMode: 'contain' },
  tickerCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft, paddingHorizontal: spacing.md, paddingVertical: 10, marginBottom: spacing.md },
  tickerText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 16 },
  disclaimer: { flexDirection: 'row', gap: 6, padding: spacing.sm, alignItems: 'flex-start' },
  disclaimerText: { flex: 1, color: colors.textTertiary, fontSize: 10, lineHeight: 14 },
});
