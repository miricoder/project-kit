import type { CredentialProvider, NodeSummary, Provider } from './types.ts';

export type Badge = 'green' | 'amber';

/**
 * Green when the chosen provider has everything the node `requires`, amber when not.
 * `apiKey` means a saved key for that provider; `strava` means a connected Strava account.
 */
export function nodeBadge(
  node: NodeSummary,
  provider: Provider,
  credentials: Array<{ provider: CredentialProvider }>,
): Badge {
  if (!node.providers[provider]) return 'amber';
  const have = new Set(credentials.map((c) => c.provider));
  for (const need of node.requires) {
    if (need === 'apiKey' && !have.has(provider)) return 'amber';
    if (need === 'strava' && !have.has('strava')) return 'amber';
  }
  return 'green';
}
