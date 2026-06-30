import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@core': r('./src/core'),
      '@exchange': r('./src/exchange'),
      '@dex': r('./src/dex'),
      '@cex': r('./src/cex'),
      '@models': r('./src/models'),
      '@backtester': r('./src/backtester'),
      '@simulator': r('./src/simulator'),
    },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    globals: false,
    coverage: {
      provider: 'v8',
      include: ['src/core/**', 'src/models/**', 'src/exchange/**', 'src/simulator/**'],
    },
  },
});
