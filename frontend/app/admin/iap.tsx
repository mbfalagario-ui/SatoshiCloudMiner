/**
 * Admin IAP Self-Check screen.
 *
 * Lets the operator (Michael) verify Apple App Store Server API
 * credentials are wired correctly on the LIVE production backend
 * without running any terminal command. Polls /api/admin/iap/selfcheck
 * (admin-gated; no secret material returned). The screen renders the
 * single decisive line "READY FOR PRODUCTION ✓" / "NOT READY ✗" in
 * large text, plus the masked configuration details and the round-trip
 * verdict from Apple.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius } from '@/src/utils/theme';

type SelfCheck = {
  enabled: boolean;
  require_real: boolean;
  key_source: string;
  private_key: {
    path: string;
    exists_on_disk: boolean;
    size_bytes: number;
    from_env_var: boolean;
  };
  key_id: string;
  issuer_id: string;
  bundle_id: string;
  environment_override: string;
  apple_round_trip: string;
  apple_status: 'ok' | 'bad_creds' | 'missing' | 'unknown' | string;
  ready_for_production: boolean;
};

export default function AdminIAPSelfCheck() {
  const [data, setData] = useState<SelfCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api('/admin/iap/selfcheck');
      setData(r);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message ?? e));
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator color={colors.primary} size="large" />
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
      <Text style={styles.h1}>IAP Self-Check</Text>
      <Text style={styles.sub}>
        Validates the Apple App Store Server API credentials wired into this
        backend. No secret material is shown.
      </Text>

      {err ? (
        <View style={[styles.verdictCard, styles.bad]}>
          <Ionicons name="alert-circle" size={40} color="#FF5C5C" />
          <Text style={styles.verdictText}>SELFCHECK FAILED</Text>
          <Text style={styles.verdictSub} numberOfLines={3}>{err}</Text>
        </View>
      ) : data ? (
        <>
          {/* Big verdict card */}
          {data.ready_for_production ? (
            <View style={[styles.verdictCard, styles.good]}>
              <Ionicons name="checkmark-circle" size={48} color="#3AE090" />
              <Text style={[styles.verdictText, { color: '#3AE090' }]}>READY FOR PRODUCTION</Text>
              <Text style={styles.verdictSub}>
                Apple verification is wired correctly. Safe to ship Build #33.
              </Text>
            </View>
          ) : (
            <View style={[styles.verdictCard, styles.bad]}>
              <Ionicons name="close-circle" size={48} color="#FF5C5C" />
              <Text style={[styles.verdictText, { color: '#FF5C5C' }]}>NOT READY</Text>
              <Text style={styles.verdictSub}>
                One or more checks failed. See diagnostics below.
              </Text>
            </View>
          )}

          {/* Diagnostics */}
          <Section title="Apple round-trip">
            <Row k="Status"     v={data.apple_status} good={data.apple_status === 'ok'} />
            <Row k="Detail"     v={data.apple_round_trip} mono />
          </Section>

          <Section title="Configuration">
            <Row k="Enabled"           v={String(data.enabled)} good={data.enabled} />
            <Row k="Require real"      v={String(data.require_real)} good={data.require_real} />
            <Row k="Key source"        v={data.key_source} mono
                 good={data.key_source.startsWith('env:')} />
            <Row k="Bundle ID"         v={data.bundle_id}
                 good={data.bundle_id === 'app.satoshicloudminer'} />
            <Row k="Key ID (masked)"   v={data.key_id}   mono />
            <Row k="Issuer (masked)"   v={data.issuer_id} mono />
            <Row k="Env override"      v={data.environment_override} mono />
          </Section>

          <Section title="Private key body">
            <Row k="From env var"     v={String(data.private_key.from_env_var)}
                 good={data.private_key.from_env_var} />
            <Row k="On-disk fallback" v={String(data.private_key.exists_on_disk)} />
            <Row k="Size (bytes)"     v={String(data.private_key.size_bytes)} />
            <Row k="Path"             v={data.private_key.path} mono />
          </Section>

          <Text style={styles.footnote}>
            Best practice: in production, the Key source row should read
            env:APPLE_PRIVATE_KEY_PEM and From env var should be true. The
            on-disk path is a dev convenience only.
          </Text>
        </>
      ) : null}

      <TouchableOpacity onPress={onRefresh} activeOpacity={0.85} style={styles.refreshBtn}>
        <Ionicons name="refresh" size={16} color={colors.bg} />
        <Text style={styles.refreshTxt}>Re-run self-check</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

/* ────────── helpers ────────── */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title.toUpperCase()}</Text>
      <View style={styles.sectionBody}>{children}</View>
    </View>
  );
}

function Row({ k, v, good, mono }: { k: string; v: string; good?: boolean; mono?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowK}>{k}</Text>
      <Text
        style={[
          styles.rowV,
          mono && styles.mono,
          good === true && { color: '#3AE090' },
          good === false && { color: '#FF5C5C' },
        ]}
        numberOfLines={3}
      >
        {v}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center:    { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll:    { padding: spacing.lg, paddingBottom: 48 },
  h1:        { color: colors.text, fontSize: 22, fontWeight: '800' },
  sub:       { color: colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: spacing.md, lineHeight: 18 },

  verdictCard: {
    borderRadius: radius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    borderWidth: 1,
    marginBottom: spacing.md,
    gap: 6,
  },
  good: { backgroundColor: '#0C2A1E', borderColor: '#1F5A40' },
  bad:  { backgroundColor: '#2A1212', borderColor: '#5A1F1F' },
  verdictText: { fontSize: 17, fontWeight: '800', letterSpacing: 0.5, marginTop: 4 },
  verdictSub:  { color: colors.textSecondary, fontSize: 12, textAlign: 'center', lineHeight: 18 },

  section:     { marginBottom: spacing.md },
  sectionTitle:{
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  sectionBody: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
    gap: spacing.sm,
  },
  rowK: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', minWidth: 110 },
  rowV: { color: colors.text, fontSize: 12, flex: 1, lineHeight: 18 },
  mono: { fontFamily: 'Menlo' },

  footnote: {
    color: colors.textTertiary,
    fontSize: 11,
    lineHeight: 16,
    fontStyle: 'italic',
    marginTop: 4,
    marginBottom: spacing.md,
  },

  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 12,
    borderRadius: radius.md,
    marginTop: spacing.sm,
  },
  refreshTxt: { color: colors.bg, fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
});
