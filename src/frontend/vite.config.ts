import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const packageJson = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf-8")
) as { version?: string };

const appVersion = process.env.VITE_APP_VERSION ?? packageJson.version ?? "dev";

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion)
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000"
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src")
    }
  }
});
