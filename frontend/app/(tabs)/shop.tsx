import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, shadows, media, fmtUsd } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';
import { confirmDialog, notify } from '@/src/utils/dialog';
import { isIapAvailable, initIap, buyProduct, fetchProducts } from '@/src/utils/iap';

type Pkg = {
  id: string;
  name: string;
  tagline: string;
  price_usd: number;
  hash_rate: number;
  duration_days: number;
  daily_yield_usd: number;
  badge?: string | null;
  bogo: boolean;
  // Backend-enriched fields (computed at /api/packages):
  total_return_usd?: number;
  roi_pct?: number;
  break_even_days?: number;
  profitable?: boolean;
  profitability_score?: number;
  ai_optimized?: boolean;
  entitlement?: string;
};

export default function Shop() {
  const { refresh } = useSession();
  const [pkgs, setPkgs] = useState<Pkg[]>([]);
  const [loading, setLoading] = useState(true);
  const [buyingId, setBuyingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api('/packages', { auth: false });
      setPkgs(r.packages);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Pre-warm StoreKit connection so the first tap on "Buy" is instant.
    if (isIapAvailable()) initIap().catch(() => {});
  }, [load]);

  // Once the backend package list arrives, pre-fetch the matching StoreKit
  // products so `requestPurchase` doesn't throw `E_PRODUCT_NOT_AVAILABLE` on
  // the very first tap (required by react-native-iap v15 Nitro).
  useEffect(() => {
    if (!pkgs.length) return;
    if (!isIapAvailable()) return;
    const skus = pkgs.map((p) => p.id);
    fetchProducts(skus).catch((e) => {
      // eslint-disable-next-line no-console
      console.warn('[Shop] StoreKit pre-fetch failed (non-fatal):', e);
    });
  }, [pkgs]);

  const buy = (pkg: Pkg) => {
    const iapOn = isIapAvailable();
    confirmDialog(
      'Confirm purchase',
      iapOn
        ? `Buy "${pkg.name}" for ${fmtUsd(pkg.price_usd)}?\n\nApple's purchase sheet will appear next. You'll be charged via your Apple ID.`
        : `Buy "${pkg.name}" for ${fmtUsd(pkg.price_usd)}?\n\nDev mode: purchase will be simulated. On a real iOS build this triggers Apple In-App Purchase.`,
      async () => {
        setBuyingId(pkg.id);
        try {
          let appleTransactionId: string | undefined;
          if (iapOn) {
            const r = await buyProduct(pkg.id);
            if (!r.applePurchase || !r.transactionId) {
              throw new Error('Apple did not return a transaction id.');
            }
            appleTransactionId = r.transactionId;
          }

          const body: { package_id: string; apple_transaction_id?: string } = {
            package_id: pkg.id,
          };
          if (appleTransactionId) body.apple_transaction_id = appleTransactionId;

          const r = await api('/packages/buy', {
            method: 'POST',
            body: JSON.stringify(body),
          });
          await refresh();
          notify(
            'Purchase successful',
            `${r.machines_added} miner${r.machines_added > 1 ? 's' : ''} added to your account.`
          );
        } catch (e: any) {
          notify('Purchase failed', e?.message ?? 'Try again.');
        } finally {
          setBuyingId(null);
        }
      },
      'Buy now'
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>AI Mining Plans</Text>
          <Text style={styles.subtitle}>Pick a plan · AI agents optimize your yield</Text>
        </View>
        <Image source={{ uri: media.serverRack }} style={styles.headerImg} />
      </View>

      <FlatList
        data={pkgs}
        keyExtractor={(it) => it.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />
        }
        ListEmptyComponent={
          loading ? (
            <View style={{ marginTop: 60, alignItems: 'center' }}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : (
            <Text style={styles.empty}>No packages available.</Text>
          )
        }
        renderItem={({ item }) => {
          const totalReturn = item.total_return_usd ?? item.daily_yield_usd * item.duration_days;
          const profitable = item.profitable ?? totalReturn > item.price_usd;
          const roi = item.roi_pct ?? ((totalReturn - item.price_usd) / item.price_usd) * 100;
          const breakEven = item.break_even_days ?? item.price_usd / Math.max(item.daily_yield_usd, 0.0001);
          const stars = Math.max(0, Math.min(5, Math.round((item.profitability_score ?? 0))));
          return (
            <View
              testID={`pkg-${item.id}`}
              style={[
                styles.card,
                item.badge === 'POPULAR' && { borderColor: colors.primary },
                item.badge === 'FLAGSHIP' && { borderColor: colors.secondary },
              ]}
            >
              {item.badge && (
                <View
                  style={[
                    styles.badge,
                    item.badge === 'POPULAR' && { backgroundColor: colors.primary },
                    item.badge === 'FLAGSHIP' && { backgroundColor: colors.secondary },
                    item.badge === 'BOGO' && { backgroundColor: colors.warning },
                  ]}
                >
                  <Text
                    style={[
                      styles.badgeText,
                      (item.badge === 'POPULAR' || item.badge === 'FLAGSHIP' || item.badge === 'BOGO') && {
                        color: colors.bg,
                      },
                    ]}
                  >
                    {item.badge}
                  </Text>
                </View>
              )}

              <View style={styles.cardHead}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.pkgName}>{item.name}</Text>
                  <Text style={styles.pkgTag}>{item.tagline}</Text>
                  {item.ai_optimized ? (
                    <View style={styles.aiChip}>
                      <Ionicons name="sparkles" size={11} color={colors.primary} />
                      <Text style={styles.aiChipText}>AI-OPTIMIZED YIELD</Text>
                    </View>
                  ) : null}
                </View>
                <View style={styles.priceWrap}>
                  <Text style={styles.priceUsd}>{fmtUsd(item.price_usd)}</Text>
                </View>
              </View>

              <View style={styles.specs}>
                <Spec label="Hashpower" value={`${item.hash_rate.toFixed(0)} TH/s`} />
                <Spec label="Duration" value={`${item.duration_days}d`} />
                <Spec label="Daily yield" value={fmtUsd(item.daily_yield_usd)} />
              </View>

              {/* AI Profitability projection */}
              <View style={styles.profitCard}>
                <View style={styles.profitRow}>
                  <Text style={styles.profitLabel}>AI ROI projection</Text>
                  <Text style={[styles.profitValue, { color: profitable ? colors.primary : colors.warning }]}>
                    {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
                  </Text>
                </View>
                <View style={styles.profitRow}>
                  <Text style={styles.profitLabel}>Total est. return</Text>
                  <Text style={styles.profitValue}>{fmtUsd(totalReturn)}</Text>
                </View>
                <View style={styles.profitRow}>
                  <Text style={styles.profitLabel}>Break-even</Text>
                  <Text style={styles.profitValue}>{breakEven.toFixed(1)} days</Text>
                </View>
                <View style={styles.profitRow}>
                  <Text style={styles.profitLabel}>Profitability score</Text>
                  <View style={styles.stars}>
                    {[0, 1, 2, 3, 4].map((i) => (
                      <Ionicons
                        key={i}
                        name={i < stars ? 'star' : 'star-outline'}
                        size={12}
                        color={i < stars ? colors.primary : colors.textTertiary}
                      />
                    ))}
                  </View>
                </View>
                {/* Profitability bar */}
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.barFill,
                      {
                        width: `${Math.min(100, Math.max(8, ((item.profitability_score ?? 0) / 5) * 100))}%`,
                        backgroundColor: profitable ? colors.primary : colors.warning,
                      },
                    ]}
                  />
                </View>
              </View>

              <TouchableOpacity
                testID={`pkg-buy-${item.id}`}
                style={[styles.buyBtn, buyingId === item.id && { opacity: 0.6 }]}
                disabled={!!buyingId}
                onPress={() => buy(item)}
                activeOpacity={0.85}
              >
                {buyingId === item.id ? (
                  <ActivityIndicator color={colors.bg} />
                ) : (
                  <>
                    <Text style={styles.buyBtnText}>Buy {fmtUsd(item.price_usd)}</Text>
                    <Ionicons name="flash" size={16} color={colors.bg} />
                  </>
                )}
              </TouchableOpacity>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.spec}>
      <Text style={styles.specLabel}>{label}</Text>
      <Text style={styles.specValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: { color: colors.text, fontSize: 26, fontWeight: '800', letterSpacing: -0.6 },
  subtitle: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  headerImg: { width: 56, height: 56, borderRadius: 14, opacity: 0.6 },
  list: { paddingHorizontal: spacing.lg, paddingBottom: 120 },
  empty: { color: colors.textSecondary, textAlign: 'center', marginTop: 60 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.md,
    ...shadows.card,
  },
  badge: {
    position: 'absolute',
    top: -10,
    right: spacing.md,
    backgroundColor: colors.primaryDim,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.full,
  },
  badgeText: { color: colors.primary, fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.md },
  pkgName: { color: colors.text, fontSize: 18, fontWeight: '800', letterSpacing: -0.3 },
  pkgTag: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  priceWrap: { alignItems: 'flex-end' },
  priceUsd: {
    color: colors.primary,
    fontSize: 22,
    fontWeight: '800',
    fontFamily: fonts.mono,
  },
  specs: {
    flexDirection: 'row',
    backgroundColor: colors.bg,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  spec: { flex: 1 },
  specLabel: { color: colors.textTertiary, fontSize: 10, fontWeight: '700', letterSpacing: 0.8 },
  specValue: { color: colors.text, fontSize: 14, fontWeight: '700', marginTop: 2, fontFamily: fonts.mono },
  summaryRow: { marginBottom: spacing.md },
  summaryText: { color: colors.textSecondary, fontSize: 12 },
  aiChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primaryDim,
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: radius.sm,
    alignSelf: 'flex-start',
    marginTop: 6,
  },
  aiChipText: { color: colors.primary, fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  profitCard: {
    backgroundColor: colors.bg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: 6,
  },
  profitRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  profitLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '600', letterSpacing: 0.3 },
  profitValue: { color: colors.text, fontSize: 13, fontWeight: '800', fontFamily: fonts.mono },
  stars: { flexDirection: 'row', gap: 1 },
  barTrack: {
    height: 4,
    backgroundColor: colors.borderSoft,
    borderRadius: 2,
    marginTop: 6,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: 2 },
  buyBtn: {
    flexDirection: 'row',
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: 14,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  buyBtnText: { color: colors.bg, fontSize: 15, fontWeight: '800' },
});
