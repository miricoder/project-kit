import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import type { CredentialStatus, NodeSummary, Result, ResultPart, Run } from '@pankra/shared';
import { api } from '../../src/api';
import { RunPanel } from '../../src/RunPanel';


interface Row {
  label: string;
  km: string;
  time: string;
  loadKg: string;
  reps: string;
}

const emptyRow = (n: number): Row => ({ label: `Part ${n}`, km: '', time: '', loadKg: '', reps: '' });

/** "4:10" -> 250 seconds; plain numbers are seconds. */
function parseTime(text: string): number | undefined {
  const t = text.trim();
  if (!t) return undefined;
  const parts = t.split(':').map(Number);
  if (parts.some((p) => !Number.isFinite(p) || p < 0)) return NaN;
  return parts.reduce((total, p) => total * 60 + p, 0);
}

function toPart(row: Row): ResultPart | string {
  const part: ResultPart = { label: row.label.trim() || 'Part' };
  const num = (s: string) => (s.trim() ? Number(s.replace(',', '.')) : undefined);
  const km = num(row.km);
  const timeS = parseTime(row.time);
  const loadKg = num(row.loadKg);
  const reps = num(row.reps);
  if ([km, timeS, loadKg, reps].some((v) => v !== undefined && (!Number.isFinite(v) || v < 0))) {
    return `${part.label}: numbers only (time as 4:10)`;
  }
  if (km !== undefined) part.distanceM = Math.round(km * 1000);
  if (timeS !== undefined) part.timeS = timeS;
  if (loadKg !== undefined) part.loadKg = loadKg;
  if (reps !== undefined) part.reps = Math.round(reps);
  return part;
}

/** Log: type a result against the session, then get feedback from result-analyzer. */
export default function Log() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [rows, setRows] = useState<Row[]>([emptyRow(1)]);
  const [notes, setNotes] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [analyzer, setAnalyzer] = useState<NodeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api.credentials().then(setCredentials).catch(() => setCredentials([]));
      api
        .nodes()
        .then((nodes) => setAnalyzer(nodes.find((n) => n.kind === 'skill' && n.name === 'result-analyzer') ?? null))
        .catch(() => setAnalyzer(null));
    }, []),
  );

  const update = (i: number, field: keyof Row, value: string) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, [field]: value } : r)));

  async function save() {
    setError(null);
    const parts = rows.map(toPart);
    const bad = parts.find((p): p is string => typeof p === 'string');
    if (bad) return setError(bad);
    try {
      setResult(await api.logResult(sessionId, parts as ResultPart[], notes.trim() || undefined));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onRun(run: Run) {
    if (run.status === 'succeeded' && result) setResult(await api.result(result.id));
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Log result' }} />
      {rows.map((row, i) => (
        <View key={i} style={styles.card}>
          <TextInput
            style={styles.input}
            value={row.label}
            onChangeText={(v) => update(i, 'label', v)}
            accessibilityLabel={`Part ${i + 1} name`}
          />
          <View style={styles.fields}>
            {(
              [
                ['km', 'km', 'Distance in km'],
                ['time', 'm:ss', 'Time as minutes and seconds'],
                ['loadKg', 'kg', 'Load in kg'],
                ['reps', 'reps', 'Reps'],
              ] as const
            ).map(([field, placeholder, label]) => (
              <TextInput
                key={field}
                style={[styles.input, styles.field]}
                value={row[field]}
                onChangeText={(v) => update(i, field, v)}
                placeholder={placeholder}
                accessibilityLabel={`Part ${i + 1}: ${label}`}
                keyboardType={field === 'time' ? 'numbers-and-punctuation' : 'decimal-pad'}
              />
            ))}
          </View>
        </View>
      ))}
      <Pressable accessibilityRole="button" onPress={() => setRows([...rows, emptyRow(rows.length + 1)])}>
        <Text style={styles.link}>+ Add part</Text>
      </Pressable>
      <TextInput
        style={[styles.input, styles.notes]}
        value={notes}
        onChangeText={setNotes}
        placeholder="How it felt"
        accessibilityLabel="Notes"
        multiline
      />
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {!result ? (
        <Pressable accessibilityRole="button" onPress={save} style={styles.button}>
          <Text style={styles.buttonText}>Save result</Text>
        </Pressable>
      ) : (
        <>
          <Text style={styles.saved}>Result saved.</Text>
          {analyzer ? (
            <RunPanel
              node={analyzer}
              credentials={credentials}
              input={{ sessionId, resultId: result.id }}
              onResult={onRun}
            />
          ) : (
            <Text>result-analyzer is not loaded yet: sync the registry in Settings to get feedback.</Text>
          )}
        </>
      )}
      {result?.feedback ? (
        <View style={styles.card} accessibilityLiveRegion="polite">
          <Text style={styles.heading} accessibilityRole="header">Feedback</Text>
          <Text style={styles.body}>{result.feedback.feedback}</Text>
          <Text style={styles.heading}>Tips</Text>
          {result.feedback.tips.map((t, i) => (
            <Text key={i} style={styles.body}>
              {i + 1}. {t}
            </Text>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10, maxWidth: 720 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  field: { flexGrow: 1, minWidth: 70 },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16, backgroundColor: '#fff' },
  notes: { minHeight: 72, textAlignVertical: 'top' },
  link: { color: '#1d4ed8', fontSize: 16, paddingVertical: 8 },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: '#b91c1c' },
  saved: { color: '#15803d', fontWeight: '600' },
  heading: { fontWeight: '700', fontSize: 16, color: '#111827' },
  body: { fontSize: 16, color: '#111827' },
});
