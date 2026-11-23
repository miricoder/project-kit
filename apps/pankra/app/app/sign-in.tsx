import { useState } from 'react';
import { Text, TextInput } from 'react-native';
import { api } from '../src/lib/client';
import { Button, Screen, styles } from '../src/ui';

export default function SignIn() {
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  async function send() {
    setState('sending');
    try { await api.requestLink(email.trim()); setState('sent'); } catch { setState('error'); }
  }
  return (
    <Screen>
      <Text accessibilityRole="header" style={styles.title}>Sign in</Text>
      {state === 'sent' ? (
        <Text style={styles.body}>Check your email for a sign-in link. It works once, for 15 minutes.</Text>
      ) : (
        <>
          <Text nativeID="email-label" style={styles.body}>Email</Text>
          <TextInput accessibilityLabelledBy="email-label" accessibilityLabel="Email" style={styles.input}
            value={email} onChangeText={setEmail} autoCapitalize="none" autoComplete="email"
            keyboardType="email-address" inputMode="email" onSubmitEditing={send} />
          {state === 'error' && <Text accessibilityRole="alert" style={styles.error}>Could not send the link. Try again.</Text>}
          <Button label={state === 'sending' ? 'Sending…' : 'Email me a sign-in link'} onPress={send}
            disabled={state === 'sending' || !email.includes('@')} />
        </>
      )}
    </Screen>
  );
}
