import React, { useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  TouchableOpacity,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fonts, media, shadows } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';

const { width } = Dimensions.get('window');

export default function Onboarding() {
  const router = useRouter();
  const { user, loading } = useSession();

  useEffect(() => {
    if (!loading && user) {
      router.replace('/(tabs)');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Image
        source={{ uri: media.dashboardBg }}
        style={styles.bgImage}
        blurRadius={2}
      />
      <LinearGradient
        colors={['rgba(11,14,20,0.3)', 'rgba(11,14,20,0.85)', colors.bg]}
        style={StyleSheet.absoluteFillObject}
      />

      <View style={styles.heroWrap}>
        <Image source={{ uri: media.miningHardware }} style={styles.hero} />
        <View style={styles.glowOrb} />
      </View>

      <View style={styles.content}>
        <View style={styles.badge} testID="onboarding-badge">
          <View style={styles.badgeDot} />
          <Text style={styles.badgeText}>CLOUD POWERED</Text>
        </View>

        <Text style={styles.title}>
          Mine smarter.{'\n'}
          <Text style={{ color: colors.primary }}>Earn anywhere.</Text>
        </Text>

        <Text style={styles.subtitle}>
          Satoshi Cloud Miner puts a cloud mining farm in your pocket. No rigs, no setup —
          just instant access to enterprise hash power and live earnings.
        </Text>

        <View style={styles.features}>
          <Feature icon="flash" text="Instant cloud mining" />
          <Feature icon="trending-up" text="Live earnings tracker" />
          <Feature icon="shield-checkmark" text="Secure withdrawals" />
        </View>

        <TouchableOpacity
          testID="onboarding-get-started-btn"
          activeOpacity={0.85}
          style={styles.primaryBtn}
          onPress={() => router.push('/sign-up')}
        >
          <Text style={styles.primaryBtnText}>Get Started — It's Free</Text>
          <Ionicons name="arrow-forward" size={20} color={colors.bg} />
        </TouchableOpacity>

        <TouchableOpacity
          testID="onboarding-sign-in-btn"
          activeOpacity={0.7}
          style={styles.secondaryBtn}
          onPress={() => router.push('/sign-in')}
        >
          <Text style={styles.secondaryBtnText}>I already have an account</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function Feature({ icon, text }: { icon: any; text: string }) {
  return (
    <View style={styles.featureRow}>
      <View style={styles.featureIcon}>
        <Ionicons name={icon} size={16} color={colors.primary} />
      </View>
      <Text style={styles.featureText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { justifyContent: 'center', alignItems: 'center' },
  bgImage: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '60%',
    opacity: 0.4,
  },
  heroWrap: {
    height: '38%',
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: spacing.xl,
  },
  hero: {
    width: width * 0.72,
    height: width * 0.72,
    resizeMode: 'contain',
  },
  glowOrb: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: colors.primaryGlow,
    opacity: 0.5,
    top: '30%',
    zIndex: -1,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    justifyContent: 'flex-end',
  },
  badge: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    alignItems: 'center',
    backgroundColor: colors.primaryDim,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.full,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  badgeText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
  },
  title: {
    color: colors.text,
    fontSize: 38,
    fontWeight: '800',
    lineHeight: 44,
    letterSpacing: -1,
    marginBottom: spacing.md,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  features: {
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  featureIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primaryDim,
    justifyContent: 'center',
    alignItems: 'center',
  },
  featureText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '500',
  },
  primaryBtn: {
    flexDirection: 'row',
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
    ...shadows.glow,
  },
  primaryBtnText: {
    color: colors.bg,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.2,
  },
  secondaryBtn: {
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  secondaryBtnText: {
    color: colors.textSecondary,
    fontSize: 14,
    fontWeight: '600',
  },
});
