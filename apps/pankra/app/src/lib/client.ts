import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { createApi, type TokenStore } from './api';

const KEY = 'pankra.session';

const secureStore: TokenStore = {
  get: () => SecureStore.getItemAsync(KEY),
  set: (v) => SecureStore.setItemAsync(KEY, v),
  clear: () => SecureStore.deleteItemAsync(KEY),
};

export const api = createApi({
  baseUrl: process.env.EXPO_PUBLIC_API_URL ?? '',
  platform: Platform.OS === 'web' ? 'web' : 'ios',
  tokenStore: Platform.OS === 'web' ? undefined : secureStore,
});
