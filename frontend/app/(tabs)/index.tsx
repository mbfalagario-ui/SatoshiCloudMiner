import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Image,
  Animated,
  Easing,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSession } from '@/src/ctx';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, media, shadows, fmtUsd, fmtBtc, fmtHash } from '@/src/utils/theme';

type Machine = {
  id: string;
  name: string;
  hash_rate: number;
  daily_yield_usd: number;
  expires_at: string;
  status: string;
};

type Dashboard = {
  user: { balance_btc: number; balance_usd: number; lifetime_btc: number; lifetime_usd: number };
  hash_rate: number;
  active_machines_count: number;
  today_earnings_usd: number;
  today_earnings_btc: number;
  daily_projected_usd: number;
  active_machines: Machine[];
};

export default function Home() {
  const { user, refresh } = useSession();
  const router = useRouter();
  const [data, setData] = useState<Dashboard | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [liveBalance, setLiveBalance] = useState(0);
  const [ticker, setTicker] = useState<string>('');
  const [agents, setAgents] = useState<any[]>([]);

  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1400, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1400, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const load = useCallback(async () => {
    try {
      const [d, t, a] = await Promise.allSettled([
        api('/dashboard'),
        api('/ai/ticker'),
        api('/ai/agents'),
      ]);
      if (d.status === 'fulfilled') {
        setData(d.value);
        setLiveBalance(d.value.user.balance_usd);
      }
      if (t.status === 'fulfilled') setTicker(t.value?.text || '');
      if (a.status === 'fulfilled') setAgents(a.value?.agents || []);
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Ticking live earnings every second (visual only)
  useEffect(() => {
    if (!data || data.daily_projected_usd <= 0) return;
    const perSec = data.daily_projected_usd / 86400;
    const t = setInterval(() => {
      setLiveBalance((b) => b + perSec);
    }, 1000);
    return () => clearInterval(t);
  }, [data]);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([load(), refresh()]);
    setRefreshing(false);
  };

  if (!data) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  const pulseScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] });
  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.4, 0.9] });

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.hello}>Welcome back</Text>
            <Text style={styles.email} numberOfLines={1}>{user?.email}</Text>
          </View>
          <TouchableOpacity
            testID="home-daily-btn"
            onPress={() => router.push('/daily')}
            style={styles.iconBtn}
          >
            <Ionicons name="gift-outline" size={22} color={colors.primary} />
          </TouchableOpacity>
        </View>

        {/* Balance Card */}
        <LinearGradient
          colors={['#16202C', '#0E1620']}
          style={styles.balanceCard}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Image source={{ uri: media.cryptoCoin }} style={styles.coinBg} />
          <Text style={styles.cardLabel}>TOTAL BALANCE</Text>
          <Text style={styles.balanceUsd} testID="home-balance-usd">
            {fmtUsd(liveBalance)}
          </Text>
          <Text style={styles.balanceBtc} testID="home-balance-btc">
            ₿ {fmtBtc(liveBalance / 65000)}
          </Text>
          <View style={styles.balanceRow}>
            <View style={styles.balanceCell}>
              <Text style={styles.cellLabel}>Today</Text>
              <Text style={styles.cellValue} testID="home-today">
                {fmtUsd(data.today_earnings_usd)}
              </Text>
            </View>
            <View style={styles.balanceDivider} />
            <View style={styles.balanceCell}>
              <Text style={styles.cellLabel}>Lifetime</Text>
              <Text style={styles.cellValue} testID="home-lifetime">
                {fmtUsd(data.user.lifetime_usd)}
              </Text>
            </View>
          </View>
        </LinearGradient>

        {/* Active Mining Card */}
        <View style={styles.miningCard}>
          <View style={{ flex: 1 }}>
            <View style={styles.miningHeader}>
              <View style={[styles.statusDot, { backgroundColor: data.hash_rate > 0 ? colors.primary : colors.textTertiary }]} />
              <Text style={styles.miningStatus}>
                {data.hash_rate > 0 ? 'MINING ACTIVE' : 'IDLE'}
              </Text>
            </View>
            <Text style={styles.hashRate} testID="home-hash-rate">
              {data.hash_rate.toFixed(2)}
            </Text>
            <Text style={styles.hashUnit}>TH/s · Cloud hashpower</Text>
            <Text style={styles.miningMeta}>
              {data.active_machines_count} active miner{data.active_machines_count === 1 ? '' : 's'}
            </Text>
            <TouchableOpacity
              testID="home-view-miners-btn"
              onPress={() => router.push('/machines')}
              style={styles.viewBtn}
            >
              <Text style={styles.viewBtnText}>View miners</Text>
              <Ionicons name="arrow-forward" size={14} color={colors.primary} />
            </TouchableOpacity>
          </View>
          <View style={styles.rigWrap}>
            <Animated.View
              style={[
                styles.pulseRing,
                { transform: [{ scale: pulseScale }], opacity: pulseOpacity },
              ]}
            />
            <Image source={{ uri: media.miningHardware }} style={styles.rig} />
          </View>
        </View>

        {/* Quick Stats */}
        <View style={styles.statsGrid}>
          <Stat icon="trending-up" label="Daily projected" value={fmtUsd(data.daily_projected_usd)} />
          <Stat icon="time" label="Updated" value="Live" highlight />
        </View>

        {/* AI market ticker */}
        {ticker ? (
          <View style={styles.tickerCard} testID="ai-ticker">
            <Ionicons name="sparkles" size={14} color={colors.primary} />
            <Text style={styles.tickerText} numberOfLines={2}>{ticker}</Text>
          </View>
        ) : null}

        {/* AI Trading Agents */}
        {agents.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>AI Trading Agents</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm, paddingRight: spacing.lg }}>
              {agents.map((a) => (
                <View key={a.id} style={styles.agentCard} testID={`agent-${a.id}`}>
                  <View style={styles.agentTop}>
                    <View style={[styles.agentDot, { backgroundColor: a.signal_strength === 'high' ? colors.primary : a.signal_strength === 'medium' ? colors.warning : colors.textTertiary }]} />
                    <Text style={styles.agentN}>{a.name}</Text>
                  </View>
                  <Text style={styles.agentS}>{a.strategy}</Text>
                  <View style={styles.agentBottom}>
                    <Text style={[styles.agentP, { color: a.daily_pct >= 0 ? colors.primary : colors.warning }]}>
                      {a.daily_pct >= 0 ? '+' : ''}{(a.daily_pct * 100).toFixed(2)}%
                    </Text>
                    <Text style={styles.agentW}>{(a.win_rate * 100).toFixed(0)}% wr</Text>
                  </View>
                </View>
              ))}
            </ScrollView>
          </>
        ) : null}

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick actions</Text>
        <View style={styles.actionsRow}>
          <Action
            testID="home-action-shop"
            icon="hardware-chip"
            label="Buy power"
            onPress={() => router.push('/(tabs)/shop')}
          />
          <Action
            testID="home-action-withdraw"
            icon="wallet"
            label="Withdraw"
            onPress={() => router.push('/(tabs)/wallet')}
          />
          <Action
            testID="home-action-refer"
            icon="people"
            label="Invite"
            onPress={() => router.push('/referral')}
          />
          <Action
            testID="home-action-tx"
            icon="time"
            label="History"
            onPress={() => router.push('/transactions')}
          />
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Stat({ icon, label, value, highlight }: any) {
  return (
    <View style={[styles.statCard, highlight && { borderColor: colors.primaryDim }]}>
      <Ionicons name={icon} size={18} color={highlight ? colors.primary : colors.textSecondary} />
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, highlight && { color: colors.primary }]}>{value}</Text>
    </View>
  );
}

