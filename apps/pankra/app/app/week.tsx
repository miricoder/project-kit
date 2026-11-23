import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link, Stack, useFocusEffect } from 'expo-router';
import { addDays, shortDate, weekStart, type Session } from '@pankra/shared';
import { api, today } from '../src/api';

const STATUS_COLOURS: Record<Session['status'], string> = {
  Done: '#15803d',
  Today: '#1d4ed8',
  Scheduled: '#374151',
  Moved: '#b45309',
  Skipped: '#6b7280',
};

/** Week: Monday to Sunday, each day's sessions and their status. */
export default function Week() {
  const [monday, setMonday] = useState(() => weekStart(today()));
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));

  useFocusEffect(
    useCallback(() => {
      setSessions(null);
      api
        .sessions(monday, addDays(monday, 6))
        .then(setSessions)
        .catch((e: Error) => setError(e.message));
    }, [monday]),
  );

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Week' }} />
      <View style={styles.nav}>
        <Pressable accessibilityRole="button" onPress={() => setMonday(addDays(monday, -7))}>
          <Text style={styles.link}>‹ Previous week</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => setMonday(addDays(monday, 7))}>
          <Text style={styles.link}>Next week ›</Text>
        </Pressable>
      </View>
      <Link href="/add-class" style={styles.link}>
        + Add class
      </Link>
      {error ? <Text accessibilityRole="alert">Could not load the week: {error}</Text> : null}
      {days.map((day) => {
        const todays = sessions?.filter((s) => s.date === day) ?? [];
        return (
          <View key={day} style={styles.day}>
            <Text style={styles.dayLabel}>{shortDate(day)}</Text>
            {sessions && todays.length === 0 ? <Text style={styles.empty}>Free</Text> : null}
            {todays.map((s) => (
              <View key={s.id} style={styles.row}>
                <Text style={styles.title}>{s.type === 'rest' ? 'Rest day' : s.title}</Text>
                {s.type !== 'rest' ? (
                  <Text style={[styles.status, { color: STATUS_COLOURS[s.status] }]}>
                    {s.status}
                    {s.movedFrom ? ` from ${shortDate(s.movedFrom)}` : ''}
                  </Text>
                ) : null}
              </View>
            ))}
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 12 },
  nav: { flexDirection: 'row', justifyContent: 'space-between' },
  link: { color: '#1d4ed8', fontSize: 16, paddingVertical: 8 },
  day: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 4 },
  dayLabel: { fontWeight: '700', fontSize: 15, color: '#111827' },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  title: { fontSize: 16, color: '#111827', flexShrink: 1 },
  status: { fontSize: 14, fontWeight: '600' },
  empty: { fontSize: 14, color: '#6b7280' },
});
