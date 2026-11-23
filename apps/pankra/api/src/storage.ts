/**
 * Private object storage for uploads (Cloudflare R2 over the S3 API in production, with
 * 10-minute signed URLs). The in-memory store serves tests and local development.
 */
export interface ObjectStorage {
  put(key: string, bytes: Buffer, mime: string): Promise<void>;
  get(key: string): Promise<{ bytes: Buffer; mime: string } | undefined>;
}

export class MemoryStorage implements ObjectStorage {
  private objects = new Map<string, { bytes: Buffer; mime: string }>();

  async put(key: string, bytes: Buffer, mime: string): Promise<void> {
    this.objects.set(key, { bytes: Buffer.from(bytes), mime });
  }

  async get(key: string): Promise<{ bytes: Buffer; mime: string } | undefined> {
    const o = this.objects.get(key);
    return o && { bytes: Buffer.from(o.bytes), mime: o.mime };
  }
}
