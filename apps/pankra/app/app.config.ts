import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * app.json plus what differs per install:
 * - PANKRA_BUNDLE_ID: the iPhone app identity, e.g. com.yourname.pankra (docs/inputs-checklist.md #3)
 * - PANKRA_API_URL: the API the app talks to, e.g. https://pankra-api.onrender.com/api/v1
 * Only capabilities a free Apple account allows are used (no push, iCloud, Sign in with Apple).
 */
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...(config as ExpoConfig),
  ios: {
    ...config.ios,
    bundleIdentifier: process.env.PANKRA_BUNDLE_ID,
    supportsTablet: false,
    infoPlist: {
      ...config.ios?.infoPlist,
      ITSAppUsesNonExemptEncryption: false,
    },
  },
  extra: {
    ...config.extra,
    apiUrl: process.env.PANKRA_API_URL ?? config.extra?.apiUrl,
  },
});
