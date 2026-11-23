import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Stack } from 'expo-router';
import type { ScheduleChange } from '@pankra/shared';
import { api, today } from '../src/api';

/** Add class: a box class from text replaces the day's plan and pushes later sessions. */
export default function AddClass() {
  const [date, setDate] = useState(today());
  const [title, setTitle] = useState('');
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState<ScheduleChange[] | null>(null);

  async function submit() {
    setError(null);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return setError('Date must look like 2026-11-24.');
    if (!title.trim()) return setError('Give the class a name.');
    setBusy(true);
    try {
      const lines = details.split('\n').map((l) => l.trim()).filter(Boolean);
      const result = await api.insert(date, {
        title: title.trim(),
        type: 'class',
        sections: lines.length ? [{ kind: 'engine', label: 'Class', lines }] : [],
      });
      setChanges(result.changes);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Add class' }} />
      <Text nativeID="date-label" style={styles.label}>Date</Text>
      <TextInput
        style={styles.input}
        value={date}
        onChangeText={setDate}
        accessibilityLabel="Date"
        placeholder="2026-11-24"
        autoCapitalize="none"
      />
      <Text nativeID="title-label" style={styles.label}>Class</Text>
      <TextInput
        style={styles.input}
        value={title}
        onChangeText={setTitle}
        accessibilityLabel="Class"
        placeholder="Box class: HYROX conditioning"
      />
      <Text nativeID="details-label" style={styles.label}>What the class does (one line each)</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        value={details}
        onChangeText={setDetails}
        accessibilityLabel="What the class does"
        multiline
      />
      {error ? (
        <Text accessibilityRole="alert" style={styles.error}>
          {error}
        </Text>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled: busy }}
        disabled={busy}
        onPress={submit}
        style={styles.button}
      >
        <Text style={styles.buttonText}>{busy ? 'Adding…' : 'Add class and move my week'}</Text>
      </Pressable>
      {changes ? (
        <View style={styles.changes} accessibilityLiveRegion="polite">
          <Text style={styles.label}>
            {changes.length ? 'What moved' : 'Nothing had to move.'}
          </Text>
          {changes.map((c) => (
            <Text key={c.sessionId} style={c.intoNextWeek ? styles.warn : undefined}>
              {c.message}
            </Text>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 8, maxWidth: 640 },
  label: { fontWeight: '700', fontSize: 15, color: '#111827' },
  input: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16 },
  multiline: { minHeight: 96, textAlignVertical: 'top' },
  error: { color: '#b91c1c' },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center', marginTop: 8 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  changes: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 4 },
  warn: { color: '#b45309', fontWeight: '600' },
});
