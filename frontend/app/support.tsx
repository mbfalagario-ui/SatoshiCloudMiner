import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, shadows } from '@/src/utils/theme';
import { notify } from '@/src/utils/dialog';

type Message = {
  id: string;
  thread_id: string;
  sender: 'user' | 'admin';
  sender_email?: string;
  body: string;
  created_at: string;
  read_at?: string | null;
};

type Thread = {
  id: string;
  status: 'open' | 'closed' | string;
  last_message_at?: string | null;
  last_message_from?: 'user' | 'admin' | null;
  unread_user_count?: number;
  unread_admin_count?: number;
};

function formatStamp(iso: string): string {
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = diffMs / 60_000;
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${Math.floor(diffMin)}m ago`;
    if (diffMin < 60 * 24) return `${Math.floor(diffMin / 60)}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  } catch {
    return iso;
  }
}

export default function SupportScreen() {
  const router = useRouter();
  const [thread, setThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [slaHours, setSlaHours] = useState(48);
  const scrollRef = useRef<ScrollView>(null);

  const load = useCallback(async () => {
    try {
      const r = await api('/support/thread');
      setThread(r.thread || null);
      setMessages(r.messages || []);
      if (typeof r.sla_hours === 'number') setSlaHours(r.sla_hours);
    } catch (e: any) {
      // quiet; the screen still works empty
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Refresh on focus + every 12s while the screen is foregrounded so a reply
  // from the operator lands without manual pull-to-refresh.
  useFocusEffect(
    useCallback(() => {
      load();
      const t = setInterval(load, 12_000);
      return () => clearInterval(t);
    }, [load])
  );

  // Auto-scroll to bottom whenever message list grows.
  useEffect(() => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(t);
  }, [messages.length]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onSend = async () => {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    try {
      const r = await api('/support/messages', {
        method: 'POST',
        body: JSON.stringify({ body }),
      });
      if (r?.message) {
        setMessages((prev) => [...prev, r.message]);
      }
      setDraft('');
    } catch (e: any) {
      notify('Could not send', e?.message || 'Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Premium Support</Text>
            <Text style={styles.subtitle}>
              {thread?.status === 'closed' ? 'Thread closed by operator' : `We reply within ${slaHours} hours`}
            </Text>
          </View>
          <View style={styles.statusDot} />
        </View>

        {/* Message list */}
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          keyboardShouldPersistTaps="handled"
        >
          {messages.length === 0 ? (
            <View style={styles.emptyBlock}>
              <Ionicons name="chatbubble-ellipses" size={36} color={colors.primary} />
              <Text style={styles.emptyTitle}>Send us your first message</Text>
              <Text style={styles.emptyBody}>
                Tell us how we can help. Our team responds within {slaHours} hours, Monday–Sunday.
              </Text>
            </View>
          ) : (
            messages.map((m) => {
              const mine = m.sender === 'user';
              return (
                <View
                  key={m.id}
                  testID={`support-msg-${m.id}`}
                  style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}
                >
                  <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}>
                    {!mine ? (
                      <Text style={styles.bubbleAuthor}>OPERATOR</Text>
                    ) : null}
                    <Text style={[styles.bubbleBody, mine && { color: colors.bg }]}>{m.body}</Text>
                    <Text style={[styles.bubbleStamp, mine && { color: 'rgba(11,14,20,0.6)' }]}>
                      {formatStamp(m.created_at)}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </ScrollView>

        {/* Composer */}
        <View style={styles.composer}>
          <TextInput
            testID="support-composer-input"
            value={draft}
            onChangeText={setDraft}
            placeholder={
              thread?.status === 'closed'
                ? 'Send a new message to reopen the thread'
                : 'Type your message…'
            }
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            multiline
            maxLength={2000}
            editable={!sending}
          />
          <TouchableOpacity
            testID="support-send-btn"
            onPress={onSend}
            disabled={sending || !draft.trim()}
            style={[styles.sendBtn, (sending || !draft.trim()) && { opacity: 0.4 }]}
          >
            {sending ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Ionicons name="send" size={18} color={colors.bg} />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
  },
  title: { color: colors.text, fontSize: 16, fontWeight: '800' },
  subtitle: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  scroll: {
    flexGrow: 1,
    padding: spacing.md,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  emptyBlock: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    gap: spacing.sm,
  },
  emptyTitle: { color: colors.text, fontSize: 16, fontWeight: '700', marginTop: spacing.sm },
  emptyBody: { color: colors.textSecondary, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  row: { flexDirection: 'row', marginVertical: 4 },
  rowMine: { justifyContent: 'flex-end' },
  rowTheirs: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderRadius: 18,
  },
  bubbleMine: {
    backgroundColor: colors.primary,
    borderBottomRightRadius: 4,
  },
  bubbleTheirs: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  bubbleAuthor: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 1,
    marginBottom: 4,
  },
  bubbleBody: { color: colors.text, fontSize: 14, lineHeight: 20 },
  bubbleStamp: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderSoft,
    backgroundColor: colors.bg,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 14,
    maxHeight: 140,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 44,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
