import { defineConfig } from "vite";

// In dev (`npm run dev`) API and WebSocket calls are proxied to the backend,
// mirroring what nginx does in the Docker setup.
const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
});
