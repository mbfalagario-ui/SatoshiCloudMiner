import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, spacing, fonts } from '@/src/utils/theme';

const NETWORKS = [
  {
    id: 'lightning',
    name: 'Lightning',
    sub: 'Instant payouts · BOLT11 invoice or LN address (speed.app, zbd.gg)',
    recommend: true,
  },
];

export default function NetworkSelect() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.close}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Select a network</Text>
        <View style={{ width: 32 }} />
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {NETWORKS.map((n) => (
          <TouchableOpacity
            key={n.id}
            style={styles.row}
            onPress={() => router.push('/redeem/form')}
            testID={`network-${n.id}`}
          >
            <View style={styles.rowIcon}>
              <Ionicons name="flash" size={22} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <View style={styles.rowTitleRow}>
                <Text style={styles.rowTitle}>{n.name}</Text>
                {n.recommend ? (
                  <View style={styles.pill}><Text style={styles.pillText}>Recommend</Text></View>
                ) : null}
              </View>
              <Text style={styles.rowSub}>{n.sub}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  close: { width: 32, height: 32, justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  scroll: { padding: spacing.lg },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: spacing.md, backgroundColor: colors.surface,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderSoft,
    marginBottom: spacing.sm,
  },
  rowIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(0,255,163,0.15)', alignItems: 'center', justifyContent: 'center' },
  rowTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  rowSub: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  pill: { backgroundColor: 'rgba(0,255,163,0.18)', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  pillText: { color: colors.primary, fontSize: 10, fontWeight: '800' },
});
