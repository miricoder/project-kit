// The app's own version (baked in at build time) and the two decisions the update notice
// makes: has this device just been updated, and is a newer version waiting on the server?
declare const __APP_VERSION__: string;

export const APP_VERSION: string = typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "dev";

export type Notice = "first-run" | "updated" | "none";

/** After opening: what to tell the user, given the version this device last ran. */
export function afterOpen(seen: string | undefined | null, running: string): Notice {
  if (!seen) return "first-run";
  return seen === running ? "none" : "updated";
}

/** While open: offer a reload when the server runs a different build than this page. A
 * rolled-back server counts too: the page should match what the server serves. */
export function offerReload(serverVersion: string | undefined | null, running: string): boolean {
  return !!serverVersion && serverVersion !== running;
}

/** "v1.2.0-3-gabc123" -> "1.2.0-3-gabc123"; what the user sees. */
export function shown(version: string): string {
  return version.replace(/^v(?=\d)/, "");
}
