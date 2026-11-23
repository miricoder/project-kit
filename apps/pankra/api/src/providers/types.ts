import type { JSONSchema, Provider } from '@pankra/shared';

export interface ToolDef {
  name: string;
  description: string;
  inputSchema: JSONSchema;
}

export interface AdapterRequest {
  system: string;
  input: unknown;
  images: Array<{ mime: string; data: Buffer }>;
  tools: ToolDef[];
  outputSchema: JSONSchema;
  model: string;
  apiKey: string;
}

export interface AdapterResult {
  output: unknown;
  tokensIn: number;
  tokensOut: number;
  costUsd: number;
}

/** One interface over every provider (docs/spec.md, Interfaces). */
export interface ProviderAdapter {
  id: Provider;
  run(req: AdapterRequest): Promise<AdapterResult>;
}

/** The provider answered with an error, or could not be reached. */
export class ProviderError extends Error {
  readonly provider: Provider;
  readonly status: number | null;

  // Plain fields, not parameter properties: `node --experimental-strip-types` runs this file.
  constructor(provider: Provider, status: number | null, message: string) {
    super(message);
    this.provider = provider;
    this.status = status;
  }
}

export type FetchLike = typeof fetch;

export const REQUEST_TIMEOUT_MS = 120_000;
