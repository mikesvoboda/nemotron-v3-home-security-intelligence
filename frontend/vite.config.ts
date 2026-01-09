import { defineConfig, loadEnv, type PluginOption } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

/**
 * Bundle Size Targets (NEM-1562)
 *
 * Target bundle sizes for the production build. These are guidelines
 * to monitor bundle growth over time.
 *
 * - Main bundle (vendor + app): < 500KB gzipped
 * - Largest chunk: < 250KB gzipped
 * - Total initial load: < 750KB gzipped
 *
 * Run `npm run analyze` to generate a visual bundle analysis report.
 * The report will be written to stats.html in the project root.
 */

export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), '');

  // Allow configurable backend URL for dev proxy (useful for remote development)
  const backendUrl = env.VITE_DEV_BACKEND_URL || 'http://localhost:8000';
  const wsBackendUrl = backendUrl.replace(/^http/, 'ws');

  // Enable bundle analysis when running with --mode analyze
  const isAnalyze = mode === 'analyze';

  // Build plugins array
  const plugins: PluginOption[] = [
    react(),
    // PWA plugin for service worker and offline support
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [
        'favicon.svg',
        'icons/icon-192.png',
        'icons/icon-512.png',
        'icons/badge-72.png',
        'icons/apple-touch-icon.png',
      ],
      manifest: false, // Use our custom manifest.json
      workbox: {
        // Cache first strategy for assets
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            // API requests - network first with fallback
            urlPattern: /\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 10,
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 5, // 5 minutes
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            // Images - cache first
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
        ],
        // Precache the app shell
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Skip waiting and claim clients immediately
        skipWaiting: true,
        clientsClaim: true,
      },
      devOptions: {
        // Enable PWA in development for testing
        enabled: true,
        type: 'module',
      },
    }) as PluginOption,
  ];

  // Add visualizer plugin for bundle analysis
  if (isAnalyze) {
    plugins.push(
      visualizer({
        filename: 'stats.html',
        open: true,
        gzipSize: true,
        brotliSize: true,
        template: 'treemap', // Options: 'treemap', 'sunburst', 'network'
      }) as PluginOption
    );
  }

  return {
    plugins,
    cacheDir: '.vitest',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
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
    build: {
      // Generate hidden source maps for production debugging
      // 'hidden' generates .map files but doesn't add //# sourceMappingURL= comment to bundles
      // This allows debugging via browser DevTools source map upload or error tracking services
      // while keeping .map files private (not served publicly by nginx)
      sourcemap: 'hidden',
      // Chunk size warning limit (in KB)
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          // Manual chunk splitting for optimal caching
          manualChunks: {
            // Vendor chunks - split large dependencies for better caching
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-ui': ['@tremor/react', '@headlessui/react', 'lucide-react'],
            'vendor-utils': ['clsx', 'tailwind-merge'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      // Exclude Playwright E2E tests - they should only be run via `npm run test:e2e`
      // Also exclude contract tests (Playwright-based API contract validation)
      exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**', 'tests/contract/**'],
      // Thread-based parallelization for faster execution
      pool: 'threads',
      // Test timeouts
      testTimeout: 30000,
      hookTimeout: 30000,
      teardownTimeout: 5000,
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
