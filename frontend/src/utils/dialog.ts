import { Alert, Platform } from 'react-native';

type Btn = { text: string; style?: 'cancel' | 'destructive' | 'default'; onPress?: () => void };

// Cross-platform confirm dialog. On web, Alert.alert is a no-op for multi-button
// dialogs, so we fall back to window.confirm.
export function confirmDialog(title: string, message: string, onConfirm: () => void, confirmLabel = 'OK') {
  if (Platform.OS === 'web') {
    // window.confirm is synchronous on web
    if (typeof window !== 'undefined' && window.confirm(`${title}\n\n${message}`)) {
      onConfirm();
    }
    return;
  }
  Alert.alert(title, message, [
    { text: 'Cancel', style: 'cancel' },
    { text: confirmLabel, style: 'destructive', onPress: onConfirm },
  ]);
}

export function notify(title: string, message?: string) {
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined') {
      window.alert(message ? `${title}\n\n${message}` : title);
    }
    return;
  }
  Alert.alert(title, message);
}
