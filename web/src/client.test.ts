import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Client, type OutboxEntry, type SendResult } from "./client";
import * as idb from "./idb";

beforeEach(async () => {
  await idb._reset();
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ items: [], deleted: [], seq: 1, me: null }), { status: 200 }));
});

function scripted(results: SendResult[]) {
  const sent: string[] = [];
  const send = async (e: OutboxEntry) => { sent.push(e.text); return results.shift() ?? { kind: "filed", status: "filed", lines: [] } as SendResult; };
  return { sent, send };
}

describe("outbox", () => {
  it("saves first and sends oldest-first, one at a time", async () => {
    const { sent, send } = scripted([{ kind: "offline" }]);
    const c = new Client(send, [0, 0]);
    await c.capture("paid 42 for groceries");
    await c.flush();
    await c.capture("that was 24 not 42");
    await c.flush();
    expect(c.log.map((l) => l.status)).toEqual(["filed", "filed"]);
    expect(sent).toEqual(["paid 42 for groceries", "paid 42 for groceries", "that was 24 not 42"]);
    expect(await idb.all("outbox")).toEqual([]);
  });

  it("keeps the words when the network is down", async () => {
    const { send } = scripted([{ kind: "offline" }]);
    const c = new Client(send, [0, 0]);
    await c.capture("coffee 3.50");
    await c.flush();
    expect(c.log[0]).toMatchObject({ status: "waiting", reason: "you were offline" });
    expect((await idb.all<OutboxEntry>("outbox")).map((e) => e.text)).toEqual(["coffee 3.50"]);
  });

  it("retries twice, then offers Retry and keeps the capture", async () => {
    const err: SendResult = { kind: "retry", reason: "model provider unavailable" };
    const { sent, send } = scripted([err, err, err]);
    const c = new Client(send, [0, 0]);
    await c.capture("lunch 12");
    await c.flush();
    expect(sent.length).toBe(3);
    expect(c.log[0].status).toBe("failed");
    expect((await idb.all("outbox")).length).toBe(1);
    await c.retry(c.log[0].capture_id);
    expect(c.log[0].status).toBe("filed");
  });

  it("files a waiting capture even if its log line was lost", async () => {
    await idb.put("outbox", { capture_id: "c-1", text: "coffee 3.50", source: "typed",
      captured_at: "2026-02-23T09:00:00", tz: "Europe/Lisbon", created: 1, attempts: 0 });
    const { sent, send } = scripted([]);
    const c = new Client(send, [0, 0]);
    await c.flush();
    expect(sent).toEqual(["coffee 3.50"]);
    expect(c.log[0]).toMatchObject({ capture_id: "c-1", status: "filed" });
  });

  it("a daily limit keeps the capture waiting with the reason", async () => {
    const { send } = scripted([{ kind: "wait", reason: "Daily filing limit reached; it will file tomorrow" }]);
    const c = new Client(send, [0, 0]);
    await c.capture("coffee 3.50");
    await c.flush();
    expect(c.log[0]).toMatchObject({ status: "waiting", reason: "Daily filing limit reached; it will file tomorrow" });
  });
});
