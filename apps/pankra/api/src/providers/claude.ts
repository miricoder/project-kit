import { costUsd } from './pricing.ts';
import {
  ProviderError,
  REQUEST_TIMEOUT_MS,
  type AdapterRequest,
  type AdapterResult,
  type FetchLike,
  type ProviderAdapter,
} from './types.ts';

const URL = 'https://api.anthropic.com/v1/messages';

/**
 * Anthropic Messages API. Structured output is a forced tool call named `output` whose input
 * schema is the node's output schema.
 */
export function claudeAdapter(fetchImpl: FetchLike): ProviderAdapter {
  return {
    id: 'claude',
    async run(req: AdapterRequest): Promise<AdapterResult> {
      const content: unknown[] = req.images.map((img) => ({
        type: 'image',
        source: { type: 'base64', media_type: img.mime, data: img.data.toString('base64') },
      }));
      content.push({ type: 'text', text: JSON.stringify(req.input) });
      const body = {
        model: req.model,
        max_tokens: 4096,
        system: req.system,
        messages: [{ role: 'user', content }],
        tools: [
          { name: 'output', description: 'Return the result in this shape.', input_schema: req.outputSchema },
          ...req.tools.map((t) => ({ name: t.name, description: t.description, input_schema: t.inputSchema })),
        ],
        tool_choice: { type: 'tool', name: 'output' },
      };
      let res: Response;
      try {
        res = await fetchImpl(URL, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'x-api-key': req.apiKey,
            'anthropic-version': '2023-06-01',
          },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
      } catch (e) {
        throw new ProviderError('claude', null, `Claude could not be reached: ${(e as Error).message}`);
      }
      const json = (await res.json().catch(() => null)) as any;
      if (!res.ok) {
        const message = json?.error?.message ?? res.statusText ?? 'unknown error';
        throw new ProviderError('claude', res.status, `Claude returned HTTP ${res.status}: ${message}`);
      }
      const block = (json?.content ?? []).find((c: any) => c.type === 'tool_use' && c.name === 'output');
      if (!block) throw new ProviderError('claude', res.status, 'Claude returned no structured output');
      const tokensIn = Number(json.usage?.input_tokens ?? 0);
      const tokensOut = Number(json.usage?.output_tokens ?? 0);
      return { output: block.input, tokensIn, tokensOut, costUsd: costUsd(req.model, tokensIn, tokensOut) };
    },
  };
}
