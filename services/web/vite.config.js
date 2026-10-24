import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

const clientPort = process.env.VITE_HMR_CLIENT_PORT;
const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8080";

export default defineConfig({
  plugins: [vue()],
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    hmr: clientPort ? { clientPort: Number(clientPort) } : undefined,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/telemetry": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
