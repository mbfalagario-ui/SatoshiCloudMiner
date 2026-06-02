import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';
import { api } from '@/src/utils/api';
import { colors, spacing, radius, fonts, shadows } from '@/src/utils/theme';
import { notify } from '@/src/utils/dialog';

type Thread = {
  id: string;
  user_id: string;
  user_email: string;
  status: 'open' | 'closed' | string;
  last_message_at?: string | null;
  last_message_preview?: string | null;
  last_message_from?: 'user' | 'admin' | null;
  unread_admin_count?: number;
  unread_user_count?: number;
};

type Message = {
  id: string;
  thread_id: string;
  sender: 'user' | 'admin';
  sender_email?: string;
  body: string;
  created_at: string;
  read_at?: string | null;
};

function formatStamp(iso?: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = diffMs / 60_000;
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${Math.floor(diffMin)}m ago`;
    if (diffMin < 60 * 24) return `${Math.floor(diffMin / 60)}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

export default function AdminSupport() {
  const insets = useSafeAreaInsets();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [totalUnread, setTotalUnread] = useState(0);
  const [openCount, setOpenCount] = useState(0);
  const [slaHours, setSlaHours] = useState(48);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Selected thread state
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const loadThreads = useCallback(async () => {
    try {
      const r = await api('/admin/support/threads');
      setThreads(r.threads || []);
      setTotalUnread(Number(r.total_unread_admin || 0));
      setOpenCount(Number(r.open_count || 0));
      if (typeof r.sla_hours === 'number') setSlaHours(r.sla_hours);
    } catch (e) {
      // quiet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  useFocusEffect(
    useCallback(() => {
      loadThreads();
      const t = setInterval(loadThreads, 15_000);
      return () => clearInterval(t);
    }, [loadThreads])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await loadThreads();
    setRefreshing(false);
  };

  const openThread = async (t: Thread) => {
    setSelectedThread(t);
    setLoadingDetail(true);
    setMessages([]);
    try {
      const r = await api(`/admin/support/threads/${t.user_id}`);
      setMessages(r.messages || []);
      // Refresh list so the unread badge clears immediately.
      loadThreads();
    } catch (e: any) {
      notify('Could not open thread', e?.message || 'Try again.');
    } finally {
      setLoadingDetail(false);
    }
  };

  const onReplySend = async () => {
    if (!selectedThread) return;
    const body = reply.trim();
    if (!body) return;
    setSending(true);
    try {
      const r = await api(`/admin/support/threads/${selectedThread.user_id}/reply`, {
        method: 'POST',
        body: JSON.stringify({ body }),
      });
      if (r?.message) setMessages((prev) => [...prev, r.message]);
      setReply('');
      // Refresh list metadata (last_message_at, preview).
      loadThreads();
    } catch (e: any) {
      notify('Could not send reply', e?.message || 'Try again.');
    } finally {
      setSending(false);
    }
  };

  const onCloseThread = async () => {
    if (!selectedThread) return;
    try {
      await api(`/admin/support/threads/${selectedThread.user_id}/close`, { method: 'POST' });
      loadThreads();
      setSelectedThread({ ...selectedThread, status: 'closed' });
      notify('Thread closed', 'You can re-open it any time by replying.');
    } catch (e: any) {
      notify('Close failed', e?.message || 'Try again.');
    }
  };

  // Auto-scroll detail to bottom when messages change.
  useEffect(() => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(t);
  }, [messages.length]);

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      {/* Stats header */}
      <View style={styles.statsHeader}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{totalUnread}</Text>
          <Text style={styles.statLabel}>UNREAD</Text>
        </View>
        <View style={styles.statDiv} />
        <View style={styles.stat}>
          <Text style={styles.statValue}>{openCount}</Text>
          <Text style={styles.statLabel}>OPEN</Text>
        </View>
        <View style={styles.statDiv} />
        <View style={styles.stat}>
          <Text style={styles.statValue}>{slaHours}h</Text>
          <Text style={styles.statLabel}>SLA</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : (
        <FlatList
          data={threads}
          keyExtractor={(t) => t.id}
          contentContainerStyle={{ padding: spacing.md, paddingBottom: spacing.xl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          ListEmptyComponent={
            <View style={styles.emptyBlock}>
              <Ionicons name="chatbubble-ellipses-outline" size={32} color={colors.textTertiary} />
              <Text style={styles.emptyText}>No support threads yet.</Text>
            </View>
          }
          renderItem={({ item }) => {
            const unread = Number(item.unread_admin_count || 0);
            const closed = item.status === 'closed';
            return (
              <TouchableOpacity
                testID={`admin-thread-${item.user_id}`}
                onPress={() => openThread(item)}
                style={[styles.threadRow, unread > 0 && styles.threadRowUnread]}
                activeOpacity={0.7}
              >
                <View style={styles.threadAvatar}>
                  <Text style={styles.threadAvatarText}>
                    {(item.user_email || '?').slice(0, 1).toUpperCase()}
                  </Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={styles.threadEmail} numberOfLines={1}>{item.user_email}</Text>
                    {closed ? (
                      <View style={styles.closedChip}>
                        <Text style={styles.closedChipText}>CLOSED</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.threadPreview} numberOfLines={1}>
                    {item.last_message_from === 'admin' ? 'You: ' : ''}
                    {item.last_message_preview || '(no messages yet)'}
                  </Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={styles.threadStamp}>{formatStamp(item.last_message_at)}</Text>
                  {unread > 0 ? (
                    <View style={styles.unreadBadge}>
                      <Text style={styles.unreadBadgeText}>{unread > 99 ? '99+' : unread}</Text>
                    </View>
                  ) : null}
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}

      {/* Detail modal */}
      <Modal
        visible={!!selectedThread}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setSelectedThread(null)}
        statusBarTranslucent
      >
        <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
        {/* IMPORTANT: <SafeAreaView> inside a <Modal> does NOT inherit the
            root safe-area context on iOS, so the header was overlapping
            the status bar / back button became unreachable (Build #15 bug
            from TestFlight screenshot). Read insets via the hook from the
            parent context and apply paddingTop manually. */}
        <View style={[styles.modalRoot, { paddingTop: insets.top }]}>
          <KeyboardAvoidingView
            style={{ flex: 1 }}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
          >
            <View style={styles.detailHeader}>
              <TouchableOpacity
                testID="admin-thread-back-btn"
                onPress={() => setSelectedThread(null)}
                hitSlop={{ top: 16, bottom: 16, left: 16, right: 16 }}
                style={styles.backBtn}
              >
                <Ionicons name="chevron-back" size={26} color={colors.text} />
              </TouchableOpacity>
              <View style={{ flex: 1, marginLeft: 4 }}>
                <Text style={styles.detailTitle} numberOfLines={1}>
                  {selectedThread?.user_email}
                </Text>
                <Text style={styles.detailSub}>
                  {selectedThread?.status === 'closed' ? 'Thread closed' : `Reply within ${slaHours}h`}
                </Text>
              </View>
              {selectedThread?.status !== 'closed' ? (
                <TouchableOpacity onPress={onCloseThread} style={styles.closeBtn} hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}>
                  <Ionicons name="archive-outline" size={14} color={colors.textSecondary} />
                  <Text style={styles.closeBtnText}>Close</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            {loadingDetail ? (
              <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
            ) : (
              <ScrollView
                ref={scrollRef}
                contentContainerStyle={styles.detailScroll}
                keyboardShouldPersistTaps="handled"
              >
                {messages.length === 0 ? (
                  <View style={styles.emptyBlock}>
                    <Text style={styles.emptyText}>This user hasn&apos;t messaged yet. You can still start the conversation.</Text>
                  </View>
                ) : (
                  messages.map((m) => {
                    const mine = m.sender === 'admin';
                    return (
                      <View
                        key={m.id}
                        style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}
                      >
                        <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}>
                          {!mine ? <Text style={styles.bubbleAuthor}>USER</Text> : null}
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
            )}

            <View style={[styles.composer, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
              <TextInput
                testID="admin-reply-input"
                value={reply}
                onChangeText={setReply}
                placeholder={
                  selectedThread?.status === 'closed'
                    ? 'Sending will re-open this thread'
                    : 'Type your reply…'
                }
                placeholderTextColor={colors.textTertiary}
                style={styles.input}
                multiline
                maxLength={2000}
                editable={!sending}
              />
              <TouchableOpacity
                testID="admin-reply-send-btn"
                onPress={onReplySend}
                disabled={sending || !reply.trim()}
                style={[styles.sendBtn, (sending || !reply.trim()) && { opacity: 0.4 }]}
              >
                {sending ? (
                  <ActivityIndicator color={colors.bg} />
                ) : (
                  <Ionicons name="send" size={18} color={colors.bg} />
                )}
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },

  statsHeader: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
  },
  stat: { flex: 1, alignItems: 'center' },
  statDiv: { width: 1, backgroundColor: colors.border },
  statValue: { color: colors.primary, fontSize: 20, fontWeight: '800', fontFamily: fonts.mono },
  statLabel: { color: colors.textTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700', marginTop: 2 },

  emptyBlock: { padding: spacing.xl, alignItems: 'center', gap: spacing.sm },
  emptyText: { color: colors.textSecondary, fontSize: 13, textAlign: 'center' },

  threadRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.sm + 2,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: spacing.sm,
  },
  threadRowUnread: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(16,185,129,0.06)',
  },
  threadAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  threadAvatarText: { color: colors.text, fontWeight: '800' },
  threadEmail: { color: colors.text, fontSize: 13, fontWeight: '700' },
  threadPreview: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  threadStamp: { color: colors.textTertiary, fontSize: 10, marginBottom: 4 },

  unreadBadge: {
    minWidth: 20,
    height: 20,
    paddingHorizontal: 6,
    borderRadius: 10,
    backgroundColor: '#ef4444',
    alignItems: 'center',
    justifyContent: 'center',
  },
  unreadBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },
  closedChip: {
    backgroundColor: 'rgba(148,163,184,0.18)',
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  closedChipText: { color: colors.textTertiary, fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },

  // Detail modal
  modalRoot: { flex: 1, backgroundColor: colors.bg },
  detailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
    minHeight: 52,
  },
  backBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: -8,
  },
  detailTitle: { color: colors.text, fontSize: 15, fontWeight: '800' },
  detailSub: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  closeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  closeBtnText: { color: colors.textSecondary, fontSize: 11, fontWeight: '700' },
  detailScroll: { flexGrow: 1, padding: spacing.md, gap: spacing.sm },

  // Bubbles
  row: { flexDirection: 'row', marginVertical: 4 },
  rowMine: { justifyContent: 'flex-end' },
  rowTheirs: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderRadius: 18,
  },
  bubbleMine: { backgroundColor: colors.primary, borderBottomRightRadius: 4 },
  bubbleTheirs: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  bubbleAuthor: { fontSize: 9, fontWeight: '800', color: colors.primary, letterSpacing: 1, marginBottom: 4 },
  bubbleBody: { color: colors.text, fontSize: 14, lineHeight: 20 },
  bubbleStamp: { fontSize: 10, color: colors.textTertiary, marginTop: 4, alignSelf: 'flex-end' },

  // Composer (admin)
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
