import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, fmtUsd, media } from '@/src/utils/theme';

type Machine = {
  id: string;
  name: string;
  hash_rate: number;
  daily_yield_usd: number;
  duration_days: number;
  purchased_at: string;
  expires_at: string;
  status: string;
};

export default function Machines() {
  const router = useRouter();
  const [items, setItems] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api('/machines');
      setItems(r.machines);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-btn" onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>My Miners</Text>
        <View style={{ width: 40 }} />
      </View>

      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />}
        ListEmptyComponent={
          !loading ? (
            <View style={{ marginTop: 80, alignItems: 'center' }}>
              <Text style={styles.empty}>You don't own any miners yet.</Text>
              <TouchableOpacity
                testID="machines-shop-cta"
                style={styles.cta}
                onPress={() => router.push('/(tabs)/shop')}
              >
                <Text style={styles.ctaText}>Browse packages</Text>
              </TouchableOpacity>
            </View>
          ) : null
        }
        renderItem={({ item }) => {
          const exp = new Date(item.expires_at);
          const days = Math.max(0, Math.ceil((exp.getTime() - Date.now()) / 86400000));
          const active = item.status === 'active' && days > 0;
          return (
            <View style={[styles.row, !active && { opacity: 0.55 }]} testID={`machine-${item.id}`}>
              <Image source={{ uri: media.miningHardware }} style={styles.thumb} />
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>{item.name}</Text>
                <View style={styles.metaRow}>
                  <Text style={styles.meta}>{item.hash_rate.toFixed(0)} TH/s</Text>
                  <Text style={styles.dot}>·</Text>
                  <Text style={styles.meta}>{fmtUsd(item.daily_yield_usd)}/day</Text>
                </View>
                <View style={[styles.statusPill, active ? styles.statusActive : styles.statusOff]}>
                  <View style={[styles.statusDot, { backgroundColor: active ? colors.primary : colors.textTertiary }]} />
                  <Text style={[styles.statusText, { color: active ? colors.primary : colors.textTertiary }]}>
                    {active ? `Active · ${days}d left` : item.status === 'expired' ? 'Expired' : 'Idle'}
                  </Text>
                </View>
              </View>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  back: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface,
    justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  empty: { color: colors.textSecondary, fontSize: 14 },
  cta: { marginTop: spacing.md, backgroundColor: colors.primary, paddingHorizontal: spacing.lg, paddingVertical: 12, borderRadius: radius.md },
  ctaText: { color: colors.bg, fontWeight: '800' },
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.sm,
    gap: spacing.md,
    alignItems: 'center',
  },
  thumb: { width: 56, height: 56, borderRadius: 12, resizeMode: 'contain', backgroundColor: colors.bg },
  name: { color: colors.text, fontSize: 14, fontWeight: '700' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  meta: { color: colors.textSecondary, fontSize: 12, fontFamily: fonts.mono },
  dot: { color: colors.textTertiary, fontSize: 12 },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start',
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.full, marginTop: 6, gap: 6,
  },
  statusActive: { backgroundColor: colors.primaryDim },
  statusOff: { backgroundColor: 'rgba(255,255,255,0.04)' },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
});
