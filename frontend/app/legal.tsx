import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fonts } from '@/src/utils/theme';

type Tab = 'terms' | 'privacy';

export default function Legal() {
  const router = useRouter();
  const params = useLocalSearchParams<{ section?: string }>();
  const initial: Tab = params?.section === 'privacy' ? 'privacy' : 'terms';
  const [tab, setTab] = useState<Tab>(initial);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back} testID="back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>
          {tab === 'terms' ? 'Terms of Service' : 'Privacy Policy'}
        </Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.tabsRow}>
        <TouchableOpacity
          style={[styles.tab, tab === 'terms' && styles.tabActive]}
          onPress={() => setTab('terms')}
        >
          <Text style={[styles.tabText, tab === 'terms' && styles.tabTextActive]}>Terms</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'privacy' && styles.tabActive]}
          onPress={() => setTab('privacy')}
        >
          <Text style={[styles.tabText, tab === 'privacy' && styles.tabTextActive]}>Privacy</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {tab === 'terms' ? <Terms /> : <Privacy />}
        <Text style={styles.lastUpdated}>Last updated: June 2026</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.h2}>{title}</Text>
      {children}
    </View>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <Text style={styles.p}>{children}</Text>;
}

function Terms() {
  return (
    <>
      <Section title="1. About Hashrate Cloud Miner">
        <P>
          {`Hashrate Cloud Miner (the "App") is a simulated cloud-hashrate experience. The App does NOT perform any cryptocurrency mining on your device or any third-party device. All hashrate values shown inside the App are virtual indicators that drive the App's internal reward simulation. The App is not a regulated investment product, an exchange, a wallet, or a money-transmission service.`}
        </P>
      </Section>

      <Section title="2. No Guaranteed Earnings">
        <P>
          All earnings figures (sats accrual rates, BTC equivalents, USD
          equivalents) displayed in the App are INDICATIVE only and are
          NOT guaranteed. Real-world value of Bitcoin (BTC) and Satoshis
          (sats) fluctuates continuously based on market conditions outside
          our control. Past or simulated performance does not predict
          future outcomes. You acknowledge that you may receive less than
          the indicative amounts displayed at any moment, or nothing at
          all if you do not meet redemption thresholds.
        </P>
      </Section>

      <Section title="3. In-App Purchases (Boosters)">
        <P>
          Boosters sold inside the App (e.g. Pro Booster, Elite Booster,
          Ultra Booster, Mega Booster, Giga Booster, Titan Booster,
          Colossus Booster) are one-time, permanent, stackable hashrate
          add-ons. Each Booster adds the displayed GH/s amount to your
          account immediately and permanently. Boosters do not expire and
          do not pay a guaranteed daily return. Pricing is shown in your
          local Apple App Store currency. All purchases are processed by
          Apple and are subject to the Apple Media Services Terms.
          Boosters are consumed at the time of purchase and are not
          refundable through the App; refund requests must be made
          directly to Apple via Report a Problem.
        </P>
      </Section>

      <Section title="4. Ad-Free + Priority Support">
        <P>
          The optional Ad-Free + Priority Support purchase removes
          interstitial advertising from your account and routes your
          support requests to a priority queue with a target 24-hour
          response window. Rewarded video opt-in ads remain available
          regardless of this purchase, since they grant in-app rewards
          you choose to watch.
        </P>
      </Section>

      <Section title="5. Referral Program">
        <P>
          You may share your unique referral code with friends. When a new
          user signs up using your code or enters your code from the
          Invite Friends screen, both of you receive a one-time bonus of
          1500 sats. You may earn this bonus on a maximum of 10 successful
          referrals per account. Self-referral, duplicate redemption, and
          repeated claims by the same account are not permitted. Bonuses
          may be revoked at our discretion if abuse, automation, or
          fraudulent activity is detected.
        </P>
      </Section>

      <Section title="6. Rewarded Ads and Daily Check-In">
        <P>
          The App provides free pathways to earn small amounts of
          simulated hashrate without purchasing: opt-in rewarded video
          ads (served via Google AdMob) and a daily check-in. These
          rewards are also indicative and not guaranteed. Daily caps
          apply and may change without notice.
        </P>
      </Section>

      <Section title="7. Withdrawal / Redemption">
        <P>
          Once your balance reaches the minimum redemption threshold
          displayed inside the App, you may request a Bitcoin Lightning
          payout to a Lightning address you provide. Payouts are net of
          network and processing fees. We are not responsible for invalid
          Lightning addresses, blocked Lightning channels, or delays
          caused by third-party Lightning routing.
        </P>
      </Section>

      <Section title="8. Account, Eligibility, and Suspension">
        <P>
          You must be at least the age of majority in your jurisdiction
          to use the App. One account per person. We may suspend or
          terminate accounts for abuse, fraud, breach of these Terms, or
          to comply with law, with or without notice.
        </P>
      </Section>

      <Section title="9. Account Deletion">
        <P>
          You may permanently delete your account at any time from
          Profile → Settings → Delete Account. Deletion removes your
          user document, transaction history, machine records, support
          messages, and any other user-scoped data from our database.
          Deletion is immediate and irreversible.
        </P>
      </Section>

      <Section title="10. Disclaimers and Liability">
        <P>
          {`The App is provided "as is" without warranties of any kind, express or implied. To the maximum extent permitted by law, we disclaim liability for indirect, incidental, consequential, punitive, or special damages, including loss of profits, loss of data, or loss of crypto-asset value.`}
        </P>
      </Section>

      <Section title="11. Contact">
        <P>
          Questions: support@hashratecloudminer.com or use Profile →
          Premium Support inside the App.
        </P>
      </Section>
    </>
  );
}

