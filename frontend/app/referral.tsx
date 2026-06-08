import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Share,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { notify } from '@/src/utils/dialog';
import { colors, spacing, radius, fonts, shadows } from '@/src/utils/theme';

type ReferralInfo = {
  code: string;
  invited_count: number;
  rewarded_count: number;
  max_referrals: number;
  bonus_sats: number;
  remaining_rewards: number;
  has_redeemed_inbound: boolean;
  share_text: string;
};

export default function Referral() {
  const router = useRouter();
  const { refresh } = useSession();
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [enteredCode, setEnteredCode] = useState('');
  const [redeeming, setRedeeming] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api('/referral');
      setInfo(r);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onShare = async () => {
    if (!info) return;
    try {
      await Share.share({ message: info.share_text });
    } catch (e: any) {
      notify('Sharing failed', e?.message ?? 'Try again');
    }
  };

  const onRedeem = async () => {
    const code = enteredCode.trim().toUpperCase();
    if (!code || code.length < 4) {
      notify('Invalid code', 'Please enter a valid referral code.');
      return;
    }
    setRedeeming(true);
    try {
      const r = await api('/referral/redeem', {
        method: 'POST',
        body: JSON.stringify({ referral_code: code }),
      });
      const awarded = Number(r?.bonus_sats || 0);
      if (awarded > 0) {
        notify(
          'Welcome bonus credited',
          `You received ${awarded} sats. Thank you for joining via a friend!`,
        );
      } else {
        notify('Code accepted', r?.message || 'No bonus was awarded.');
      }
      setEnteredCode('');
      await load();
      await refresh();
    } catch (e: any) {
      const msg = e?.message ?? 'Try again later';
      notify('Could not redeem code', msg);
    } finally {
      setRedeeming(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-btn" onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Invite Friends</Text>
        <View style={{ width: 40 }} />
      </View>

      {loading || !info ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1 }}
        >
          <ScrollView
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.bubble}>
              <Ionicons name="people" size={36} color={colors.primary} />
            </View>

            <Text style={styles.h1}>Enjoying the App? Tell Your Friends</Text>
            <Text style={styles.h2}>
              Share your code below with your friends. When they sign up and
              enter your unique code, you both earn a one-time reward of{' '}
              {info.bonus_sats} sats. Maximum {info.max_referrals} referrals.
            </Text>

            <View style={styles.codeCard}>
              <Text style={styles.codeLabel}>YOUR CODE</Text>
              <Text style={styles.code} testID="referral-code">
                {info.code}
              </Text>
              <Text style={styles.counterText} testID="referral-counter">
                Referrals used: {info.rewarded_count} / {info.max_referrals}
              </Text>
            </View>

            <TouchableOpacity
              testID="referral-share-btn"
              style={styles.share}
              onPress={onShare}
              activeOpacity={0.85}
            >
              <Ionicons name="share-social" size={18} color={colors.bg} />
              <Text style={styles.shareText}>Share your code</Text>
            </TouchableOpacity>

            {/* Code-entry input. Hidden once the user has redeemed an
                inbound code (only one inbound redemption per account). */}
            {!info.has_redeemed_inbound ? (
              <View style={styles.redeemCard}>
                <Text style={styles.redeemTitle}>{`Have a friend's code?`}</Text>
                <Text style={styles.redeemHint}>
                  {`Enter it once to claim your ${info.bonus_sats}-sat welcome bonus. One inbound code per account.`}
                </Text>
                <View style={styles.inputRow}>
                  <TextInput
                    testID="referral-input"
                    style={styles.input}
                    value={enteredCode}
                    onChangeText={(t) => setEnteredCode(t.replace(/\s/g, '').toUpperCase())}
                    placeholder="ENTER CODE"
                    placeholderTextColor={colors.textTertiary}
                    autoCapitalize="characters"
                    autoCorrect={false}
                    maxLength={16}
                    editable={!redeeming}
                  />
                  <TouchableOpacity
                    testID="referral-redeem-btn"
                    style={[
                      styles.redeemBtn,
                      (!enteredCode || redeeming) && styles.redeemBtnDisabled,
                    ]}
                    onPress={onRedeem}
                    disabled={!enteredCode || redeeming}
                    activeOpacity={0.85}
                  >
                    {redeeming ? (
                      <ActivityIndicator color={colors.bg} />
                    ) : (
                      <Text style={styles.redeemBtnText}>Redeem</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <View style={styles.redeemedBadge}>
                <Ionicons name="checkmark-circle" size={18} color={colors.primary} />
                <Text style={styles.redeemedText}>
                  {`You have already redeemed a friend's code.`}
                </Text>
              </View>
            )}

            <Text style={styles.fineprint}>
              Rewards are credited as sats. The BTC equivalent in USD will
              fluctuate with the live BTC price. Earnings are indicative
              and not guaranteed.
            </Text>
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
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
  content: { padding: spacing.lg, alignItems: 'center', paddingBottom: spacing.xl },
  bubble: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: colors.primaryDim,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  h1: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginTop: spacing.md,
    textAlign: 'center',
    letterSpacing: -0.5,
    paddingHorizontal: spacing.sm,
  },
  h2: {
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 6,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
    lineHeight: 18,
  },
  codeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    width: '100%',
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  codeLabel: { color: colors.textTertiary, fontSize: 11, fontWeight: '700', letterSpacing: 1.2 },
  code: {
    color: colors.primary,
    fontSize: 34,
    fontWeight: '800',
    fontFamily: fonts.mono,
    marginTop: 8,
    letterSpacing: 4,
  },
  counterText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '700',
    marginTop: spacing.md,
    fontFamily: fonts.mono,
  },
  share: {
    flexDirection: 'row',
    width: '100%',
    height: 52,
    marginTop: spacing.lg,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    ...shadows.glow,
  },
  shareText: { color: colors.bg, fontSize: 15, fontWeight: '800' },
  redeemCard: {
    width: '100%',
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  redeemTitle: { color: colors.text, fontSize: 15, fontWeight: '800' },
  redeemHint: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 17,
  },
  inputRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
    alignItems: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: colors.bg,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 46,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    fontFamily: fonts.mono,
    fontSize: 15,
    letterSpacing: 2,
  },
  redeemBtn: {
    height: 46,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    minWidth: 92,
  },
  redeemBtnDisabled: { opacity: 0.4 },
  redeemBtnText: { color: colors.bg, fontWeight: '800', fontSize: 14 },
  redeemedBadge: {
    flexDirection: 'row',
    gap: 8,
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primaryDim,
    alignItems: 'center',
  },
  redeemedText: { color: colors.text, fontSize: 13, fontWeight: '600', flex: 1 },
  fineprint: {
    color: colors.textTertiary,
    fontSize: 11,
    marginTop: spacing.lg,
    textAlign: 'center',
    lineHeight: 16,
    paddingHorizontal: spacing.sm,
  },
});
