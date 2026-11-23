import { StyleSheet, Text, View } from 'react-native';
import type { Card, CardSection } from '@pankra/shared';

const SECTION_COLOURS: Record<CardSection['kind'], string> = {
  warmup: '#6b7280',
  cooldown: '#6b7280',
  strength: '#7c3aed',
  engine: '#e0604a',
  core: '#0f9488',
};

export function WhiteboardCard({ card }: { card: Card }) {
  return (
    <View style={styles.card} accessibilityRole="summary">
      <Text style={styles.pill}>{card.date}</Text>
      <Text style={styles.title} accessibilityRole="header">
        {card.title}
      </Text>
      {card.tag ? <Text style={styles.tag}>{card.tag}</Text> : null}
      {card.sections.map((s, i) => (
        <View key={i} style={[styles.section, { borderLeftColor: SECTION_COLOURS[s.kind] }]}>
          <Text style={[styles.label, { color: SECTION_COLOURS[s.kind] }]}>{s.label}</Text>
          {s.lines.map((line, j) => (
            <Text key={j} style={styles.line}>
              {line}
            </Text>
          ))}
          {s.flow ? <Text style={styles.flow}>{s.flow}</Text> : null}
        </View>
      ))}
      {card.log ? <Text style={styles.log}>Log: {card.log}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, gap: 10, maxWidth: 640 },
  pill: { alignSelf: 'flex-start', fontSize: 13, color: '#374151' },
  title: { fontSize: 24, fontFamily: 'Georgia', color: '#111827' },
  tag: { alignSelf: 'flex-start', fontSize: 13, color: '#1f2937', backgroundColor: '#fde68a', paddingHorizontal: 8, borderRadius: 6 },
  section: { borderLeftWidth: 4, paddingLeft: 10, gap: 4 },
  label: { fontSize: 15, fontWeight: '700' },
  line: { fontSize: 16, color: '#111827' },
  flow: { fontSize: 15, color: '#111827', backgroundColor: '#f3f4f6', padding: 8, borderRadius: 6 },
  log: { fontSize: 14, color: '#374151', fontStyle: 'italic' },
});
