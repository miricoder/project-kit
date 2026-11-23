import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Same JSX transform as Expo: no React import needed in components.
  esbuild: { jsx: 'automatic' },
  resolve: {
    alias: {
      // App components render through react-native-web, as they do in the web app.
      'react-native': 'react-native-web',
      'expo-router': fileURLToPath(new URL('./tests/stubs/expo-router.tsx', import.meta.url)),
      'expo-constants': fileURLToPath(new URL('./tests/stubs/expo-constants.ts', import.meta.url)),
    },
  },
  test: { include: ['tests/**/*.test.{ts,tsx}'] },
});
