import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the service runs on :8080; the app calls it on the same origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/v1": "http://127.0.0.1:8080" } },
  build: { outDir: "dist", emptyOutDir: true },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
