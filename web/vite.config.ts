import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";

// The version the image was built as (scripts/version.sh); the service reports the same one.
const fileVersion = existsSync("../app-version.txt") ? readFileSync("../app-version.txt", "utf8").trim() : "";
const APP_VERSION = process.env.APP_VERSION || fileVersion || "dev";

// In development the service runs on :8080; the app calls it on the same origin.
export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify(APP_VERSION) },
  server: { proxy: { "/v1": "http://127.0.0.1:8080" } },
  build: { outDir: "dist", emptyOutDir: true },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
