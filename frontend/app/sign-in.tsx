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

export default function SignIn() {
  const router = useRouter();
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    if (!email.includes('@') || password.length < 6) {
      Alert.alert('Invalid input', 'Please enter a valid email and a password of at least 6 characters.');
      return;
    }
    setBusy(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
      router.replace('/(tabs)');
    } catch (e: any) {
      Alert.alert('Sign in failed', e?.message ?? 'Please try again.');
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

          <Text style={styles.title}>Welcome back</Text>
          <Text style={styles.subtitle}>Sign in to continue mining.</Text>

          <View style={styles.field}>
            <Text style={styles.label}>Email</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="mail-outline" size={18} color={colors.textTertiary} />
              <TextInput
                testID="sign-in-email-input"
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
                testID="sign-in-password-input"
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

          <TouchableOpacity
            testID="sign-in-submit-btn"
            style={[styles.primaryBtn, busy && { opacity: 0.7 }]}
            onPress={onSubmit}
            disabled={busy}
            activeOpacity={0.85}
          >
            {busy ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Text style={styles.primaryBtnText}>Sign In</Text>
            )}
          </TouchableOpacity>

          <View style={styles.bottomRow}>
            <Text style={styles.muted}>No account?</Text>
            <TouchableOpacity testID="to-sign-up-link" onPress={() => router.replace('/sign-up')}>
              <Text style={styles.link}> Create one</Text>
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
  title: {
    color: colors.text,
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.8,
  },
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
  input: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    paddingVertical: 0,
  },
  primaryBtn: {
    backgroundColor: colors.primary,
    height: 52,
    borderRadius: radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.md,
    ...shadows.glow,
  },
  primaryBtnText: {
    color: colors.bg,
    fontSize: 16,
    fontWeight: '800',
  },
  bottomRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  muted: { color: colors.textSecondary, fontSize: 14 },
  link: { color: colors.primary, fontSize: 14, fontWeight: '700' },
});
