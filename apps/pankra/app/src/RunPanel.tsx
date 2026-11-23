import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Link } from 'expo-router';
import { nodeBadge, type CredentialStatus, type JSONSchema, type NodeSummary, type Provider, type Run } from '@pankra/shared';
import { ApiError, IS_PREVIEW, api } from './api';

const NAMES: Record<Provider, string> = { claude: 'Claude', gpt: 'GPT' };

/** The string properties of a JSON schema, as simple text fields. */
function textFields(schema?: JSONSchema): Array<{ name: string; required: boolean }> {
  const props = (schema?.properties ?? {}) as Record<string, { type?: string }>;
  const required = new Set((schema?.required as string[] | undefined) ?? []);
  return Object.entries(props)
    .filter(([, p]) => p.type === 'string')
    .map(([name]) => ({ name, required: required.has(name) }));
}

/**
 * Run panel: description, provider choice, credential status and Run. A missing key or a
 * reached cap is explained before anything is sent; a failed run offers Retry.
 */
export function RunPanel({ node, credentials, input, inputSchema, onResult }: {
  node: NodeSummary;
  credentials: CredentialStatus[];
  /** Input the caller already has (e.g. the session being logged). */
  input: Record<string, unknown>;
  /** When given, the panel asks for the schema's text fields the caller did not supply. */
  inputSchema?: JSONSchema;
  onResult?: (run: Run) => void;
}) {
  // The preview runs every skill on Claude through claude.ai, with no key.
  const offered = (Object.keys(node.providers) as Provider[]).filter(
    (p) => node.providers[p] && (!IS_PREVIEW || p === 'claude'),
  );
  const [provider, setProvider] = useState<Provider>(offered[0] ?? 'claude');
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const [typed, setTyped] = useState<Record<string, string>>({});
  const badge = IS_PREVIEW ? 'green' : nodeBadge(node, provider, credentials);
  const fields = textFields(inputSchema).filter((f) => !(f.name in input));

  async function go() {
    setBusy(true);
    setRefusal(null);
    setRun(null);
    try {
      const extra = Object.fromEntries(
        Object.entries(typed).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()]),
      );
      const result = await api.run(node, provider, { ...extra, ...input });
      setRun(result);
      onResult?.(result);
    } catch (e) {
      setRefusal(e instanceof ApiError ? e : new ApiError(0, (e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.panel}>
      <Text style={styles.name} accessibilityRole="header">{node.name}</Text>
      {node.description ? <Text>{node.description}</Text> : null}
      <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel="Provider">
        {offered.map((p) => (
          <Pressable
            key={p}
            accessibilityRole="radio"
            accessibilityState={{ checked: provider === p }}
            onPress={() => setProvider(p)}
            style={[styles.chip, provider === p && styles.chipOn]}
          >
            <Text style={provider === p ? styles.chipTextOn : undefined}>
              {NAMES[p]} · {node.providers[p]?.model}
            </Text>
          </Pressable>
        ))}
      </View>
      {fields.map((f) => (
        <TextInput
          key={f.name}
          style={styles.input}
          value={typed[f.name] ?? ''}
          onChangeText={(v) => setTyped({ ...typed, [f.name]: v })}
          placeholder={`${f.name}${f.required ? ' (required)' : ''}`}
          accessibilityLabel={f.name}
          autoCapitalize="none"
        />
      ))}
      <Text style={badge === 'green' ? styles.ok : styles.warn}>
        {IS_PREVIEW
          ? '● Preview: runs on Claude when opened on claude.ai (no key needed)'
          : badge === 'green'
            ? `● Ready on ${NAMES[provider]}`
            : `● Needs a ${NAMES[provider]} key`}
      </Text>
      <Pressable
        accessibilityRole="button"
        disabled={busy}
        accessibilityState={{ disabled: busy }}
        onPress={go}
        style={[styles.button, busy && styles.disabled]}
      >
        <Text style={styles.buttonText}>{busy ? 'Running…' : run?.status === 'failed' ? 'Retry' : 'Run'}</Text>
      </Pressable>
      {refusal ? (
        <View accessibilityRole="alert">
          <Text style={styles.warn}>{refusal.message}</Text>
          {refusal.needs ? (
            <Link href="/settings" style={styles.link}>
              Add a {NAMES[refusal.needs.credential]} key in Settings ›
            </Link>
          ) : null}
        </View>
      ) : null}
      {run?.status === 'failed' ? (
        <Text accessibilityRole="alert" style={styles.warn}>Run failed: {run.error}</Text>
      ) : null}
      {run?.status === 'succeeded' ? (
        <Text style={styles.small}>
          Done on {NAMES[run.provider]} ({run.model}) · ${run.costUsd.toFixed(4)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  name: { fontSize: 18, fontWeight: '700', color: '#111827' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 16, paddingHorizontal: 10, paddingVertical: 6 },
  chipOn: { backgroundColor: '#111827', borderColor: '#111827' },
  chipTextOn: { color: '#fff' },
  ok: { color: '#15803d', fontWeight: '600' },
  warn: { color: '#b45309', fontWeight: '600' },
  small: { fontSize: 14, color: '#374151' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16 },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 12, alignItems: 'center' },
  disabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontWeight: '700' },
  link: { color: '#1d4ed8', paddingVertical: 6 },
});
