import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, spacing, radius, shadows } from '@/src/utils/theme';
import { useSession } from '@/src/ctx';

export default function SignUp() {
  const router = useRouter();
  const { signUp } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [referral, setReferral] = useState('');
  const [show, setShow] = useState(false);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    const trimmedEmail = email.trim().toLowerCase();
    const trimmedRef = referral.trim();

    // F2 — Proper email validation (matches "x@y.z" style, blocks blanks/typos).
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    if (!emailRe.test(trimmedEmail)) {
      Alert.alert(
        'Invalid email',
        'Please enter a valid email address (e.g. you@example.com).',
      );
      return;
    }
    if (password.length < 6) {
      Alert.alert(
        'Password too short',
        'Please use at least 6 characters.',
      );
      return;
    }
    if (password.length > 128) {
      Alert.alert(
        'Password too long',
        'Please use 128 characters or fewer.',
      );
      return;
    }
    if (!agree) {
      Alert.alert(
        'Terms required',
        'Please accept the Terms of Service and Privacy Policy.',
      );
      return;
    }
    setBusy(true);
    try {
      await signUp(trimmedEmail, password, trimmedRef || undefined);
      router.replace('/(tabs)');
    } catch (e: any) {
      // F3 — Surface the backend's specific reason instead of a generic alert.
      const reason =
        e?.message ||
        e?.detail ||
        'Please check your email and password, then try again.';
      Alert.alert('Sign up failed', String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity
            testID="back-btn"
            onPress={() => router.back()}
            style={styles.back}
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>

          <Text style={styles.title}>Create your account</Text>
          <Text style={styles.subtitle}>Sign up and claim a free Welcome Miner.</Text>

          <View style={styles.field}>
            <Text style={styles.label}>Email</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="mail-outline" size={18} color={colors.textTertiary} />
              <TextInput
                testID="sign-up-email-input"
                placeholder="you@example.com"
                placeholderTextColor={colors.textTertiary}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
                value={email}
                onChangeText={setEmail}
                style={styles.input}
              />
            </View>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Password</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="lock-closed-outline" size={18} color={colors.textTertiary} />
              <TextInput
                testID="sign-up-password-input"
                placeholder="At least 6 characters"
                placeholderTextColor={colors.textTertiary}
                autoCapitalize="none"
                secureTextEntry={!show}
                value={password}
                onChangeText={setPassword}
                style={styles.input}
              />
              <TouchableOpacity onPress={() => setShow((v) => !v)}>
                <Ionicons
                  name={show ? 'eye-off-outline' : 'eye-outline'}
                  size={18}
                  color={colors.textTertiary}
                />
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Referral code (optional)</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="gift-outline" size={18} color={colors.textTertiary} />
              <TextInput
                testID="sign-up-referral-input"
                placeholder="E.g. AB12CDE"
                placeholderTextColor={colors.textTertiary}
                autoCapitalize="characters"
                value={referral}
                onChangeText={setReferral}
                style={styles.input}
              />
            </View>
          </View>

          <TouchableOpacity
            testID="agree-checkbox"
            style={styles.agreeRow}
            onPress={() => setAgree((v) => !v)}
            activeOpacity={0.7}
          >
            <View style={[styles.checkbox, agree && styles.checkboxOn]}>
              {agree && <Ionicons name="checkmark" size={14} color={colors.bg} />}
            </View>
            <Text style={styles.agreeText}>
              I agree to the{' '}
              <Text style={styles.link} onPress={() => router.push('/legal?doc=terms')}>
                Terms of Service
              </Text>{' '}
              and{' '}
              <Text style={styles.link} onPress={() => router.push('/legal?doc=privacy')}>
                Privacy Policy
              </Text>
              .
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            testID="sign-up-submit-btn"
            style={[styles.primaryBtn, busy && { opacity: 0.7 }]}
            onPress={onSubmit}
            disabled={busy}
            activeOpacity={0.85}
          >
            {busy ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Text style={styles.primaryBtnText}>Create Account</Text>
            )}
          </TouchableOpacity>

          <View style={styles.bottomRow}>
            <Text style={styles.muted}>Have an account?</Text>
            <TouchableOpacity testID="to-sign-in-link" onPress={() => router.replace('/sign-in')}>
              <Text style={styles.link}> Sign in</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  back: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  title: { color: colors.text, fontSize: 32, fontWeight: '800', letterSpacing: -0.8 },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 15,
    marginTop: spacing.xs,
    marginBottom: spacing.xl,
  },
  field: { marginBottom: spacing.md },
  label: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: spacing.sm,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
    height: 52,
  },
  input: { flex: 1, color: colors.text, fontSize: 15, paddingVertical: 0 },
  agreeRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.border,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  checkboxOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  agreeText: { flex: 1, color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  primaryBtn: {
    backgroundColor: colors.primary,
    height: 52,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    ...shadows.glow,
  },
  primaryBtnText: { color: colors.bg, fontSize: 16, fontWeight: '800' },
  bottomRow: { flexDirection: 'row', justifyContent: 'center', marginTop: spacing.lg },
  muted: { color: colors.textSecondary, fontSize: 14 },
  link: { color: colors.primary, fontSize: 14, fontWeight: '700' },
});