function Privacy() {
  return (
    <>
      <Section title="1. What We Collect">
        <P>
          • Account: email address and a securely hashed password.{'\n'}
          • Purchases: Apple transaction IDs and product IDs that you
          buy through the App.{'\n'}
          • Wallet: any Lightning address you submit for a withdrawal.
          {'\n'}
          • Activity: in-app actions needed to operate the App (daily
          check-ins, rewarded-ad views, support messages, referral
          relationships).{'\n'}
          • Device-level identifiers required by Google AdMob for
          rewarded/interstitial advertising (subject to your iOS App
          Tracking Transparency choice).
        </P>
      </Section>

      <Section title="2. What We Do NOT Collect">
        <P>
          We do not collect your name, address, phone number, contact
          list, photos, microphone, calendar, health data, or location.
          We do not run any on-device cryptocurrency mining and do not
          access device CPU/GPU for hashing.
        </P>
      </Section>

      <Section title="3. How We Use Data">
        <P>
          {`To operate your account, validate Apple In-App Purchases with Apple's App Store Server API, credit Booster purchases, run the referral program, process withdrawals you initiate, and provide customer support.`}
        </P>
      </Section>

      <Section title="4. Advertising">
        <P>
          The App uses Google AdMob to serve rewarded video and
          (post-approval) interstitial advertising. AdMob may use device
          identifiers and aggregated diagnostic data to deliver ads.
          When iOS App Tracking Transparency prompts you, your answer
          controls whether personalised ads are delivered. You can
          change this at any time from iOS Settings → Privacy &
          Security → Tracking.
        </P>
      </Section>

      <Section title="5. Data Sharing">
        <P>
          We share only the minimum data needed with: Apple (purchase
          validation), Google AdMob (advertising), our hosting provider
          Fly.io (server execution), and MongoDB Atlas (database).
          We do not sell your data.
        </P>
      </Section>

      <Section title="6. Security">
        <P>
          {`Passwords are stored as bcrypt hashes. Apple receipts are validated through Apple's App Store Server API using ES256 JSON Web Tokens. All transport is over HTTPS.`}
        </P>
      </Section>

      <Section title="7. Account Deletion and Data Retention">
        <P>
          {`You may delete your account immediately from Profile → Settings → Delete Account. Deletion is permanent. We may retain hashed Apple transaction IDs in a fraud-prevention log for as long as required by Apple's terms; this log contains no personal data.`}
        </P>
      </Section>

      <Section title="8. Children">
        <P>
          The App is not directed to children under 13 and we do not
          knowingly collect data from children. If you believe a child
          has registered, contact us and we will delete the account.
        </P>
      </Section>

      <Section title="9. Changes to This Policy">
        <P>
          We may update this Privacy Policy. Material changes will be
          shown inside the App and dated below.
        </P>
      </Section>

      <Section title="10. Contact">
        <P>support@hashratecloudminer.com</P>
      </Section>
    </>
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
  tabsRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    alignItems: 'center',
  },
  tabActive: { backgroundColor: colors.primaryDim, borderColor: colors.primary },
  tabText: { color: colors.textSecondary, fontWeight: '700', fontSize: 13 },
  tabTextActive: { color: colors.primary },
  scroll: { padding: spacing.lg, paddingBottom: spacing.xl },
  section: { marginBottom: spacing.lg },
  h2: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '800',
    marginBottom: 6,
    letterSpacing: -0.3,
  },
  p: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    fontFamily: fonts.body,
  },
  lastUpdated: {
    color: colors.textTertiary,
    fontSize: 11,
    marginTop: spacing.md,
    textAlign: 'center',
  },
});
