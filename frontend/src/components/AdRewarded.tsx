import React, { useEffect, useRef, useState } from 'react';
import { Modal, View, Text, StyleSheet, TouchableOpacity, Animated, Easing } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, fonts } from '@/src/utils/theme';

// Lightweight simulator for rewarded ads while the AdMob SDK is being
// integrated. Looks like a real ad with a countdown and "Reward" prompt.
// Backend grants the actual hashrate via /api/ads/claim_dev when caller
// completes successfully.
export default function AdRewarded({
  visible,
  onClose,
  durationSec = 5,
}: {
  visible: boolean;
  onClose: (ok: boolean) => void;
  durationSec?: number;
}) {
  const [remaining, setRemaining] = useState(durationSec);
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) return;
    setRemaining(durationSec);
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: durationSec * 1000,
      easing: Easing.linear,
      useNativeDriver: false,
    }).start();
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(t);
  }, [visible, durationSec, progress]);

  const canClaim = remaining <= 0;

  return (
    <Modal visible={visible} animationType="fade" transparent={false}>
      <View style={styles.bg}>
        <LinearGradient
          colors={['#0B0E14', '#11334D', '#0B0E14']}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.top}>
          <Text style={styles.label}>Sponsored · Hashrate Boost</Text>
          <Text style={styles.timer}>{canClaim ? 'Ready!' : `${remaining}s`}</Text>
        </View>
        <View style={styles.center}>
          <Animated.View
            style={[
              styles.pulseRing,
              {
                transform: [
                  {
                    scale: progress.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1.05] }),
                  },
                ],
              },
            ]}
          />
          <View style={styles.iconBox}>
            <Ionicons name="flash" size={56} color={colors.primary} />
          </View>
          <Text style={styles.headline}>Free hashrate</Text>
          <Text style={styles.sub}>Watch the full ad to earn a 24-hour hashpower boost.</Text>
        </View>
        <View style={styles.bar}>
          <Animated.View
            style={[
              styles.barFill,
              {
                width: progress.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }),
              },
            ]}
          />
        </View>
        <View style={styles.actions}>
          <TouchableOpacity onPress={() => onClose(false)} style={styles.skipBtn}>
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => canClaim && onClose(true)}
            disabled={!canClaim}
            style={[styles.claimBtn, !canClaim && styles.claimBtnMuted]}
            testID="ad-claim-btn"
          >
            <Text style={[styles.claimText, !canClaim && { color: colors.textTertiary }]}>
              {canClaim ? 'Claim reward' : 'Watching...'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg, padding: 20, justifyContent: 'space-between' },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 60 },
  label: { color: colors.textTertiary, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  timer: { color: colors.primary, fontSize: 14, fontWeight: '900', fontFamily: fonts.mono },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 8 },
  pulseRing: {
    position: 'absolute',
    width: 200, height: 200, borderRadius: 100,
    backgroundColor: colors.primaryGlow,
  },
  iconBox: {
    width: 130, height: 130, borderRadius: 65,
    backgroundColor: 'rgba(0,255,163,0.20)',
    borderWidth: 2, borderColor: colors.primary,
    justifyContent: 'center', alignItems: 'center',
    marginBottom: 16,
  },
  headline: { color: colors.text, fontSize: 22, fontWeight: '800' },
  sub: { color: colors.textSecondary, fontSize: 13, textAlign: 'center', marginHorizontal: 30 },
  bar: {
    height: 4, backgroundColor: colors.surface, borderRadius: 2, marginVertical: 16, overflow: 'hidden',
  },
  barFill: { height: '100%', backgroundColor: colors.primary, borderRadius: 2 },
  actions: { flexDirection: 'row', gap: 12, marginBottom: 30 },
  skipBtn: {
    paddingHorizontal: 20, paddingVertical: 14,
    borderWidth: 1, borderColor: colors.border,
    borderRadius: 14,
  },
  skipText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
  claimBtn: { flex: 1, backgroundColor: colors.primary, paddingVertical: 14, borderRadius: 14, alignItems: 'center' },
  claimBtnMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
  claimText: { color: colors.bg, fontSize: 14, fontWeight: '800' },
});
