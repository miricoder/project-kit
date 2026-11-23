import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Stack, useFocusEffect } from 'expo-router';
import type { CredentialStatus, NodeSummary, Run } from '@pankra/shared';
import { api, today } from '../src/api';
import { RunPanel } from '../src/RunPanel';

interface Meals {
  seen?: string[];
  before: string[];
  after: string[];
  buy?: string;
  questions?: string[];
}

/** Fuel: meals before and after the day's session from a fridge photo or a list. */
export default function Fuel() {
  const [date, setDate] = useState(today());
  const [fridgeText, setFridgeText] = useState('');
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [planner, setPlanner] = useState<NodeSummary | null>(null);
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [meals, setMeals] = useState<Meals | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api.credentials().then(setCredentials).catch(() => setCredentials([]));
      api
        .nodes()
        .then((n) => setPlanner(n.find((x) => x.kind === 'skill' && x.name === 'meal-planner') ?? null))
        .catch(() => setPlanner(null));
    }, []),
  );

  async function pickPhoto() {
    setError(null);
    const picked = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (picked.canceled || !picked.assets[0]) return;
    try {
      const upload = await api.uploadScreenshot(picked.assets[0], 'meal');
      setUploadId(upload.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const input: Record<string, unknown> = { date };
  if (uploadId) input.uploadIds = [uploadId];
  if (fridgeText.trim()) input.fridgeText = fridgeText.trim();

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Fuel' }} />
      <View style={styles.card}>
        <Text style={styles.label}>Day</Text>
        <TextInput style={styles.input} value={date} onChangeText={setDate} accessibilityLabel="Day" placeholder="2026-11-25" />
        <Pressable accessibilityRole="button" onPress={pickPhoto} style={styles.button}>
          <Text style={styles.buttonText}>{uploadId ? 'Fridge photo added ✓ (change)' : 'Add a fridge photo'}</Text>
        </Pressable>
        <Text style={styles.label}>…or list what is there</Text>
        <TextInput
          style={[styles.input, styles.multi]}
          value={fridgeText}
          onChangeText={setFridgeText}
          accessibilityLabel="What is in the fridge"
          placeholder="eggs, rice, yoghurt, bananas"
          multiline
        />
        {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      </View>
      {planner ? (
        <RunPanel
          node={planner}
          credentials={credentials}
          input={input}
          onResult={(run: Run) => run.status === 'succeeded' && setMeals(run.output as Meals)}
        />
      ) : (
        <Text>meal-planner is not loaded yet: sync the registry in Settings.</Text>
      )}
      {meals ? (
        <View style={styles.card} accessibilityLiveRegion="polite">
          {meals.seen?.length ? <Text style={styles.small}>Seen: {meals.seen.join(', ')}</Text> : null}
          <Text style={styles.heading} accessibilityRole="header">Before</Text>
          {meals.before.map((m, i) => <Text key={`b${i}`} style={styles.body}>• {m}</Text>)}
          <Text style={styles.heading} accessibilityRole="header">After</Text>
          {meals.after.map((m, i) => <Text key={`a${i}`} style={styles.body}>• {m}</Text>)}
          {meals.buy ? <Text style={styles.body}>Worth buying: {meals.buy}</Text> : null}
          {meals.questions?.map((q, i) => <Text key={`q${i}`} style={styles.small}>? {q}</Text>)}
          <Text style={styles.small}>Not medical or dietetic advice.</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10, maxWidth: 720 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  label: { fontSize: 15, fontWeight: '600', color: '#111827' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16 },
  multi: { minHeight: 72, textAlignVertical: 'top' },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: '#b91c1c' },
  heading: { fontSize: 17, fontWeight: '700', color: '#111827' },
  body: { fontSize: 16, color: '#111827' },
  small: { fontSize: 14, color: '#374151' },
});
