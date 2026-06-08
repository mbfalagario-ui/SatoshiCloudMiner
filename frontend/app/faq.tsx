import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  LayoutAnimation,
  Platform,
  UIManager,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts } from '@/src/utils/theme';

// Enable LayoutAnimation on Android.
if (
  Platform.OS === 'android' &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

type FAQ = { id: string; q: string; a: string };

export default function FaqScreen() {
  const router = useRouter();
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api('/faqs', { auth: false });
      setFaqs(r.faqs || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (id: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOpenId((curr) => (curr === id ? null : id));
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back} testID="back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Help & FAQs</Text>
        <View style={{ width: 40 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll}>
          {faqs.length === 0 ? (
            <Text style={styles.empty}>No frequently asked questions available yet.</Text>
          ) : (
            faqs.map((f) => {
              const open = openId === f.id;
              return (
                <TouchableOpacity
                  key={f.id}
                  testID={`faq-${f.id}`}
                  style={styles.card}
                  onPress={() => toggle(f.id)}
                  activeOpacity={0.8}
                >
                  <View style={styles.qRow}>
                    <Text style={styles.q} numberOfLines={open ? undefined : 2}>
                      {f.q}
                    </Text>
                    <Ionicons
                      name={open ? 'chevron-up' : 'chevron-down'}
                      size={18}
                      color={colors.textSecondary}
                    />
                  </View>
                  {open ? <Text style={styles.a}>{f.a}</Text> : null}
                </TouchableOpacity>
              );
            })
          )}

          <View style={styles.footerCard}>
            <Text style={styles.footerTitle}>Need more help?</Text>
            <Text style={styles.footerBody}>
              Reach our support team at support@hashratecloudminer.com or
              use Profile → Premium Support inside the app.
            </Text>
          </View>
        </ScrollView>
      )}
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
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: spacing.lg, paddingBottom: spacing.xl },
  empty: { color: colors.textSecondary, textAlign: 'center', marginTop: spacing.xl },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    marginBottom: spacing.sm,
  },
  qRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  q: {
    flex: 1,
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 19,
  },
  a: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    marginTop: spacing.sm,
    fontFamily: fonts.body,
  },
  footerCard: {
    marginTop: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.primaryDim,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  footerTitle: { color: colors.text, fontWeight: '800', fontSize: 14 },
  footerBody: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4,
  },
});
