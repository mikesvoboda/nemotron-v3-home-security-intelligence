import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), '');

  // Allow configurable backend URL for dev proxy (useful for remote development)
  const backendUrl = env.VITE_DEV_BACKEND_URL || 'http://localhost:8000';
  const wsBackendUrl = backendUrl.replace(/^http/, 'ws');

  return {
    plugins: [react()],
    cacheDir: '.vitest',
    server: {
      port: 5173,
      strictPort: true,
      // Listen on all network interfaces to allow access from other machines on the network
      // This is needed for WebSocket connections when accessing via network IP (e.g., 192.168.x.x)
      host: true,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        '/ws': {
          target: wsBackendUrl,
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
          // Coverage thresholds - realistic targets based on current coverage
          // Lower than ideal due to hard-to-test UI code paths
          // Adjusted 2026-01-02 after UI audit feature additions
          statements: 83,
          branches: 77,
          functions: 81,
          lines: 84,
        },
      },
    },
  };
});
