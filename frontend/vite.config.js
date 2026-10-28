import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, Vite reenvía /api al backend: el navegador ve un único origen y no hace falta CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY || "http://127.0.0.1:8000",
    },
  },
});
