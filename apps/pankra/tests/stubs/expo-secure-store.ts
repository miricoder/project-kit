// The iPhone keychain is not under test in component tests: an in-memory stand-in.
const items = new Map<string, string>();
export async function getItemAsync(key: string) {
  return items.get(key) ?? null;
}
export async function setItemAsync(key: string, value: string) {
  items.set(key, value);
}
export async function deleteItemAsync(key: string) {
  items.delete(key);
}