function Action({ icon, label, onPress, testID }: any) {
  return (
    <TouchableOpacity testID={testID} style={styles.action} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.actionIcon}>
        <Ionicons name={icon} size={20} color={colors.primary} />
      </View>
      <Text style={styles.actionLabel}>{label}</Text>
    </TouchableOpacity>
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
  balanceCard: {
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
    right: -30,
    top: -10,
    width: 160,
    height: 160,
    opacity: 0.3,
  },
  cardLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.4,
  },
  balanceUsd: {
    color: colors.text,
    fontFamily: fonts.mono,
    fontSize: 44,
    fontWeight: '700',
    letterSpacing: -1.5,
    marginTop: spacing.sm,
  },
  balanceBtc: {
    color: colors.primary,
    fontFamily: fonts.mono,
    fontSize: 14,
    fontWeight: '600',
    marginTop: 4,
  },
  balanceRow: {
    flexDirection: 'row',
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderSoft,
  },
  balanceCell: { flex: 1 },
  balanceDivider: { width: 1, backgroundColor: colors.borderSoft, marginHorizontal: spacing.sm },
  cellLabel: { color: colors.textTertiary, fontSize: 11, fontWeight: '600', letterSpacing: 0.8 },
  cellValue: {
    color: colors.text,
    fontFamily: fonts.mono,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 2,
  },
  miningCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  miningHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  miningStatus: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.4,
  },
  hashRate: {
    color: colors.primary,
    fontFamily: fonts.mono,
    fontSize: 36,
    fontWeight: '800',
    marginTop: 4,
    letterSpacing: -1,
  },
  hashUnit: { color: colors.textSecondary, fontSize: 11, fontWeight: '600' },
  miningMeta: { color: colors.textSecondary, fontSize: 12, marginTop: spacing.sm },
  viewBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.md },
  viewBtnText: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  rigWrap: { width: 110, height: 110, justifyContent: 'center', alignItems: 'center' },
  pulseRing: {
    position: 'absolute',
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: colors.primaryGlow,
  },
  rig: { width: 100, height: 100, resizeMode: 'contain' },
  statsGrid: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  statCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: 4,
  },
  statLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '600' },
  statValue: { color: colors.text, fontSize: 16, fontWeight: '800', fontFamily: fonts.mono },
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
  agentCard: {
    width: 170,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.md,
    gap: 6,
  },
  agentTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  agentDot: { width: 8, height: 8, borderRadius: 4 },
  agentN: { color: colors.text, fontSize: 14, fontWeight: '800', letterSpacing: -0.2 },
  agentS: { color: colors.textSecondary, fontSize: 11 },
  agentBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 },
  agentP: { fontSize: 16, fontWeight: '800', fontFamily: fonts.mono },
  agentW: { color: colors.textTertiary, fontSize: 10, fontFamily: fonts.mono },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  actionsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  action: { flex: 1, alignItems: 'center', gap: 6 },
  actionIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionLabel: { color: colors.text, fontSize: 12, fontWeight: '600' },
});
