// A small promise wrapper over IndexedDB: the device's outbox, read cache and capture log.
// Everything here is a copy; the server is the home of the data (docs/spec.md).

export type StoreName = "outbox" | "items" | "log" | "meta";
const DB_NAME = "dumpit";
const VERSION = 1;

let opening: Promise<IDBDatabase> | null = null;

export function open(): Promise<IDBDatabase> {
  if (!opening) {
    opening = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("outbox")) db.createObjectStore("outbox", { keyPath: "capture_id" });
        if (!db.objectStoreNames.contains("items")) db.createObjectStore("items", { keyPath: "key" });
        if (!db.objectStoreNames.contains("log")) db.createObjectStore("log", { keyPath: "capture_id" });
        if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta");
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => { opening = null; reject(req.error); };
    });
  }
  return opening;
}

function done<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function store(name: StoreName, mode: IDBTransactionMode): Promise<IDBObjectStore> {
  return (await open()).transaction(name, mode).objectStore(name);
}

export async function all<T>(name: StoreName): Promise<T[]> {
  return done((await store(name, "readonly")).getAll()) as Promise<T[]>;
}

export async function put(name: StoreName, value: unknown, key?: IDBValidKey): Promise<void> {
  await done((await store(name, "readwrite")).put(value, key));
}

export async function get<T>(name: StoreName, key: IDBValidKey): Promise<T | undefined> {
  return done((await store(name, "readonly")).get(key)) as Promise<T | undefined>;
}

export async function remove(name: StoreName, key: IDBValidKey): Promise<void> {
  await done((await store(name, "readwrite")).delete(key));
}

export async function clear(name: StoreName): Promise<void> {
  await done((await store(name, "readwrite")).clear());
}

export async function putMany(name: StoreName, values: unknown[]): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(name, "readwrite");
    const os = tx.objectStore(name);
    values.forEach((v) => os.put(v));
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/** Test helper: close and delete the database so each test starts empty. */
export async function _reset(): Promise<void> {
  if (opening) (await opening).close();
  opening = null;
  await new Promise<void>((resolve) => {
    const req = indexedDB.deleteDatabase(DB_NAME);
    req.onsuccess = req.onerror = req.onblocked = () => resolve();
  });
}
