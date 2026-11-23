import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link, Stack, useFocusEffect } from 'expo-router';
import { nodeBadge, type CredentialStatus, type Edge, type Provider } from '@pankra/shared';
import { IS_PREVIEW, api, type GraphNode } from '../src/api';
import { nodeId } from '../src/graph';
import { RunPanel } from '../src/RunPanel';
import SkillsGraph from '../src/SkillsGraph';

const KIND_LABEL = { skill: 'Skill', agent: 'Agent', plugin: 'Plugin', provider: 'Provider' } as const;

/** Skills: every node as a graph (hover for run order, click to run) and as a list. */
export default function Skills() {
  const [nodes, setNodes] = useState<GraphNode[] | null>(null);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      Promise.all([api.nodes(), api.edges(), api.credentials()])
        .then(([n, e, c]) => {
          setNodes(n);
          setEdges(e);
          setCredentials(c);
        })
        .catch((e: Error) => setError(e.message));
    }, []),
  );

  const onSelect = useCallback(async (id: string) => setSelected(id), []);
  const node = nodes?.find((n) => nodeId(n) === selected);
  const runnable = node && node.kind !== 'plugin' && Object.keys(node.providers).length > 0;

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Skills' }} />
      {error ? <Text accessibilityRole="alert">Could not load the skills: {error}</Text> : null}
      {nodes?.length === 0 ? (
        <Text>
          No skills yet. <Link href="/settings" style={styles.link}>Sync the registry in Settings</Link>.
        </Text>
      ) : null}
      {nodes && nodes.length > 0 ? (
        <View style={styles.graph}>
          <SkillsGraph nodes={nodes} edges={edges} onSelect={onSelect} dom={{ style: { height: 460 } }} />
        </View>
      ) : null}
      {node ? (
        runnable ? (
          <RunPanel key={selected} node={node} credentials={credentials} input={{}} inputSchema={node.input} />
        ) : (
          <View style={styles.card}>
            <Text style={styles.name} accessibilityRole="header">{node.name}</Text>
            {node.description ? <Text>{node.description}</Text> : null}
            {node.skills?.length ? <Text>Skills: {node.skills.join(', ')}</Text> : null}
            {node.agents?.length ? <Text>Agents: {node.agents.join(', ')}</Text> : null}
          </View>
        )
      ) : null}
      {nodes?.map((n) => {
        const ready = (Object.keys(n.providers) as Provider[]).some((p) => nodeBadge(n, p, credentials) === 'green');
        return (
          <Pressable
            key={nodeId(n)}
            accessibilityRole="button"
            accessibilityState={{ selected: selected === nodeId(n) }}
            onPress={() => setSelected(nodeId(n))}
            style={[styles.row, selected === nodeId(n) && styles.rowOn]}
          >
            <Text style={styles.rowName}>
              {KIND_LABEL[n.kind]} · {n.name}
            </Text>
            {n.steps?.length ? (
              <Text style={styles.small}>{n.steps.map((s) => `${s.order}. ${s.skill}`).join('  ')}</Text>
            ) : null}
            {n.kind === 'plugin' ? null : IS_PREVIEW ? (
              <Text style={styles.small}>Runs on Claude when opened on claude.ai</Text>
            ) : (
              <Text style={ready ? styles.ok : styles.warn}>{ready ? '● Ready' : '● Needs a key'}</Text>
            )}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 10 },
  graph: { height: 460, borderRadius: 12, overflow: 'hidden' },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 6 },
  name: { fontSize: 18, fontWeight: '700', color: '#111827' },
  link: { color: '#1d4ed8' },
  row: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 4 },
  rowOn: { borderWidth: 2, borderColor: '#111827' },
  rowName: { fontSize: 16, fontWeight: '600', color: '#111827' },
  small: { fontSize: 14, color: '#374151' },
  ok: { color: '#15803d', fontWeight: '600' },
  warn: { color: '#b45309', fontWeight: '600' },
});
