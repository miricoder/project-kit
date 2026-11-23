import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { formatDuration, parseDuration, type RaceAnalysis } from '@pankra/shared';
import { api } from '../../src/api';

/** Race analysis: seconds to gain per segment against a target, most first. */
export default function RaceAnalysisScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [target, setTarget] = useState('60:00');
  const [analysis, setAnalysis] = useState<RaceAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (targetText: string) => {
      const s = parseDuration(targetText); // "60:00" or "1:05:00"
      if (!s) return setError('Target looks like 60:00 or 1:05:00');
      setError(null);
      api.raceAnalysis(id, s).then(setAnalysis).catch((e: Error) => setError(e.message));
    },
    [id],
  );
  // Analyse with the current target when the screen opens; "Set target" re-runs it.
  const [initialTarget] = useState(target);
  useFocusEffect(useCallback(() => load(initialTarget), [load, initialTarget]));

  const max = Math.max(1, ...(analysis?.segments.map((s) => Math.abs(s.gainSeconds)) ?? [1]));
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Race analysis' }} />
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          value={target}
          onChangeText={setTarget}
          accessibilityLabel="Target time"
          placeholder="60:00"
        />
        <Pressable accessibilityRole="button" onPress={() => load(target)} style={styles.button}>
          <Text style={styles.buttonText}>Set target</Text>
        </Pressable>
      </View>
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {analysis ? (
        <>
          <Text style={styles.small}>
            Race {formatDuration(analysis.totalS)} against {formatDuration(analysis.targetS)}. {analysis.model}: a model to aim at, not a fact.
          </Text>
          {analysis.segments.map((s) => (
            <View
              key={s.name}
              style={styles.segment}
              accessible
              accessibilityLabel={`${s.name}: ${formatDuration(s.actualSeconds)}, target ${formatDuration(s.targetSeconds)}, ${s.gainSeconds} seconds to gain`}
            >
              <View style={styles.segmentHead}>
                <Text style={styles.name}>{s.name}</Text>
                <Text style={styles.gain}>{s.gainSeconds > 0 ? `${s.gainSeconds} s to gain` : 'on target'}</Text>
              </View>
              <View style={styles.track}>
                <View style={[styles.bar, { width: `${(Math.max(0, s.gainSeconds) / max) * 100}%` }]} />
              </View>
              <Text style={styles.small}>
                {formatDuration(s.actualSeconds)} → {formatDuration(s.targetSeconds)}
              </Text>
            </View>
          ))}
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10, maxWidth: 720 },
  row: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16, backgroundColor: '#fff', minWidth: 110 },
  button: { backgroundColor: '#111827', borderRadius: 8, paddingVertical: 12, paddingHorizontal: 16 },
  buttonText: { color: '#fff', fontWeight: '700' },
  error: { color: '#b91c1c' },
  small: { fontSize: 14, color: '#374151' },
  segment: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 6 },
  segmentHead: { flexDirection: 'row', justifyContent: 'space-between' },
  name: { fontSize: 16, fontWeight: '700', color: '#111827' },
  gain: { fontSize: 15, fontWeight: '600', color: '#b45309' },
  track: { height: 10, backgroundColor: '#f3f4f6', borderRadius: 5, overflow: 'hidden' },
  bar: { height: 10, backgroundColor: '#e0604a', borderRadius: 5 },
});
