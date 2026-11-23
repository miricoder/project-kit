import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import { api } from '../src/api';

/**
 * Sign in by email link. The link opens this screen with ?token= (pankra:// on iPhone, the
 * web address in a browser), which signs in and goes to Today.
 */
export default function SignIn() {
  const { token } = useLocalSearchParams<{ token?: string }>();
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    setBusy(true);
    api
      .verifySignIn(token)
      .then(() => router.replace('/'))
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  }, [token]);

  async function send() {
    setError(null);
    setMessage(null);
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Enter your email address.');
    setBusy(true);
    try {
      const r = await api.requestSignInLink(email.trim());
      setMessage(`${r.message} Open it on this device.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.page}>
      <Stack.Screen options={{ title: 'Sign in' }} />
      <Text style={styles.title} accessibilityRole="header">PANKRA</Text>
      {token && busy ? <ActivityIndicator accessibilityLabel="Signing in" /> : null}
      <Text nativeID="email-label" style={styles.label}>Email</Text>
      <TextInput
        style={styles.input}
        value={email}
        onChangeText={setEmail}
        accessibilityLabel="Email"
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        inputMode="email"
        onSubmitEditing={send}
      />
      <Pressable
        accessibilityRole="button"
        disabled={busy}
        accessibilityState={{ disabled: busy }}
        onPress={send}
        style={[styles.button, busy && styles.disabled]}
      >
        <Text style={styles.buttonText}>Email me a sign-in link</Text>
      </Pressable>
      {message ? <Text accessibilityLiveRegion="polite">{message}</Text> : null}
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: 24, gap: 12, maxWidth: 480, width: '100%', alignSelf: 'center' },
  title: { fontSize: 34, fontFamily: 'Georgia', color: '#111827', marginBottom: 12 },
  label: { fontSize: 15, fontWeight: '600', color: '#111827' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 12, fontSize: 16, backgroundColor: '#fff' },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center' },
  disabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: '#b91c1c' },
});
