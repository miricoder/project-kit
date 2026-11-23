import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

export function Screen({ children }: { children: ReactNode }) {
  return <View style={styles.screen}><View style={styles.inner}>{children}</View></View>;
}

export function Button({ label, onPress, disabled }: { label: string; onPress(): void; disabled?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} disabled={disabled}
      style={({ pressed }) => [styles.button, (pressed || disabled) && styles.dim]}>
      <Text style={styles.buttonText}>{label}</Text>
    </Pressable>
  );
}

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0f1115', alignItems: 'center', justifyContent: 'center', padding: 16 },
  inner: { width: '100%', maxWidth: 420, gap: 12 },
  title: { color: '#f5f5f5', fontSize: 28, fontWeight: '700' },
  body: { color: '#c9ccd3', fontSize: 16, lineHeight: 22 },
  error: { color: '#ff8a80', fontSize: 15 },
  input: { borderWidth: 1, borderColor: '#3a3f4b', borderRadius: 8, padding: 12, color: '#f5f5f5', fontSize: 16, minHeight: 48 },
  button: { backgroundColor: '#f5f5f5', borderRadius: 8, padding: 14, alignItems: 'center', minHeight: 48 },
  buttonText: { color: '#0f1115', fontSize: 16, fontWeight: '600' },
  dim: { opacity: 0.6 },
});
