/**
 * Lightweight interstitial "ad" overlay used between tab switches.
 *
 * Behaviour:
 *  - Cross-promotes the app's own AI mining plans (a.k.a. "house ads").
 *    Using the app's own content keeps us 100% compliant with App Store
 *    guidelines (no third-party network, no tracking, no PII).
 *  - 5 second skip timer; users can dismiss after that.
 *  - Hidden entirely when the user owns the Ad-Free entitlement.
 *  - Replaceable later with a real ad network (AdMob / Unity) by swapping
 *    out the body of this component without touching the rest of the app.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Platform,
  Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { colors, spacing, radius, fonts, shadows } from '@/src/utils/theme';

const SKIP_AFTER_S = 5;

const CREATIVES = [
  {
    id: 'pro-rig',
    headline: 'Most popular: Pro Rig',
    sub: 'AI-optimized cluster. 30 days of high-yield mining.',
    cta: 'View plan',
    accent: '#00FFA3',
    iconName: 'flash' as const,
    pkg: 'pro_499',
  },
  {
    id: 'colossus',
    headline: 'Flagship: Colossus Farm',
    sub: '1900 TH/s, 365 days. Maximum hashpower yield.',
    cta: 'Explore',
    accent: '#A78BFA',
    iconName: 'rocket' as const,
    pkg: 'colossus_19999',
  },
  {
    id: 'mega',
    headline: 'Industrial scale: Mega Farm',
    sub: '380 TH/s for 90 days. Pro tier returns.',
    cta: 'See details',
    accent: '#FBBF24',
    iconName: 'cube' as const,
    pkg: 'mega_4999',
  },
  {
    id: 'ad-free',
    headline: 'Tired of ads?',
    sub: 'Go Ad-Free + Priority Support for a one-time $3.99.',
    cta: 'Upgrade',
    accent: '#FF6B6B',
    iconName: 'sparkles' as const,
    pkg: 'adfree_399',
  },
];

export default function AdInterstitial({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const router = useRouter();
  const [secondsLeft, setSecondsLeft] = useState(SKIP_AFTER_S);
  const opacity = useRef(new Animated.Value(0)).current;

  // Pick a random creative on each show.
  const creative = useMemo(() => {
    const idx = Math.floor(Math.random() * CREATIVES.length);
    return CREATIVES[idx];
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    setSecondsLeft(SKIP_AFTER_S);
    Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }).start();
    const t = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [visible, opacity]);

  const close = () => {
    Animated.timing(opacity, { toValue: 0, duration: 150, useNativeDriver: true }).start(onClose);
  };

  const tap = () => {
    onClose();
    router.push('/shop');
  };

  if (!visible) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={() => { if (secondsLeft <= 0) close(); }}
    >
      <Animated.View style={[styles.scrim, { opacity }]}>
        <View style={styles.card} testID="ad-interstitial">
          <View style={styles.headerRow}>
            <Text style={styles.tagSponsored}>SPONSORED</Text>
            {secondsLeft > 0 ? (
              <View style={styles.timerPill}>
                <Text style={styles.timerText}>Skip in {secondsLeft}s</Text>
              </View>
            ) : (
              <TouchableOpacity testID="ad-close-btn" style={styles.closeBtn} onPress={close}>
                <Ionicons name="close" size={20} color={colors.text} />
              </TouchableOpacity>
            )}
          </View>

          <Pressable onPress={tap} style={styles.body}>
            <View style={[styles.iconWrap, { backgroundColor: creative.accent + '22' }]}>
              <Ionicons name={creative.iconName} size={48} color={creative.accent} />
            </View>
            <Text style={styles.headline}>{creative.headline}</Text>
            <Text style={styles.sub}>{creative.sub}</Text>
            <View style={[styles.ctaBtn, { backgroundColor: creative.accent }]}>
              <Text style={[styles.ctaText, { color: creative.accent === '#FBBF24' ? colors.bg : colors.bg }]}>
                {creative.cta}
              </Text>
              <Ionicons name="chevron-forward" size={16} color={colors.bg} />
            </View>
          </Pressable>

          <Text style={styles.footnote}>Promoted in-app content. Owned by Satoshi Cloud Miner.</Text>
        </View>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.78)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    ...shadows.card,
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md },
  tagSponsored: {
    color: colors.textTertiary,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.4,
    backgroundColor: colors.bg,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.sm,
  },
  timerPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  timerText: { color: colors.textSecondary, fontSize: 11, fontWeight: '700' },
  closeBtn: {
    width: 28, height: 28, borderRadius: 14,
    justifyContent: 'center', alignItems: 'center',
    backgroundColor: colors.bg,
  },
  body: { alignItems: 'center', paddingVertical: spacing.md },
  iconWrap: {
    width: 96, height: 96, borderRadius: 48,
    justifyContent: 'center', alignItems: 'center',
    marginBottom: spacing.md,
  },
  headline: { color: colors.text, fontSize: 20, fontWeight: '800', textAlign: 'center', marginBottom: 6 },
  sub: { color: colors.textSecondary, fontSize: 13, textAlign: 'center', marginBottom: spacing.md, paddingHorizontal: spacing.sm },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: radius.md,
    minWidth: 200,
  },
  ctaText: { fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  footnote: { color: colors.textTertiary, fontSize: 10, textAlign: 'center', marginTop: spacing.md },
});
