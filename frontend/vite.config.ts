import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  cacheDir: '.vitest',
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    // Exclude Playwright E2E tests - they should only be run via `npm run test:e2e`
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**'],
    // Memory optimization: use forks pool with single fork to prevent heap out of memory
    pool: 'forks',
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
    // Test timeouts
    testTimeout: 10000,
    hookTimeout: 10000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/**',
        'src/test/**',
        'src/main.tsx',
        'src/types/generated/**',
        '**/*.d.ts',
        '**/*.test.{ts,tsx}',
        '**/index.ts',
        '**/*.example.tsx',
        '**/Example.tsx',
        '*.config.{js,ts,cjs,mjs}',
        '.eslintrc.cjs',
        'postcss.config.js',
        'tailwind.config.js',
      ],
      thresholds: {
        // Coverage thresholds set to realistic levels based on testable code paths
        // Some code is intentionally untestable (e.g., animation branches in RiskGauge
        // that only run in non-test mode via import.meta.env.MODE checks)
        statements: 92,
        branches: 88,
        functions: 90,
        lines: 93,
      },
    },
  },
});
