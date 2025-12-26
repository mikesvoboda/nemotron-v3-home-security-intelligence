import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
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
    // Cache for faster subsequent runs
    cache: {
      dir: '.vitest',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/**',
        'src/test/**',
        'src/main.tsx',
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
        statements: 95,
        branches: 94,
        functions: 95,
        lines: 95,
      },
    },
  },
});
