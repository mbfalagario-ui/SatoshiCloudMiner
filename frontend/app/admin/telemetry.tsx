/**
 * Admin Telemetry — Crash Reports viewer.
 *
 * Lists JS crash reports captured by Build #33's 3-layer JS exception
 * fence (global ErrorUtils handler, unhandled-promise tracker, render
 * ErrorBoundary) and POSTed to `/api/telemetry/crash`.
 *
 * Pulls from `GET /api/admin/telemetry/crashes?limit=N`. Each card shows
 * the type, fatality, app/build/OS, the error message, and an expandable
 * stack trace so Michael can read the symbolicated stack right from his
 * iPhone (no curl required).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius } from '@/src/utils/theme';

type Crash = {
  id: string;
  received_at: string;
  ts: string;
  type: string;
  fatal: boolean;
  message: string;
  stack: string;
  app_version: string;
  build_number: string;
  platform: string;
  os_version: string;
};

export default function AdminTelemetry() {
  const [crashes, setCrashes] = useState<Crash[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const r = await api('/admin/telemetry/crashes?limit=100');
      setCrashes(Array.isArray(r?.crashes) ? r.crashes : []);
    } catch (e) {
      // intentional swallow — show an empty state rather than crashing
      // the admin shell over a telemetry list fetch
      setCrashes([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const toggle = (id: string) =>
    setExpanded((m) => ({ ...m, [id]: !m[id] }));

  const fmtTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch {
      return iso || '';
    }
  };

  const typeChip = (type: string, fatal: boolean) => {
    const map: Record<string, { bg: string; fg: string; label: string }> = {
      'error':              { bg: '#3a1f1f', fg: '#FF5C5C', label: 'JS ERROR' },
      'unhandled-rejection':{ bg: '#33291a', fg: '#FFB347', label: 'PROMISE REJ' },
      'render-boundary':    { bg: '#3a1f33', fg: '#FF5CB0', label: 'REACT RENDER' },
    };
    const m = map[type] || { bg: '#1f2633', fg: '#9BA0AC', label: (type || 'UNKNOWN').toUpperCase() };
    return (
      <View style={[styles.chip, { backgroundColor: m.bg }]}>
        <Text style={[styles.chipText, { color: m.fg }]}>{m.label}{fatal ? ' · FATAL' : ''}</Text>
      </View>
    );
  };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={styles.scroll}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.h1}>Crash Telemetry</Text>
        <Text style={styles.sub}>
          {crashes.length === 0
            ? 'No crash reports yet. Pull to refresh.'
            : `${crashes.length} report${crashes.length === 1 ? '' : 's'} · most recent first`}
        </Text>
      </View>

      {crashes.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="shield-checkmark" size={32} color={colors.primary} />
          <Text style={styles.emptyTitle}>All clear</Text>
          <Text style={styles.emptyBody}>
            No JS exceptions have been reported. Reports arrive automatically
            from clients via the global error handler, the Promise rejection
            tracker, and the React ErrorBoundary.
          </Text>
        </View>
      ) : (
        crashes.map((c) => (
          <TouchableOpacity
            key={c.id}
            activeOpacity={0.85}
            onPress={() => toggle(c.id)}
            style={styles.card}
          >
            <View style={styles.cardHeader}>
              {typeChip(c.type, c.fatal)}
              <Text style={styles.cardTime}>{fmtTime(c.received_at)}</Text>
            </View>

            <Text style={styles.message} numberOfLines={expanded[c.id] ? undefined : 2}>
              {c.message || '(no message)'}
            </Text>

            <View style={styles.metaRow}>
              <Meta label="App" value={`${c.app_version || '?'} (${c.build_number || '?'})`} />
              <Meta label="OS" value={`${c.platform || '?'} ${c.os_version || ''}`.trim()} />
            </View>

            {expanded[c.id] ? (
              <View style={styles.stackBox}>
                <Text style={styles.stackLabel}>STACK</Text>
                <Text style={styles.stack}>{c.stack || '(no stack)'}</Text>
                <Text style={styles.id} selectable>{c.id}</Text>
              </View>
            ) : (
              <Text style={styles.expandHint}>tap to view stack trace</Text>
            )}
          </TouchableOpacity>
        ))
      )}
    </ScrollView>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.meta}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { padding: spacing.lg, paddingBottom: 48 },
  header: { marginBottom: spacing.md },
  h1: { color: colors.text, fontSize: 22, fontWeight: '800' },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },

  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.lg,
    alignItems: 'center',
    gap: 8,
  },
  emptyTitle: { color: colors.text, fontSize: 16, fontWeight: '800', marginTop: 4 },
  emptyBody: { color: colors.textSecondary, fontSize: 12, textAlign: 'center', lineHeight: 18 },

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardTime: { color: colors.textSecondary, fontSize: 11 },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  chipText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  message: { color: colors.text, fontSize: 14, lineHeight: 20, marginBottom: 10 },

  metaRow: { flexDirection: 'row', gap: spacing.sm },
  meta: { flex: 1 },
  metaLabel: { color: colors.textSecondary, fontSize: 10, letterSpacing: 0.5, fontWeight: '700' },
  metaValue: { color: colors.text, fontSize: 12, fontWeight: '600', marginTop: 2 },

  stackBox: {
    marginTop: 12,
    backgroundColor: '#0B0E14',
    borderRadius: radius.md,
    padding: 10,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  stackLabel: { color: '#FF5C5C', fontSize: 10, fontWeight: '800', letterSpacing: 0.5, marginBottom: 6 },
  stack: { color: '#D8D8D8', fontSize: 11, fontFamily: 'Menlo', lineHeight: 16 },
  id: { color: '#5A5F6B', fontSize: 10, marginTop: 8, fontFamily: 'Menlo' },

  expandHint: { color: '#5A5F6B', fontSize: 10, marginTop: 8, fontStyle: 'italic' },
});
