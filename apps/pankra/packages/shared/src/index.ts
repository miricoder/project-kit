import { z } from 'zod';

/** Fields every stored document carries (spec: Data model). */
export const BaseDocument = z.object({
  userId: z.string().min(1),
  schemaVersion: z.number().int().positive(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
});
export type BaseDocument = z.infer<typeof BaseDocument>;

export const SignInRequest = z.object({ email: z.string().email() });
export type SignInRequest = z.infer<typeof SignInRequest>;

export const VerifyRequest = z.object({
  token: z.string().min(20),
  client: z.enum(['web', 'ios']).default('web'),
});
export type VerifyRequest = z.infer<typeof VerifyRequest>;

export const Me = z.object({ userId: z.string(), email: z.string().email() });
export type Me = z.infer<typeof Me>;

export const Health = z.object({ ok: z.boolean(), db: z.boolean(), version: z.string() });
export type Health = z.infer<typeof Health>;

export const API_PREFIX = '/api/v1';
