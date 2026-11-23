import { useCallback, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useFocusEffect } from 'expo-router';
import { formatDuration, type Activity, type CredentialStatus } from '@pankra/shared';
import { api } from '../src/api';

/** min/km from metres and seconds. */
function pace(a: Activity): string {
  if (!a.distanceM || !a.movingTimeS) return '–';
  return `${formatDuration(a.movingTimeS / (a.distanceM / 1000))} /km`;
}

/** Paces: runs arriving from Strava, and the connection that brings them. */
export default function Paces() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [strava, setStrava] = useState<CredentialStatus | undefined>();
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api.activities().then(setActivities).catch((e: Error) => setError(e.message));
      api
        .credentials()
        .then((c) => setStrava(c.find((x) => x.provider === 'strava')))
        .catch(() => undefined);
    }, []),
  );

  async function connect() {
    setError(null);
    try {
      const { url } = await api.stravaConnectUrl();
      await Linking.openURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Paces' }} />
      <View style={styles.card}>
        <Text style={styles.heading} accessibilityRole="header">Strava</Text>
        {strava ? (
          <Text>Connected. New runs arrive here on their own.</Text>
        ) : (
          <>
            <Text>Connect Strava so your runs arrive here by themselves.</Text>
            <Pressable accessibilityRole="button" onPress={connect} style={styles.button}>
              <Text style={styles.buttonText}>Connect Strava</Text>
            </Pressable>
          </>
        )}
        {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      </View>
      {activities.length === 0 ? <Text>No runs yet.</Text> : null}
      {activities.map((a) => (
        <View key={a.id} style={styles.row}>
          <Text style={styles.name}>{a.name || a.sport}</Text>
          <Text style={styles.small}>
            {a.startDate.slice(0, 10)} · {(a.distanceM / 1000).toFixed(2)} km · {formatDuration(a.movingTimeS)} · {pace(a)}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10, maxWidth: 720 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  heading: { fontSize: 17, fontWeight: '700', color: '#111827' },
  button: { backgroundColor: '#fc4c02', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: '#b91c1c' },
  row: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 4 },
  name: { fontSize: 16, fontWeight: '600', color: '#111827' },
  small: { fontSize: 14, color: '#374151' },
});
