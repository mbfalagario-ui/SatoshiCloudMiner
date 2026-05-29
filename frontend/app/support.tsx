import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { useSession } from '@/src/ctx';
import { colors, radius, spacing, fonts } from '@/src/utils/theme';

type FAQ = { id: string; q: string; a: string };
type Msg = { id: string; sender: 'user' | 'admin'; body: string; created_at: string; ai_generated?: boolean };

export default function Support() {
  const router = useRouter();
  const { user } = useSession();
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [thread, setThread] = useState<Msg[]>([]);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const loadFaqs = useCallback(async () => {
    try {
      const r = await api('/faqs', { auth: false });
      setFaqs(r.faqs || []);
    } catch {}
  }, []);

  const loadThread = useCallback(async () => {
    try {
      const r = await api('/support/thread');
      setThread(r.messages || []);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    } catch {}
  }, []);

  useEffect(() => {
    loadFaqs();
    loadThread();
  }, [loadFaqs, loadThread]);

  const send = async () => {
    const text = body.trim();
    if (!text) return;
    setBody('');
    setBusy(true);
    try {
      await api('/support/ai-reply', { method: 'POST', body: JSON.stringify({ body: text }) });
      await loadThread();
    } catch (e: any) {
      // ignore
    } finally {
      setBusy(false);
    }
  };

  const useSuggestion = (q: string) => {
    setBody(q);
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={styles.title}>Support</Text>
          <Text style={styles.subtitle}>{user?.ad_free ? 'Priority queue · 24h SLA' : 'AI + human team'}</Text>
        </View>
        <View style={{ width: 32 }} />
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView ref={scrollRef} contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          {/* FAQ tiles */}
          {thread.length === 0 ? (
            <View>
              <Text style={styles.section}>Quick answers</Text>
              {faqs.slice(0, 8).map((f) => (
                <TouchableOpacity
                  key={f.id}
                  style={styles.faqTile}
                  onPress={() => setExpanded(expanded === f.id ? null : f.id)}
                  testID={`faq-${f.id}`}
                >
                  <View style={styles.faqRow}>
                    <Text style={styles.faqQ}>{f.q}</Text>
                    <Ionicons name={expanded === f.id ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
                  </View>
                  {expanded === f.id ? (
                    <View>
                      <Text style={styles.faqA}>{f.a}</Text>
                      <TouchableOpacity onPress={() => useSuggestion(f.q)} style={styles.faqAskBtn}>
                        <Text style={styles.faqAskText}>Ask follow-up ›</Text>
                      </TouchableOpacity>
                    </View>
                  ) : null}
                </TouchableOpacity>
              ))}
              <View style={styles.hint}>
                <Ionicons name="sparkles" size={14} color={colors.primary} />
                <Text style={styles.hintText}>Or type your question below — our AI assistant + team will respond.</Text>
              </View>
            </View>
          ) : (
            <View>
              {thread.map((m) => (
                <View key={m.id} style={[styles.bubble, m.sender === 'user' ? styles.userBubble : styles.adminBubble]}>
                  {m.sender === 'admin' ? (
                    <View style={styles.adminTag}>
                      <Ionicons name={m.ai_generated ? 'sparkles' : 'shield-checkmark'} size={10} color={m.ai_generated ? colors.secondary : colors.primary} />
                      <Text style={[styles.adminLabel, m.ai_generated && { color: colors.secondary }]}>
                        {m.ai_generated ? 'AI assistant' : 'Hashrate Support'}
                      </Text>
                    </View>
                  ) : null}
                  <Text style={[styles.bubbleText, m.sender === 'user' ? { color: colors.bg } : { color: colors.text }]}>{m.body}</Text>
                </View>
              ))}
              {busy ? (
                <View style={[styles.bubble, styles.adminBubble]}>
                  <ActivityIndicator size="small" color={colors.primary} />
                </View>
              ) : null}
            </View>
          )}
          <View style={{ height: 80 }} />
        </ScrollView>

        <View style={styles.composer}>
          <TextInput
            value={body}
            onChangeText={setBody}
            placeholder="Type your question..."
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            multiline
            testID="support-input"
          />
          <TouchableOpacity onPress={send} disabled={!body.trim() || busy} style={[styles.sendBtn, (!body.trim() || busy) && styles.sendMuted]} testID="support-send-btn">
            <Ionicons name="arrow-up" size={18} color={colors.bg} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  back: { width: 32, height: 32, justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 17, fontWeight: '800' },
  subtitle: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  scroll: { padding: spacing.lg },
  section: { color: colors.textSecondary, fontSize: 12, fontWeight: '800', letterSpacing: 1, marginBottom: spacing.sm, textTransform: 'uppercase' },
  faqTile: { padding: spacing.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft, borderRadius: radius.md, marginBottom: 8 },
  faqRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  faqQ: { flex: 1, color: colors.text, fontSize: 13, fontWeight: '700' },
  faqA: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: 8 },
  faqAskBtn: { marginTop: 8 },
  faqAskText: { color: colors.primary, fontSize: 11, fontWeight: '800' },
  hint: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.md, padding: spacing.sm },
  hintText: { color: colors.textSecondary, fontSize: 11, fontStyle: 'italic' },
  bubble: { padding: 12, borderRadius: 14, marginVertical: 4, maxWidth: '85%' },
  userBubble: { backgroundColor: colors.primary, alignSelf: 'flex-end' },
  adminBubble: { backgroundColor: colors.surface, alignSelf: 'flex-start', borderWidth: 1, borderColor: colors.borderSoft },
  adminTag: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  adminLabel: { color: colors.primary, fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  bubbleText: { fontSize: 13, lineHeight: 18 },
  composer: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderTopWidth: 1, borderTopColor: colors.borderSoft, backgroundColor: colors.bg },
  input: { flex: 1, color: colors.text, fontSize: 13, backgroundColor: colors.surface, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 10, maxHeight: 100 },
  sendBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  sendMuted: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderSoft },
});
