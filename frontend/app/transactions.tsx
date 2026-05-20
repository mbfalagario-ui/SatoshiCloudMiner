import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, fmtUsd } from '@/src/utils/theme';

type Tx = {
  id: string;
  type: 'mining' | 'purchase' | 'withdrawal' | 'bonus' | 'referral';
  amount_usd: number;
  amount_btc: number;
  status: string;
  description: string;
  method?: string;
  created_at: string;
};

const ICONS: any = {
  mining: 'flash',
  purchase: 'cart',
  withdrawal: 'arrow-up-circle',
  bonus: 'gift',
  referral: 'people',
};

export default function Transactions() {
  const router = useRouter();
  const [items, setItems] = useState<Tx[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api('/transactions');
      setItems(r.transactions);
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
        <Text style={styles.title}>Transactions</Text>
        <View style={{ width: 40 }} />
      </View>

      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />}
        ListEmptyComponent={
          !loading ? <Text style={styles.empty}>No transactions yet.</Text> : null
        }
        renderItem={({ item }) => {
          const isCredit = item.type !== 'withdrawal' && item.type !== 'purchase';
          const sign = isCredit ? '+' : '-';
          const color = item.type === 'withdrawal' ? colors.warning : item.type === 'purchase' ? colors.danger : colors.primary;
          const d = new Date(item.created_at);
          return (
            <View style={styles.row} testID={`tx-${item.id}`}>
              <View style={[styles.icon, { backgroundColor: color + '20' }]}>
                <Ionicons name={ICONS[item.type] || 'cash'} size={18} color={color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.desc} numberOfLines={1}>{item.description}</Text>
                <Text style={styles.date}>{d.toLocaleDateString()} · {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={[styles.amount, { color }]}>
                  {sign}{fmtUsd(item.amount_usd)}
                </Text>
                <Text style={styles.status}>{item.status}</Text>
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
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.sm,
  },
  back: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface,
    justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  empty: { color: colors.textSecondary, fontSize: 14, textAlign: 'center', marginTop: 60 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.md,
    borderWidth: 1, borderColor: colors.borderSoft, marginBottom: spacing.sm,
  },
  icon: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  desc: { color: colors.text, fontSize: 13, fontWeight: '700' },
  date: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: '800', fontFamily: fonts.mono },
  status: { color: colors.textTertiary, fontSize: 10, fontWeight: '700', letterSpacing: 0.5, marginTop: 2, textTransform: 'uppercase' },
});
