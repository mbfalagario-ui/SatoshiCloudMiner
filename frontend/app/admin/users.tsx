import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, TextInput, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, shadows, fmtUsd } from '@/src/utils/theme';
import { fmtSats } from '@/src/utils/sats';
import { confirmDialog, notify } from '@/src/utils/dialog';

export default function AdminUsers() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = search ? `?search=${encodeURIComponent(search)}` : '';
      const r = await api(`/admin/users${q}`);
      setUsers(r.users || []);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const patch = async (u: any, body: any, msg: string) => {
    try {
      await api(`/admin/users/${u.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      await load();
      notify('Updated', msg);
    } catch (e: any) {
      notify('Failed', e?.message ?? 'Try again.');
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <View style={styles.searchRow}>
        <Ionicons name="search" size={16} color={colors.textTertiary} />
        <TextInput
          placeholder="Search by email…"
          placeholderTextColor={colors.textTertiary}
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={load}
          style={styles.searchInput}
          autoCapitalize="none"
        />
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
      </View>
      <FlatList
        data={users}
        keyExtractor={(it) => it.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} />}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.rowTop}>
              <View style={{ flex: 1 }}>
                <Text style={styles.email}>{item.email}</Text>
                <Text style={styles.id}>{item.id.slice(0, 12)}…</Text>
              </View>
              <View style={styles.badges}>
                {item.is_admin ? <View style={styles.tagAdmin}><Text style={styles.tagText}>ADMIN</Text></View> : null}
                {item.is_banned ? <View style={styles.tagBan}><Text style={styles.tagText}>BANNED</Text></View> : null}
              </View>
            </View>
            <View style={styles.balRow}>
              <View><Text style={styles.balLabel}>Balance</Text><Text style={styles.balVal}>{fmtSats(item.balance_sats || 0)}</Text></View>
              <View><Text style={styles.balLabel}>USD</Text><Text style={styles.balVal}>{fmtUsd(item.balance_usd || 0)}</Text></View>
              <View><Text style={styles.balLabel}>Lifetime</Text><Text style={styles.balVal}>{fmtUsd(item.lifetime_usd || 0)}</Text></View>
            </View>
            <View style={styles.actions}>
              <ActBtn icon={item.is_banned ? 'lock-open' : 'ban'} label={item.is_banned ? 'Unban' : 'Ban'}
                onPress={() => confirmDialog('Confirm', `${item.is_banned ? 'Unban' : 'Ban'} ${item.email}?`,
                  () => patch(item, { is_banned: !item.is_banned }, item.is_banned ? 'User unbanned.' : 'User banned.'))} />
              <ActBtn icon={item.is_admin ? 'shield-checkmark' : 'shield-outline'} label={item.is_admin ? 'Revoke admin' : 'Make admin'}
                onPress={() => confirmDialog('Confirm', `${item.is_admin ? 'Revoke admin from' : 'Make'} ${item.email}${item.is_admin ? '' : ' an admin'}?`,
                  () => patch(item, { is_admin: !item.is_admin }, 'Admin flag updated.'))} />
              <ActBtn icon="add-circle" label="+ 1000 sats" tone="primary"
                onPress={() => patch(item, { balance_btc_delta: 0.00001000 }, 'Credited 1000 sats.')} />
              <ActBtn icon="remove-circle" label="- 1000 sats" tone="warning"
                onPress={() => confirmDialog('Confirm', `Debit 1000 sats from ${item.email}?`,
                  () => patch(item, { balance_btc_delta: -0.00001000 }, 'Debited 1000 sats.'))} />
            </View>
          </View>
        )}
        ListEmptyComponent={!loading ? (
          <Text style={{ color: colors.textTertiary, textAlign: 'center', marginTop: 80 }}>
            No users match.
          </Text>
        ) : null}
      />
    </SafeAreaView>
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
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.borderSoft,
  },
  searchInput: { flex: 1, color: colors.text, fontSize: 14, paddingVertical: 8 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: 10,
    ...shadows.card,
  },
  rowTop: { flexDirection: 'row', alignItems: 'center' },
  email: { color: colors.text, fontSize: 14, fontWeight: '800' },
  id: { color: colors.textTertiary, fontSize: 10, fontFamily: fonts.mono, marginTop: 2 },
  badges: { flexDirection: 'row', gap: 4 },
  tagAdmin: { backgroundColor: colors.primaryDim, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm },
  tagBan: { backgroundColor: 'rgba(255,90,95,0.18)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm },
  tagText: { color: colors.text, fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  balRow: { flexDirection: 'row', gap: spacing.md, paddingVertical: 6 },
  balLabel: { color: colors.textTertiary, fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  balVal: { color: colors.text, fontSize: 12, fontWeight: '700', fontFamily: fonts.mono, marginTop: 2 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  actBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actBtnText: { fontSize: 11, fontWeight: '700' },
});
