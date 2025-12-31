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
    // Memory optimization and parallelization
    pool: 'forks',
    // Test timeouts
    testTimeout: 30000,
    hookTimeout: 30000,
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
        // Coverage thresholds - high quality targets with realistic branch expectations
        // Branches at 90% due to defensive code paths (switch defaults, error handlers)
        // Functions at 93% due to some animation/timing-sensitive code
        statements: 95,
        branches: 90,
        functions: 93,
        lines: 95,
      },
    },
  },
});
