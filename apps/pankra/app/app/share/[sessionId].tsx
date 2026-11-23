import { useEffect, useState } from 'react';
import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';
import type { PostTheme } from '@pankra/shared';
import { IS_PREVIEW, api } from '../../src/api';
import { savePostPng } from '../../src/demo/download';

const THEMES: Array<{ id: PostTheme; label: string }> = [
  { id: 'whiteboard', label: 'Whiteboard' },
  { id: 'game-inspired', label: 'Game-inspired' },
  { id: 'clean', label: 'Clean' },
];

/** Share: the day's workout as a 1080 x 1350 Instagram post. */
export default function Share() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [theme, setTheme] = useState<PostTheme>('whiteboard');
  const [url, setUrl] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.postUrl(sessionId, theme).then((u) => live && setUrl(u));
    return () => {
      live = false;
    };
  }, [sessionId, theme]);

  async function download() {
    if (!url) return;
    setMessage(null);
    if (!IS_PREVIEW) return void Linking.openURL(url);
    try {
      setMessage(await savePostPng(url, `pankra-${theme}.png`));
    } catch (e) {
      setMessage((e as Error).message);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: 'Share' }} />
      <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel="Theme">
        {THEMES.map((t) => (
          <Pressable
            key={t.id}
            accessibilityRole="radio"
            accessibilityState={{ checked: theme === t.id }}
            onPress={() => setTheme(t.id)}
            style={[styles.chip, theme === t.id && styles.chipOn]}
          >
            <Text style={theme === t.id ? styles.chipTextOn : undefined}>{t.label}</Text>
          </Pressable>
        ))}
      </View>
      {url ? (
        <Image
          source={{ uri: url }}
          style={styles.preview}
          resizeMode="contain"
          accessibilityLabel={`The day's workout as a post, ${theme} theme`}
        />
      ) : null}
      <Pressable accessibilityRole="button" onPress={download} style={styles.button}>
        <Text style={styles.buttonText}>Download PNG (1080 × 1350)</Text>
      </Pressable>
      {message ? <Text accessibilityLiveRegion="polite">{message}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 12, maxWidth: 560 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#9ca3af', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  chipOn: { backgroundColor: '#111827', borderColor: '#111827' },
  chipTextOn: { color: '#fff' },
  preview: { width: '100%', aspectRatio: 1080 / 1350, backgroundColor: '#e5e7eb', borderRadius: 8 },
  button: { backgroundColor: '#111827', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
