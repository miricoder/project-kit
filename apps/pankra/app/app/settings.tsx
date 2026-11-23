import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Stack, useFocusEffect } from 'expo-router';
import type { CredentialStatus, Provider, RegistryStatus, Retention } from '@pankra/shared';
import { api } from '../src/api';

const PROVIDERS: Array<{ id: Provider; name: string }> = [
  { id: 'claude', name: 'Claude (Anthropic)' },
  { id: 'gpt', name: 'GPT (OpenAI)' },
];

const RETENTIONS: Array<{ id: Retention; label: string }> = [
  { id: 'session', label: 'This session' },
  { id: '24h', label: '24 hours' },
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: 'forever', label: 'Until deleted' },
];

function KeyRow({ provider, name, status, onChange }: {
  provider: Provider;
  name: string;
  status?: CredentialStatus;
  onChange: () => void;
}) {
  const [secret, setSecret] = useState('');
  const [retention, setRetention] = useState<Retention>('7d');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setSecret('');
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.label} accessibilityRole="header">{name}</Text>
      {status ? (
        <Text>
          Key ending {status.last4} ·{' '}
          {status.expiresAt ? `deleted ${new Date(status.expiresAt).toLocaleString()}` : 'kept until you delete it'}
        </Text>
      ) : (
        <Text>No key saved. Skills cannot run on {name} until you add one.</Text>
      )}
      <TextInput
        style={styles.input}
        value={secret}
        onChangeText={setSecret}
        accessibilityLabel={`${name} API key`}
        placeholder={status ? 'Paste a new key to replace it' : 'Paste your API key'}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
      />
      <Text style={styles.small}>Keep it for</Text>
      <View style={styles.chips} accessibilityRole="radiogroup">
        {RETENTIONS.map((r) => (
          <Pressable
            key={r.id}
            accessibilityRole="radio"
            accessibilityState={{ checked: retention === r.id }}
            onPress={() => setRetention(r.id)}
            style={[styles.chip, retention === r.id && styles.chipOn]}
          >
            <Text style={retention === r.id ? styles.chipTextOn : undefined}>{r.label}</Text>
          </Pressable>
        ))}
      </View>
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          disabled={busy || secret.trim().length < 8}
          accessibilityState={{ disabled: busy || secret.trim().length < 8 }}
          onPress={() => run(() => api.saveKey(provider, secret.trim(), retention))}
          style={[styles.button, (busy || secret.trim().length < 8) && styles.disabled]}
        >
          <Text style={styles.buttonText}>Save key</Text>
        </Pressable>
        {status ? (
          <Pressable
            accessibilityRole="button"
            disabled={busy}
            onPress={() => run(() => api.deleteKey(provider))}
            style={[styles.button, styles.danger]}
          >
            <Text style={styles.buttonText}>Delete key now</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function CapRow({ provider, name, monthlyUsd, spentUsd, onChange }: {
  provider: Provider;
  name: string;
  monthlyUsd: number | null;
  spentUsd: number;
  onChange: () => void;
}) {
  const [value, setValue] = useState(monthlyUsd === null ? '' : String(monthlyUsd));
  const [error, setError] = useState<string | null>(null);
  async function save() {
    const n = Number(value);
    if (!value.trim() || !Number.isFinite(n) || n < 0) return setError('Enter an amount in dollars, e.g. 10');
    setError(null);
    try {
      await api.setCap(provider, n);
      onChange();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <View style={styles.capRow}>
      <Text style={styles.capName}>
        {name}: ${spentUsd.toFixed(2)} spent this month
        {monthlyUsd !== null ? ` of $${monthlyUsd.toFixed(2)}` : ', no cap'}
      </Text>
      <View style={styles.actions}>
        <TextInput
          style={[styles.input, styles.capInput]}
          value={value}
          onChangeText={setValue}
          accessibilityLabel={`${name} monthly cap in dollars`}
          keyboardType="decimal-pad"
          placeholder="10"
        />
        <Pressable accessibilityRole="button" onPress={save} style={styles.button}>
          <Text style={styles.buttonText}>Set cap</Text>
        </Pressable>
      </View>
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    </View>
  );
}

type Caps = Awaited<ReturnType<typeof api.caps>>;

/** Registry: where skills come from, when they last synced, and Sync now. */
function RegistryCard() {
  const [status, setStatus] = useState<RegistryStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(() => {
    api.registryStatus().then(setStatus).catch((e: Error) => setMessage(e.message));
  }, []);
  useFocusEffect(load);

  async function syncNow() {
    setBusy(true);
    setMessage(null);
    try {
      const r = await api.syncRegistry();
      const skipped = r.skipped.map((s) => `${s.name} (${s.reason})`).join(', ');
      setMessage(`Synced: ${r.added} added, ${r.updated} updated, ${r.retired} retired${skipped ? `; skipped ${skipped}` : ''}.`);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
      load();
    }
  }

  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : 'never');
  return (
    <View style={styles.card}>
      <Text style={styles.label} accessibilityRole="header">Skills registry</Text>
      {status ? (
        <>
          <Text style={styles.small}>
            {status.repo} at {status.ref} · {status.nodes} nodes
          </Text>
          <Text>Last successful sync: {when(status.lastSuccessAt)}</Text>
          {status.lastError ? (
            <Text style={styles.error}>
              Last attempt {when(status.lastAttemptAt)} failed: {status.lastError}. Current skills are kept.
            </Text>
          ) : null}
        </>
      ) : null}
      {message ? <Text accessibilityLiveRegion="polite">{message}</Text> : null}
      <Pressable
        accessibilityRole="button"
        disabled={busy}
        accessibilityState={{ disabled: busy }}
        onPress={syncNow}
        style={[styles.button, busy && styles.disabled]}
      >
        <Text style={styles.buttonText}>{busy ? 'Syncing…' : 'Sync now'}</Text>
      </Pressable>
    </View>
  );
}

/** Settings: LLM keys, encrypted on the server, kept for the period chosen; monthly caps. */
export default function Settings() {
  const [statuses, setStatuses] = useState<CredentialStatus[]>([]);
  const [caps, setCaps] = useState<Caps>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api.credentials().then(setStatuses).catch((e: Error) => setError(e.message));
    api.caps().then(setCaps).catch((e: Error) => setError(e.message));
  }, []);
  useFocusEffect(load);

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Settings' }} />
      <Text>Keys are encrypted on the server and never shown again; only the last 4 characters are.</Text>
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {PROVIDERS.map((p) => (
        <KeyRow key={p.id} provider={p.id} name={p.name} status={statuses.find((s) => s.provider === p.id)} onChange={load} />
      ))}
      <View style={styles.card}>
        <Text style={styles.label} accessibilityRole="header">Monthly spending caps</Text>
        <Text style={styles.small}>
          Runs stop once a provider reaches its cap, until next month or until you raise it.
        </Text>
        {caps.map((c) => (
          <CapRow
            key={`${c.provider}:${c.monthlyUsd}`}
            provider={c.provider}
            name={PROVIDERS.find((p) => p.id === c.provider)?.name ?? c.provider}
            monthlyUsd={c.monthlyUsd}
            spentUsd={c.spentUsd}
            onChange={load}
          />
        ))}
      </View>
      <RegistryCard />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 12, maxWidth: 640 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  label: { fontWeight: '700', fontSize: 16, color: '#111827' },
  small: { fontSize: 14, color: '#374151' },
  input: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 8, padding: 10, fontSize: 16 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 16, paddingHorizontal: 10, paddingVertical: 6, minHeight: 32 },
  chipOn: { backgroundColor: '#111827', borderColor: '#111827' },
  chipTextOn: { color: '#fff' },
  actions: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  button: { backgroundColor: '#111827', borderRadius: 8, paddingVertical: 12, paddingHorizontal: 16 },
  danger: { backgroundColor: '#b91c1c' },
  disabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontWeight: '700' },
  error: { color: '#b91c1c' },
  capRow: { gap: 6, paddingTop: 6 },
  capName: { fontSize: 15, color: '#111827' },
  capInput: { minWidth: 100 },
});
