import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// UI-only build. The engine runs as a standalone Node process and talks to the
// UI over a local WebSocket (see src/core/wsserver.ts). Vite never bundles the
// engine, the fetchers, or anything that touches the network venues.
export default defineConfig({
  plugins: [react()],
  root: 'src/ui',
  resolve: {
    alias: {
      '@core': r('./src/core'),
      '@exchange': r('./src/exchange'),
      '@models': r('./src/models'),
    },
  },
  server: { port: 5173 },
  build: { outDir: '../../dist/ui', emptyOutDir: true },
});
