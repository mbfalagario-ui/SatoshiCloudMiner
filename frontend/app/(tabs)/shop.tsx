import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, RefreshControl,
  ActivityIndicator, Alert, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useFocusEffect } from 'expo-router';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, radius, spacing, fonts, fmtUsd, fmtGhs } from '@/src/utils/theme';
import CrossSellBanner from '@/src/components/CrossSellBanner';
import { buyProduct, isIapAvailable, restorePurchases } from '@/src/utils/iap';

type Pkg = {
  id: string;
  name: string;
  tagline?: string;
  offer_text?: string | null;
  price_usd: number;
  original_price_usd: number;
  hashrate_boost_ghs: number;
  duration_hours: number;
  badge?: string | null;
  first_purchase_bonus_pct: number;
  hashrate_display: string;
  duration_label: string;
  entitlement?: string;
};

export default function Store() {
  const { user, refresh } = useSession();
  const params = useLocalSearchParams<{ focus?: string }>();
  const [packages, setPackages] = useState<Pkg[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [crossSell, setCrossSell] = useState<any>(null);
  const [earnings, setEarnings] = useState<any>(null);
  const [consumed, setConsumed] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const [pk, cs, e] = await Promise.allSettled([
        api('/packages'),
        api('/store/cross-sell'),
        api('/earnings'),
      ]);
      if (pk.status === 'fulfilled') {
        const all = (pk.value?.packages || []) as Pkg[];
        setPackages(all.filter((p) => p.id !== 'adfree_399'));
        const adFreePkg = all.find((p) => p.id === 'adfree_399');
        if (adFreePkg) setPackages((prev) => [...prev, adFreePkg]);
      }
      if (cs.status === 'fulfilled') setCrossSell(cs.value);
      if (e.status === 'fulfilled') setEarnings(e.value);
      setConsumed((user as any)?.purchased_sku_bonuses || []);
    } catch {}
  }, [user]);

  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  useEffect(() => {
    if (params.focus && packages.length > 0) {
      const target = packages.find((p) => p.id === params.focus);
      if (target) setSelectedId(target.id);
    } else if (!selectedId && packages.length > 0) {
      const popular = packages.find((p) => p.badge === 'POPULAR') || packages[2] || packages[0];
      setSelectedId(popular.id);
    }
  }, [packages, params.focus, selectedId]);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([load(), refresh()]);
    setRefreshing(false);
  };

  const buy = async (pkg: Pkg) => {
    if (busy) return;
    setBusy(true);
    try {
      // ───────────────────────────────────────────────────────────
      // Apple Guideline 2.1(b): all paid digital content MUST go
      // through StoreKit. On iOS we ALWAYS open the native sheet
      // first and only call the backend with the resulting
      // transactionId. The backend rejects /packages/buy on iOS
      // unless apple_transaction_id is present.
      // ───────────────────────────────────────────────────────────
      let appleTransactionId: string | undefined;
      if (Platform.OS === 'ios') {
        if (!isIapAvailable()) {
          Alert.alert(
            'In-App Purchases unavailable',
            'Apple In-App Purchases are not available on this device. Please ensure you are signed in to the App Store and try again.',
          );
          return;
        }
        const result = await buyProduct(pkg.id);
        if (!result.applePurchase || !result.transactionId) {
          // StoreKit closed without a successful purchase (user
          // cancelled, network error, payment declined). Do NOT
          // call the backend.
          return;
        }
        appleTransactionId = result.transactionId;
      }

      const r = await api('/packages/buy', {
        method: 'POST',
        body: JSON.stringify({
          package_id: pkg.id,
          apple_transaction_id: appleTransactionId,
        }),
      });
      const bonusMsg = r.first_purchase_bonus_applied
        ? `\n\nFirst-time bonus +${r.bonus_pct}% applied (+${r.bonus_ghs?.toFixed?.(1)} GH/s)`
        : '';
      Alert.alert('Purchase successful', `${pkg.name} is now active.${bonusMsg}`);
      await load();
      await refresh();
    } catch (e: any) {
      const msg = e?.message || 'Try again later';
      // Don't show the alert if the user cancelled the StoreKit sheet
      const isCancellation =
        /cancel/i.test(msg) ||
        /E_USER_CANCELLED/i.test(msg) ||
        /SKErrorPaymentCancelled/i.test(msg);
      if (!isCancellation) {
        Alert.alert('Purchase failed', msg);
      }
    } finally {
      setBusy(false);
    }
  };

  const selected = useMemo(() => packages.find((p) => p.id === selectedId), [packages, selectedId]);
  const totalGhs = earnings?.hashrate?.total_ghs || 0;

  // Apple Guideline 3.1.1 — explicit user-initiated Restore Purchases.
  // Tap → fetches every entitlement on this Apple ID via StoreKit, forwards
  // to /api/iap/restore which verifies each with Apple's Server API and
  // idempotently re-grants whatever this user is missing.
  const onRestore = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (Platform.OS !== 'ios') {
        Alert.alert('Restore Purchases', 'Apple In-App Purchase restore is only available on iOS devices.');
        return;
      }
      if (!isIapAvailable()) {
        Alert.alert('Restore Purchases', 'Apple In-App Purchase is not available on this device. Make sure you are signed in to the App Store.');
        return;
      }
      const items = await restorePurchases();
      if (items.length === 0) {
        Alert.alert('Nothing to restore', 'There are no previous purchases on this Apple ID for Hashrate Cloud Miner.');
        return;
      }
      const r = await api('/iap/restore', {
        method: 'POST',
        body: JSON.stringify({
          purchases: items.map((i) => ({ transaction_id: i.transactionId, product_id: i.productId })),
        }),
      });
      const restored = (r?.restored || []).length;
      const skipped = (r?.skipped || []).length;
      const errs = (r?.errors || []).length;
      const parts: string[] = [];
      if (restored > 0) parts.push(`${restored} restored`);
      if (skipped > 0) parts.push(`${skipped} already owned`);
      if (errs > 0) parts.push(`${errs} error${errs === 1 ? '' : 's'}`);
      Alert.alert(
        restored > 0 ? 'Purchases restored' : 'Restore complete',
        parts.join(' · ') || 'No new purchases were restored.',
      );
      await load();
      await refresh();
    } catch (e: any) {
      const msg = e?.message || 'Restore failed. Please try again.';
      Alert.alert('Restore failed', msg);
    } finally {
      setBusy(false);
    }
  };

  if (packages.length === 0) {
    return (
      <SafeAreaView style={styles.safe}><View style={styles.center}><ActivityIndicator color={colors.primary} size="large" /></View></SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        <View style={styles.titleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Store</Text>
            <Text style={styles.subtitle}>Boost hashrate · First purchase gets free GH/s</Text>
          </View>
          {Platform.OS === 'ios' ? (
            <TouchableOpacity
              testID="restore-purchases-btn"
              onPress={onRestore}
              disabled={busy}
              style={styles.restoreBtn}
              activeOpacity={0.7}
            >
              <Ionicons name="refresh" size={14} color={colors.primary} />
              <Text style={styles.restoreBtnText}>Restore</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        <CrossSellBanner data={crossSell} />

        {/* Active Computing Power */}
        <View style={styles.activeCard}>
          <View style={{ flex: 1 }}>
            <Text style={styles.activeLabel}>Active Computing Power</Text>
            <Text style={styles.activeValue}>{fmtGhs(totalGhs)}</Text>
          </View>
          {selected ? (
            <View style={styles.activeBoost}>
              <Text style={styles.boostLabel}>+ if you buy</Text>
              <Text style={styles.boostValue}>{fmtGhs(selected.hashrate_boost_ghs)}</Text>
            </View>
          ) : null}
        </View>

        {/* Plan selector pills (mining only, no adfree) */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.pillRow}
          style={styles.pillScroll}
        >
          {packages.filter((p) => !p.entitlement).map((p) => {
            const isSel = p.id === selectedId;
            return (
              <TouchableOpacity
                key={p.id}
                onPress={() => setSelectedId(p.id)}
                style={[styles.pill, isSel && styles.pillActive]}
                testID={`pill-${p.id}`}
              >
                <Text style={[styles.pillText, isSel && styles.pillTextActive]}>{p.hashrate_display}</Text>
                {p.first_purchase_bonus_pct > 0 && !consumed.includes(p.id) ? (
                  <View style={styles.pillBadge}><Text style={styles.pillBadgeText}>+{p.first_purchase_bonus_pct}%</Text></View>
                ) : null}
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Selected plan detail card */}
        {selected && !selected.entitlement ? (
          <PlanCard pkg={selected} alreadyBonusUsed={consumed.includes(selected.id)} onBuy={() => buy(selected)} busy={busy} />
        ) : null}

        {/* Ad-Free upgrade card */}
        {packages.find((p) => p.entitlement === 'ad_free') ? (
          <AdFreeCard pkg={packages.find((p) => p.entitlement === 'ad_free')!} onBuy={buy} busy={busy} alreadyOwned={!!user?.ad_free} />
        ) : null}

        <View style={styles.disclaimer}>
          <Ionicons name="shield-checkmark" size={14} color={colors.textTertiary} />
          <Text style={styles.disclaimerText}>
            Boost packs are one-time purchases that permanently increase your virtual hashpower credit. Earnings are indicative based on live network hashrate and operator settings. This app does not hold, manage, or custody on-chain assets. Withdrawals route to a Lightning address you control.
          </Text>
        </View>
        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function PlanCard({ pkg, alreadyBonusUsed, onBuy, busy }: { pkg: Pkg; alreadyBonusUsed: boolean; onBuy: () => void; busy: boolean }) {
  const bonusActive = pkg.first_purchase_bonus_pct > 0 && !alreadyBonusUsed;
  const bonusGhs = bonusActive ? (pkg.hashrate_boost_ghs * pkg.first_purchase_bonus_pct) / 100 : 0;
  return (
    <LinearGradient colors={['#16202C', '#0E1620']} style={styles.detailCard}>
      {pkg.offer_text ? (
        <View style={styles.offerPill}>
          <Ionicons name="pricetag" size={11} color="#FF7A00" />
          <Text style={styles.offerText}>{pkg.offer_text}</Text>
        </View>
      ) : null}
      <View style={styles.bonusRow}>
        <Text style={styles.bonusLabel}>Free Computing Power</Text>
        <Text style={[styles.bonusValue, !bonusActive && { color: colors.textTertiary }]}>
          {bonusActive ? `+${pkg.first_purchase_bonus_pct}.0%` : 'Used'}
        </Text>
      </View>
      <View style={styles.gainRow}>
        <Text style={styles.gainLabel}>Gain</Text>
        <View style={styles.gainValueRow}>
          <Text style={styles.gainValue}>{fmtGhs(pkg.hashrate_boost_ghs)}</Text>
          {bonusActive ? (
            <Text style={styles.gainBonus}> + {fmtGhs(bonusGhs)}</Text>
          ) : null}
        </View>
      </View>
      <Text style={styles.durationMeta}>
        {pkg.duration_label === 'permanent' ? 'Permanent hashpower credit' : `Active for ${pkg.duration_label}`}
      </Text>
      <TouchableOpacity
        disabled={busy}
        onPress={onBuy}
        style={styles.cta}
        testID={`buy-${pkg.id}`}
      >
        <LinearGradient colors={['#00FFA3', '#00D1FF']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.ctaInner}>
          <Text style={styles.ctaText}>Pay {fmtUsd(pkg.price_usd)}</Text>
          <Text style={styles.ctaStrike}>{fmtUsd(pkg.original_price_usd)}</Text>
        </LinearGradient>
      </TouchableOpacity>
    </LinearGradient>
  );
}

function AdFreeCard({ pkg, onBuy, busy, alreadyOwned }: { pkg: Pkg; onBuy: (p: Pkg) => void; busy: boolean; alreadyOwned: boolean }) {
  return (
    <View style={styles.adFreeCard}>
      <View style={styles.adFreeIcon}>
        <Ionicons name="shield" size={24} color={colors.secondary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.adFreeTitle}>{pkg.name}</Text>
        <Text style={styles.adFreeSub}>Remove interstitial ads · Priority support</Text>
      </View>
      <TouchableOpacity
        disabled={busy || alreadyOwned}
        onPress={() => onBuy(pkg)}
        style={[styles.adFreeBtn, alreadyOwned && styles.adFreeBtnOwned]}
        testID="buy-adfree"
      >
        <Text style={styles.adFreeBtnText}>{alreadyOwned ? 'Active' : fmtUsd(pkg.price_usd)}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: spacing.lg },
  title: { color: colors.text, fontSize: 28, fontWeight: '800' },
  subtitle: { color: colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: spacing.md },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  restoreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary + '66',
    backgroundColor: colors.primary + '14',
    marginTop: 6,
  },
  restoreBtnText: { color: colors.primary, fontSize: 12, fontWeight: '700' },
  activeCard: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.md,
    borderWidth: 1, borderColor: colors.borderSoft, marginBottom: spacing.md,
  },
  activeLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  activeValue: { color: colors.text, fontSize: 28, fontWeight: '800', fontFamily: fonts.mono, marginTop: 2 },
  activeBoost: { alignItems: 'flex-end' },
  boostLabel: { color: colors.primary, fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  boostValue: { color: colors.primary, fontSize: 18, fontWeight: '800', fontFamily: fonts.mono, marginTop: 2 },
  pillScroll: { marginBottom: spacing.md },
  pillRow: { gap: 8, paddingRight: spacing.lg },
  pill: {
    backgroundColor: colors.surface,
    paddingHorizontal: 14, paddingVertical: 10,
    borderRadius: 22,
    borderWidth: 1, borderColor: colors.borderSoft,
    flexDirection: 'row', alignItems: 'center', gap: 8,
  },
  pillActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  pillText: { color: colors.textSecondary, fontSize: 13, fontWeight: '800', fontFamily: fonts.mono },
  pillTextActive: { color: colors.bg },
  pillBadge: { backgroundColor: 'rgba(0,0,0,0.15)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  pillBadgeText: { color: '#0B0E14', fontSize: 10, fontWeight: '800' },
  detailCard: {
    borderRadius: radius.lg, padding: spacing.lg,
    borderWidth: 1, borderColor: colors.borderSoft,
    marginBottom: spacing.md,
  },
  offerPill: {
    alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,122,0,0.15)',
    borderWidth: 1, borderColor: 'rgba(255,122,0,0.45)',
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12,
    marginBottom: spacing.md,
  },
  offerText: { color: '#FF7A00', fontSize: 11, fontWeight: '800' },
  bonusRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  bonusLabel: { color: colors.textSecondary, fontSize: 13 },
  bonusValue: { color: colors.primary, fontSize: 18, fontWeight: '800', fontFamily: fonts.mono },
  gainRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  gainLabel: { color: colors.textSecondary, fontSize: 13 },
  gainValueRow: { flexDirection: 'row', alignItems: 'baseline' },
  gainValue: { color: colors.text, fontSize: 22, fontWeight: '800', fontFamily: fonts.mono },
  gainBonus: { color: colors.primary, fontSize: 14, fontWeight: '800', fontFamily: fonts.mono },
  durationMeta: { color: colors.textTertiary, fontSize: 11, marginTop: 4 },
  cta: { marginTop: spacing.md, borderRadius: radius.md, overflow: 'hidden' },
  ctaInner: { paddingVertical: 16, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 10 },
  ctaText: { color: colors.bg, fontSize: 16, fontWeight: '900' },
  ctaStrike: { color: 'rgba(0,0,0,0.5)', fontSize: 13, fontWeight: '700', textDecorationLine: 'line-through' },
  adFreeCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.md,
    borderWidth: 1, borderColor: colors.borderSoft, marginBottom: spacing.md,
  },
  adFreeIcon: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(0,209,255,0.15)',
    alignItems: 'center', justifyContent: 'center',
  },
  adFreeTitle: { color: colors.text, fontSize: 14, fontWeight: '800' },
  adFreeSub: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  adFreeBtn: {
    paddingHorizontal: 14, paddingVertical: 10,
    backgroundColor: colors.secondary, borderRadius: 12,
  },
  adFreeBtnOwned: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  adFreeBtnText: { color: '#0B0E14', fontSize: 13, fontWeight: '800' },
  disclaimer: { flexDirection: 'row', gap: 6, padding: spacing.sm, alignItems: 'flex-start' },
  disclaimerText: { flex: 1, color: colors.textTertiary, fontSize: 10, lineHeight: 14 },
});
