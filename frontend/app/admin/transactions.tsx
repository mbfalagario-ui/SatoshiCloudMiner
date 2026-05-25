import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, shadows, fmtUsd } from '@/src/utils/theme';
import { fmtSats } from '@/src/utils/sats';
import { confirmDialog, notify } from '@/src/utils/dialog';

const TYPES = ['all', 'purchase', 'withdrawal', 'mining', 'checkin', 'referral', 'reinvest'];

export default function AdminTransactions() {
  const [items, setItems] = useState<any[]>([]);
  const [type, setType] = useState('all');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = type !== 'all' ? `?type=${type}` : '';
      const r = await api(`/admin/transactions${q}`);
      setItems(r.transactions || []);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => { load(); }, [load]);

  const setStatus = async (tx: any, status: string) => {
    try {
      await api(`/admin/transactions/${tx.id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      await load();
      notify('Updated', `Status set to ${status}`);
    } catch (e: any) {
      notify('Failed', e?.message ?? 'Try again.');
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filters} contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: 6 }}>
        {TYPES.map((t) => (
          <TouchableOpacity key={t} style={[styles.chip, type === t && styles.chipOn]} onPress={() => setType(t)}>
            <Text style={[styles.chipText, type === t && { color: colors.bg }]}>{t.toUpperCase()}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm }}
        ListEmptyComponent={!loading ? <Text style={{ color: colors.textTertiary, textAlign: 'center', marginTop: 80 }}>No transactions yet.</Text> : null}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.rowTop}>
              <View style={{ flex: 1 }}>
                <Text style={styles.title}>{(item.type || '').toUpperCase()} · {item.method || ''}</Text>
                <Text style={styles.id}>{item.user_email || item.user_id?.slice(0, 8)} · {new Date(item.created_at).toLocaleString()}</Text>
              </View>
              <Text style={[styles.status, item.status === 'completed' && { color: colors.primary }, item.status === 'failed' && { color: colors.danger }, item.status === 'pending' && { color: colors.warning }]}>
                {item.status?.toUpperCase()}
              </Text>
            </View>
            <View style={styles.metaRow}>
              <Meta label="Amount" value={item.amount_sats ? fmtSats(item.amount_sats) : fmtUsd(item.amount_usd || 0)} />
              {item.fee_sats ? <Meta label="Fee" value={fmtSats(item.fee_sats)} /> : null}
              <Meta label="USD" value={fmtUsd(item.amount_usd || 0)} />
            </View>
            {item.address ? (
              <Text style={styles.addr} numberOfLines={1}>{item.address}</Text>
            ) : null}
            {item.type === 'withdrawal' ? (
              <View style={styles.actions}>
                {item.status !== 'completed' && <ActBtn icon="checkmark" label="Mark completed" tone="primary" onPress={() => setStatus(item, 'completed')} />}
                {item.status !== 'failed' && <ActBtn icon="close" label="Mark failed" tone="warning" onPress={() => confirmDialog('Confirm', 'Mark as failed?', () => setStatus(item, 'failed'))} />}
              </View>
            ) : null}
          </View>
        )}
      />
    </SafeAreaView>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <View><Text style={styles.metaLabel}>{label}</Text><Text style={styles.metaValue}>{value}</Text></View>
  );
}

function ActBtn({ icon, label, onPress, tone }: any) {
  const c = tone === 'primary' ? colors.primary : tone === 'warning' ? colors.warning : colors.text;
  return (
    <TouchableOpacity style={styles.actBtn} onPress={onPress} activeOpacity={0.85}>
      <Ionicons name={icon} size={13} color={c} />
      <Text style={[styles.actBtnText, { color: c }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  filters: { backgroundColor: colors.surface, borderBottomWidth: 1, borderColor: colors.borderSoft, paddingVertical: 10, flexGrow: 0 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text, fontSize: 11, fontWeight: '700', letterSpacing: 0.6 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: 8,
    ...shadows.card,
  },
  rowTop: { flexDirection: 'row', alignItems: 'center' },
  title: { color: colors.text, fontSize: 13, fontWeight: '800', letterSpacing: 0.3 },
  id: { color: colors.textTertiary, fontSize: 11, marginTop: 2 },
  status: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: colors.textSecondary },
  metaRow: { flexDirection: 'row', gap: spacing.md },
  metaLabel: { color: colors.textTertiary, fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  metaValue: { color: colors.text, fontSize: 13, fontWeight: '700', fontFamily: fonts.mono, marginTop: 2 },
  addr: { color: colors.textSecondary, fontSize: 11, fontFamily: fonts.mono },
  actions: { flexDirection: 'row', gap: 6, marginTop: 4 },
  actBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border },
  actBtnText: { fontSize: 11, fontWeight: '700' },
});
