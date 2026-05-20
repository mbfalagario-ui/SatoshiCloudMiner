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
  }, [load]);

  const buy = (pkg: Pkg) => {
    confirmDialog(
      'Confirm purchase',
      `Buy "${pkg.name}" for ${fmtUsd(pkg.price_usd)}?\n\nIn the App Store version, this will be processed via Apple In-App Purchase.`,
      async () => {
        setBuyingId(pkg.id);
        try {
          const r = await api('/packages/buy', {
            method: 'POST',
            body: JSON.stringify({ package_id: pkg.id }),
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
          <Text style={styles.title}>Cloud Mining Power</Text>
          <Text style={styles.subtitle}>Choose a hashpower package</Text>
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
          const totalDays = item.duration_days;
          const totalReturn = item.daily_yield_usd * totalDays;
          const profitable = totalReturn > item.price_usd;
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

              <View style={styles.summaryRow}>
                <Text style={styles.summaryText}>
                  Total estimated return:{' '}
                  <Text style={{ color: profitable ? colors.primary : colors.text, fontWeight: '700' }}>
                    {fmtUsd(totalReturn)}
                  </Text>
                </Text>
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
