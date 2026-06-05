/**
 * Top-level React ErrorBoundary.
 *
 * Catches errors thrown during the React render/commit phases. The
 * `installErrorHandlers()` function in `src/utils/errorHandler.ts`
 * catches everything ELSE (uncaught JS errors, Promise rejections);
 * this Boundary is the last line of defence for component-tree
 * errors that would otherwise propagate to React Native's native
 * `RCTExceptionsManager` and abort the app on iOS 26.5 beta.
 *
 * Design (per GPT-calibrated Build #33 plan):
 *   - DO record/persist the error via recordRenderError so the next
 *     drain pass POSTs it to /api/telemetry/crash.
 *   - DO render a fallback UI explaining what happened.
 *   - DO NOT auto-recover by re-mounting the tree (that can corrupt
 *     state). User manually closes & reopens the app.
 *   - iOS forbids programmatic exit/restart; the UI tells the user
 *     what to do.
 */
import React from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { recordRenderError } from '@/src/utils/errorHandler';

type Props = { children: React.ReactNode };
type State = {
  hasError: boolean;
  message: string;
  stack: string;
};

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: '', stack: '' };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: String(error?.message ?? error ?? 'Unknown error'),
      stack: String(error?.stack ?? ''),
    };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    try {
      recordRenderError(error, info.componentStack);
    } catch {}
    // Also log so the dev console captures it.
    // eslint-disable-next-line no-console
    console.warn('[ErrorBoundary] caught:', error?.message);
  }

  reset = () => {
    // Best-effort soft reset. NOT a true restart — RN has no portable
    // API for that. The fallback screen primarily instructs the user
    // to close & reopen the app.
    this.setState({ hasError: false, message: '', stack: '' });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <View style={styles.root}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.subtitle}>
            The app encountered an unexpected error. Please close the app
            completely (swipe up from the bottom) and reopen it.
          </Text>
          <View style={styles.errorBox}>
            <Text style={styles.errorLabel}>Error</Text>
            <Text style={styles.errorMessage}>{this.state.message}</Text>
          </View>
          <TouchableOpacity onPress={this.reset} style={styles.button}>
            <Text style={styles.buttonText}>Try to recover</Text>
          </TouchableOpacity>
          <Text style={styles.support}>
            This error has been reported automatically. If it keeps happening,
            email support@hashratecloudminer.com with the time you saw it.
          </Text>
        </ScrollView>
      </View>
    );
  }
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B0E14' },
  content: { padding: 24, paddingTop: 80 },
  title: { color: '#FFFFFF', fontSize: 22, fontWeight: '800', marginBottom: 8 },
  subtitle: { color: '#9BA0AC', fontSize: 14, lineHeight: 20, marginBottom: 24 },
  errorBox: {
    backgroundColor: '#1F2633',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#FF4757',
  },
  errorLabel: { color: '#FF4757', fontSize: 11, fontWeight: '800', marginBottom: 6, letterSpacing: 0.5 },
  errorMessage: { color: '#FFFFFF', fontSize: 13, fontFamily: 'Menlo' },
  button: {
    backgroundColor: '#00FFA3',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 14,
    alignItems: 'center',
    marginBottom: 24,
  },
  buttonText: { color: '#0B0E14', fontSize: 14, fontWeight: '800' },
  support: { color: '#666B75', fontSize: 11, lineHeight: 16, textAlign: 'center' },
});
