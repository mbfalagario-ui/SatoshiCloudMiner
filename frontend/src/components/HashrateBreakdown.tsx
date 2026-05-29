import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, spacing, fonts, fmtGhs } from '@/src/utils/theme';

export type HashrateBreakdown = {
  total_ghs: number;
  pack_ghs: number;
  checkin_ghs: number;
  ad_ghs: number;
};

export default function HashrateBreakdownCard({ data }: { data: HashrateBreakdown }) {
  return (
    <View style={styles.card} testID="hashrate-breakdown">
      <View style={styles.headerRow}>
        <Ionicons name="speedometer" size={18} color={colors.primary} />
        <Text style={styles.title}>Active Hashrate</Text>
      </View>
      <Text style={styles.total} testID="hashrate-total">{fmtGhs(data.total_ghs || 0)}</Text>
      <View style={styles.row}>
        <Cell label="Plans" value={fmtGhs(data.pack_ghs || 0)} icon="layers" />
        <View style={styles.divider} />
        <Cell label="Check-in" value={fmtGhs(data.checkin_ghs || 0)} icon="calendar" />
        <View style={styles.divider} />
        <Cell label="Ads" value={fmtGhs(data.ad_ghs || 0)} icon="play" />
      </View>
    </View>
  );
}

function Cell({ label, value, icon }: any) {
  return (
    <View style={styles.cell}>
      <View style={styles.cellHeader}>
        <Ionicons name={icon} size={12} color={colors.textSecondary} />
        <Text style={styles.cellLabel}>{label}</Text>
      </View>
      <Text style={styles.cellValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.md,
  },
  headerRow: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  title: { color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 1.2 },
  total: {
    color: colors.primary,
    fontSize: 32,
    fontWeight: '800',
    fontFamily: fonts.mono,
    marginTop: 4,
    letterSpacing: -0.5,
  },
  row: { flexDirection: 'row', marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  cell: { flex: 1, alignItems: 'center', gap: 4 },
  cellHeader: { flexDirection: 'row', gap: 4, alignItems: 'center' },
  cellLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '600' },
  cellValue: { color: colors.text, fontSize: 12, fontWeight: '700', fontFamily: fonts.mono },
  divider: { width: 1, backgroundColor: colors.borderSoft },
});
