import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // same origin as the docker build, so CORS only ever needs localhost:3000
  server: { port: 3000, strictPort: true },
});
