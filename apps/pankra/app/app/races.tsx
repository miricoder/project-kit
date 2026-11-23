import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Link, Stack, useFocusEffect } from 'expo-router';
import { formatDuration, raceFromScreen, type Provider, type Race, type Upload } from '@pankra/shared';
import { ApiError, api, today } from '../src/api';

const PROVIDERS: Array<{ id: Provider; name: string }> = [
  { id: 'claude', name: 'Claude' },
  { id: 'gpt', name: 'GPT' },
];

/** Races: a results screenshot becomes splits to confirm; confirmed races open their analysis. */
export default function Races() {
  const [races, setRaces] = useState<Race[]>([]);
  const [provider, setProvider] = useState<Provider>('claude');
  const [upload, setUpload] = useState<Upload | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const load = useCallback(() => {
    api.races().then(setRaces).catch((e: Error) => setError(e));
  }, []);
  useFocusEffect(load);

  async function pick() {
    setError(null);
    const picked = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1 });
    if (picked.canceled || !picked.assets[0]) return;
    setBusy(true);
    try {
      const u = await api.uploadScreenshot(picked.assets[0], 'race', provider);
      setUpload(u);
      setEdits(Object.fromEntries((u.extracted?.fields ?? []).map((f) => [f.label, f.text])));
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  // The athlete's corrections are parsed the same way as the reader's values.
  const draft = upload ? raceFromScreen(edits, [], { date: upload.extracted?.race?.date ?? today(), division: upload.extracted?.race?.division }) : null;

  async function confirm() {
    if (!upload || !draft?.race) return;
    setBusy(true);
    try {
      await api.confirmRace(upload.id, draft.race);
      setUpload(null);
      setEdits({});
      load();
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Races' }} />
      <View style={styles.card}>
        <Text style={styles.heading} accessibilityRole="header">Add a race from a results screenshot</Text>
        <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel="Read it with">
          {PROVIDERS.map((p) => (
            <Pressable
              key={p.id}
              accessibilityRole="radio"
              accessibilityState={{ checked: provider === p.id }}
              onPress={() => setProvider(p.id)}
              style={[styles.chip, provider === p.id && styles.chipOn]}
            >
              <Text style={provider === p.id ? styles.chipTextOn : undefined}>{p.name}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable accessibilityRole="button" disabled={busy} onPress={pick} style={[styles.button, busy && styles.disabled]}>
          <Text style={styles.buttonText}>{busy ? 'Reading…' : 'Choose screenshot'}</Text>
        </Pressable>
        {error ? (
          <View accessibilityRole="alert">
            <Text style={styles.error}>{error.message}</Text>
            {error instanceof ApiError && error.needs ? (
              <Link href="/settings" style={styles.link}>Add a key in Settings ›</Link>
            ) : null}
          </View>
        ) : null}
      </View>

      {upload?.extracted ? (
        <View style={styles.card}>
          <Text style={styles.heading} accessibilityRole="header">Check the splits</Text>
          <Text style={styles.small}>Nothing is saved until you confirm. Fix anything misread.</Text>
          {upload.extracted.fields.map((f) => (
            <View key={f.label} style={styles.field}>
              <Text nativeID={`f-${f.label}`} style={[styles.label, f.uncertain && styles.warn]}>
                {f.label}{f.uncertain ? ` (unsure${f.seen ? `: saw "${f.seen}"` : ''})` : ''}
              </Text>
              <TextInput
                style={[styles.input, f.uncertain && styles.inputWarn]}
                value={edits[f.label] ?? ''}
                onChangeText={(v) => setEdits({ ...edits, [f.label]: v })}
                accessibilityLabel={f.label}
              />
            </View>
          ))}
          {draft && draft.missing.length > 0 ? (
            <Text style={styles.warn}>Missing: {draft.missing.join(', ')}. Add them to confirm.</Text>
          ) : null}
          <Pressable
            accessibilityRole="button"
            disabled={busy || !draft?.race}
            accessibilityState={{ disabled: busy || !draft?.race }}
            onPress={confirm}
            style={[styles.button, (busy || !draft?.race) && styles.disabled]}
          >
            <Text style={styles.buttonText}>Confirm</Text>
          </Pressable>
        </View>
      ) : null}

      {races.map((r) => (
        <Link key={r.id} href={{ pathname: '/race/[id]', params: { id: r.id } }} style={styles.raceRow}>
          <Text style={styles.label}>
            {r.event} · {r.date} · {formatDuration(r.totalS)}
          </Text>
        </Link>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10, maxWidth: 720 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  heading: { fontSize: 17, fontWeight: '700', color: '#111827' },
  row: { flexDirection: 'row', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  chipOn: { backgroundColor: '#111827', borderColor: '#111827' },
  chipTextOn: { color: '#fff' },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  disabled: { opacity: 0.5 },
  error: { color: '#b91c1c' },
  link: { color: '#1d4ed8', paddingVertical: 6 },
  small: { fontSize: 14, color: '#374151' },
  field: { gap: 2 },
  label: { fontSize: 15, color: '#111827', fontWeight: '600' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 8, fontSize: 16 },
  inputWarn: { borderColor: '#b45309', borderWidth: 2 },
  warn: { color: '#b45309' },
  raceRow: { backgroundColor: '#fff', borderRadius: 10, padding: 14 },
});
