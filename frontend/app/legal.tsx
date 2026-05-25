import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/utils/theme';

const TERMS = `Last updated: February 2026

By using Satoshi Cloud Miner, you agree to these Terms of Service.

1. SERVICE DESCRIPTION
Satoshi Cloud Miner is a cloud computing simulation and monitoring tool. The application allows users to purchase virtual computing-power packages and track simulated performance metrics. Satoshi Cloud Miner is not a financial, investment, brokerage, or trading platform. We do not provide investment advice, and outcomes shown in the app are simulated based on configurable parameters that may change at any time.

2. ELIGIBILITY
You must be at least 18 years old to use Satoshi Cloud Miner. By creating an account, you represent that you meet this age requirement and have the legal capacity to enter into this agreement in your jurisdiction.

3. ACCOUNTS
You are responsible for keeping your credentials secure. You agree to notify us immediately of any unauthorized use of your account.

4. PURCHASES AND IN-APP PURCHASES
All purchases of computing-power packages within the App Store version of Satoshi Cloud Miner are processed through Apple In-App Purchase. Prices reflect operational and platform costs. Purchases are non-refundable except where required by applicable law or Apple's policies.

5. WITHDRAWALS
Withdrawal of accrued rewards is subject to minimum amounts, daily caps, and processing time. Submission of an invalid wallet address or destination may result in failed or unrecoverable transfers. Satoshi Cloud Miner is not responsible for losses caused by user-provided destination errors.

6. PROHIBITED USES
You may not use Satoshi Cloud Miner to violate applicable law, infringe third-party rights, attempt to gain unauthorized access to our systems, or engage in fraud.

7. DISCLAIMER
Satoshi Cloud Miner is provided "as is" without warranties of any kind. Results within the app are illustrative and depend on server status and operational conditions. We may modify, suspend, or terminate features at any time.

8. LIMITATION OF LIABILITY
To the maximum extent permitted by law, Satoshi Cloud Miner and its affiliates are not liable for indirect, incidental, special, consequential, or punitive damages arising from your use of the service.

9. CHANGES
We may update these Terms at any time. Material changes will be communicated in the app. Continued use after changes constitutes acceptance.

10. CONTACT
For questions, contact support@hashcloud.app.
`;

const PRIVACY = `Last updated: February 2026

This Privacy Policy explains how Satoshi Cloud Miner handles your information.

1. INFORMATION WE COLLECT
- Account: email address and an encrypted password hash.
- Usage: device type, app version, crash diagnostics, and feature interactions used to improve the product.
- Identifiers: a user ID and device-level identifier used for fraud prevention, abuse detection, and third-party advertising attribution where applicable.

2. HOW WE USE INFORMATION
We use information to operate and improve Satoshi Cloud Miner, deliver in-app rewards and notifications, prevent fraud, and comply with legal obligations.

3. THIRD-PARTY ADVERTISING
We may use third-party advertising partners. These partners may use identifiers to deliver and measure advertising performance. You can limit ad tracking through your device settings.

4. DATA STORAGE
Your data is stored on secure cloud infrastructure. Passwords are stored as bcrypt hashes only — we never see your plaintext password.

5. RETENTION
We retain account data while your account is active and for a reasonable period thereafter to satisfy legal and operational requirements.

6. YOUR CHOICES
You can request deletion of your account by contacting support@hashcloud.app. You can also limit data sharing for advertising purposes via iOS app tracking settings.

7. CHILDREN
Satoshi Cloud Miner is not intended for users under 18. We do not knowingly collect data from children.

8. INTERNATIONAL TRANSFERS
Your data may be processed in countries other than your own. We apply appropriate safeguards in line with applicable law.

9. SECURITY
We implement reasonable technical and organizational measures to protect your data. No system is perfectly secure; please use a strong, unique password.

10. CONTACT
For privacy questions or requests, contact privacy@hashcloud.app.
`;

export default function Legal() {
  const router = useRouter();
  const { doc } = useLocalSearchParams<{ doc?: string }>();
  const isPrivacy = doc === 'privacy';
  const title = isPrivacy ? 'Privacy Policy' : 'Terms of Service';
  const body = isPrivacy ? PRIVACY : TERMS;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-btn" onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>{title}</Text>
        <View style={{ width: 40 }} />
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.body}>{body}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.sm,
  },
  back: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface,
    justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: '800' },
  scroll: { padding: spacing.lg, paddingBottom: spacing.xxl },
  body: { color: colors.textSecondary, fontSize: 13, lineHeight: 20 },
});
