import { useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '../../src/lib/client';
import { useSession } from '../../src/session';
import { Button, Screen, styles } from '../../src/ui';

export default function Verify() {
  const { token } = useLocalSearchParams<{ token?: string }>();
  const { refresh } = useSession();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!token) { setError('This sign-in link is incomplete.'); return; }
    api.verify(token)
      .then(async () => { await refresh(); router.replace('/'); })
      .catch((e: Error) => setError(e.message));
  }, [token, refresh]);
  return (
    <Screen>
      {error ? (
        <>
          <Text accessibilityRole="alert" style={styles.error}>{error}</Text>
          <Button label="Get a new link" onPress={() => router.replace('/sign-in')} />
        </>
      ) : <ActivityIndicator accessibilityLabel="Signing in" />}
    </Screen>
  );
}
