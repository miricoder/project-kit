import { costUsd } from './pricing.ts';
import {
  ProviderError,
  REQUEST_TIMEOUT_MS,
  type AdapterRequest,
  type AdapterResult,
  type FetchLike,
  type ProviderAdapter,
} from './types.ts';

const URL = 'https://api.openai.com/v1/responses';

/** OpenAI Responses API with a JSON-schema text format for structured output. */
export function gptAdapter(fetchImpl: FetchLike): ProviderAdapter {
  return {
    id: 'gpt',
    async run(req: AdapterRequest): Promise<AdapterResult> {
      const content: unknown[] = [{ type: 'input_text', text: JSON.stringify(req.input) }];
      for (const img of req.images) {
        content.push({ type: 'input_image', image_url: `data:${img.mime};base64,${img.data.toString('base64')}` });
      }
      const body = {
        model: req.model,
        instructions: req.system,
        input: [{ role: 'user', content }],
        text: { format: { type: 'json_schema', name: 'output', schema: req.outputSchema, strict: false } },
        tools: req.tools.map((t) => ({ type: 'function', name: t.name, description: t.description, parameters: t.inputSchema })),
      };
      let res: Response;
      try {
        res = await fetchImpl(URL, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${req.apiKey}` },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
      } catch (e) {
        throw new ProviderError('gpt', null, `OpenAI could not be reached: ${(e as Error).message}`);
      }
      const json = (await res.json().catch(() => null)) as any;
      if (!res.ok) {
        const message = json?.error?.message ?? res.statusText ?? 'unknown error';
        throw new ProviderError('gpt', res.status, `OpenAI returned HTTP ${res.status}: ${message}`);
      }
      const text = (json?.output ?? [])
        .filter((o: any) => o.type === 'message')
        .flatMap((o: any) => o.content ?? [])
        .filter((c: any) => c.type === 'output_text')
        .map((c: any) => c.text)
        .join('');
      let output: unknown;
      try {
        output = JSON.parse(text);
      } catch {
        // Not JSON at all: hand it to validation, which fails it and asks for a repair.
        output = text;
      }
      const tokensIn = Number(json.usage?.input_tokens ?? 0);
      const tokensOut = Number(json.usage?.output_tokens ?? 0);
      return { output, tokensIn, tokensOut, costUsd: costUsd(req.model, tokensIn, tokensOut) };
    },
  };
}
