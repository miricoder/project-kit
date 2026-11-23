import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text } from 'react-native';
import { Link, Stack } from 'expo-router';
import { buildCard, type Card } from '@pankra/shared';
import { api, today } from '../src/api';
import { WhiteboardCard } from '../src/WhiteboardCard';

/** Today: the day's sessions as whiteboard cards. */
export default function Today() {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const day = today();
    Promise.all([api.sessions(day, day), api.profile()])
      .then(([sessions, profile]) => setCards(sessions.map((s) => buildCard(s, profile))))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Today' }} />
      <Link href="/week" style={styles.link}>
        Week ›
      </Link>
      <Link href="/settings" style={styles.link}>
        Settings ›
      </Link>
      {error ? <Text accessibilityRole="alert">Could not load today: {error}</Text> : null}
      {!cards && !error ? <ActivityIndicator accessibilityLabel="Loading" /> : null}
      {cards?.length === 0 ? <Text>Nothing planned today.</Text> : null}
      {cards?.map((c, i) => <WhiteboardCard key={i} card={c} />)}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 16 },
  link: { color: '#1d4ed8', fontSize: 16, paddingVertical: 8 },
});
