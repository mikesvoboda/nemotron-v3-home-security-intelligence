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
 *
 * Advanced Build Optimizations:
 * - Module Preloading (NEM-3387): Configures modulepreload polyfill and strategy
 * - CSS Build Optimization (NEM-3388): PostCSS/Tailwind with esbuild minification
 * - Dynamic Import Chunk Naming (NEM-3438): Consistent [name]-[hash].js pattern
 * - Framer Motion Optimization (NEM-3439): Separate chunk for tree-shaking
 *
 * Vite Build Optimizations (NEM-3384 to NEM-3437):
 * - Manual Chunks (NEM-3384): Function-based chunk splitting for better caching
 * - Build Target (NEM-3385): Explicit ES2020 target with esbuild options
 * - Dependency Optimization (NEM-3386): Pre-bundles common dependencies
 * - Barrel File Tree Shaking (NEM-3436): Configures proper tree shaking
 * - Dev Server Warmup (NEM-3437): Warms up critical entry points
 *
 * Vite 7 Experimental Features (NEM-3782):
 * - Rolldown Build: Enables experimental Rolldown integration for transformation
 *   Note: Full Rolldown bundling and Oxc minification require rolldown-vite or Vite 8
 *   See: https://vite.dev/guide/rolldown for migration path
 */

export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), '');

  // Allow configurable backend URL for dev proxy (useful for remote development)
  const backendUrl = env.VITE_DEV_BACKEND_URL || 'http://localhost:8000';
  const wsBackendUrl = backendUrl.replace(/^http/, 'ws');

  // Enable bundle analysis when running with --mode analyze
  const isAnalyze = mode === 'analyze';
  // Disable PWA in test mode to prevent service worker interference with test cleanup
  const isTest = mode === 'test';

  // Build plugins array
  const plugins: PluginOption[] = [react()];

  // PWA plugin for service worker and offline support (disabled in test mode)
  if (!isTest) {
    plugins.push(VitePWA({
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
    }) as PluginOption);
  }

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
    // NEM-3782: Vite 7 Experimental Features for Faster Builds
    // Enable experimental Rolldown integration for transformation
    // Note: In Vite 7, this enables Rolldown for some internal operations but
    // production bundling still uses Rollup. For full Rolldown bundling and
    // Oxc minification, migrate to rolldown-vite or wait for Vite 8.
    // See: https://vite.dev/guide/rolldown
    experimental: {
      rolldownBuild: true,
    },
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
      // NEM-3437: Dev server warmup configuration
      // Pre-transform critical entry points for faster initial page loads
      warmup: {
        // Client-side files to pre-transform on dev server start
        clientFiles: [
          // Main entry point
          './src/main.tsx',
          // Core app structure
          './src/App.tsx',
          // Critical components loaded on first page
          './src/components/dashboard/DashboardPage.tsx',
          './src/components/layout/Layout.tsx',
          './src/components/layout/Sidebar.tsx',
          // Core hooks and services
          './src/hooks/useEventsQuery.ts',
          './src/hooks/useWebSocket.ts',
          './src/services/api.ts',
          // Style entry point
          './src/styles/index.css',
        ],
      },
    },
    // NEM-3386: Dependency pre-bundling optimization for faster dev server
    optimizeDeps: {
      // Explicitly include commonly used dependencies for pre-bundling
      // This improves dev server cold start time by preparing these upfront
      include: [
        // React ecosystem
        'react',
        'react-dom',
        'react-dom/client',
        'react-router-dom',
        // UI libraries
        '@tremor/react',
        '@headlessui/react',
        'lucide-react',
        'framer-motion',
        // State management
        'zustand',
        '@tanstack/react-query',
        // Form handling
        'react-hook-form',
        '@hookform/resolvers',
        'zod',
        // Utilities
        'clsx',
        'date-fns',
        'sonner',
        // Data compression
        'pako',
        'lru-cache',
      ],
      // Exclude packages that should not be pre-bundled
      // (e.g., packages with special ESM handling requirements)
      exclude: [
        // PWA-related packages work better when not pre-bundled
        'workbox-window',
      ],
      // Force re-optimization when these change
      // This ensures pre-bundled deps stay in sync with actual usage
      entries: ['./src/main.tsx', './index.html'],
      // Enable esbuild optimization for pre-bundling
      esbuildOptions: {
        // Target modern browsers for better tree shaking
        target: 'es2020',
        // Enable JSX automatic runtime
        jsx: 'automatic',
      },
    },
    build: {
      // NEM-3385: Explicit build target for consistent output
      // ES2020 provides good browser support while enabling modern features
      target: 'es2020',
      // NEM-3782: Minification via esbuild (default for Vite 7)
      // Note: Oxc minification will be available in Vite 8/rolldown-vite
      minify: 'esbuild',
      // Generate hidden source maps for production debugging
      // 'hidden' generates .map files but doesn't add //# sourceMappingURL= comment to bundles
      // This allows debugging via browser DevTools source map upload or error tracking services
      // while keeping .map files private (not served publicly by nginx)
      sourcemap: 'hidden',
      // Chunk size warning limit (in KB)
      chunkSizeWarningLimit: 500,
      // Module preloading configuration (NEM-3387)
      // Polyfill ensures modulepreload works in older browsers
      // resolveDependencies enables selective preloading of critical chunks
      modulePreload: {
        polyfill: true,
        resolveDependencies: (filename, deps) => {
          // Preload critical vendor chunks when main bundle loads
          // This improves perceived performance by loading dependencies early
          const criticalChunks = ['vendor-react', 'vendor-ui'];
          return deps.filter((dep) => criticalChunks.some((chunk) => dep.includes(chunk)));
        },
      },
      // CSS Minification (NEM-3388): Using esbuild (default) for Tailwind compatibility
      // Note: lightningcss is incompatible with Tailwind's @apply/@tailwind directives
      // and arbitrary selector syntax (e.g., [appearance:textfield])
      rollupOptions: {
        output: {
          // Dynamic import chunk naming convention (NEM-3438)
          // Consistent [name]-[hash].js pattern for better cache management
          chunkFileNames: 'assets/[name]-[hash].js',
          entryFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash][extname]',
          // NEM-3384: Manual chunk splitting DISABLED
          // The previous function-based chunking caused circular import deadlocks
          // between vendor-react and vendor-misc due to shared interop helpers.
          // Rollup/Rolldown's natural chunking handles this correctly.
          // TODO: Re-enable with a more sophisticated approach that accounts for
          // interop helper dependencies (see NEM-XXXX for E2E test).
          // manualChunks: undefined,
        },
        // NEM-3436: Tree shaking configuration for barrel files
        // Enables aggressive dead code elimination for barrel exports
        treeshake: {
          // Enable aggressive tree shaking - external modules not assumed to have side effects
          moduleSideEffects: 'no-external',
          // Treat property access as side-effect free for better elimination
          propertyReadSideEffects: false,
          // Remove unused exports from chunks
          tryCatchDeoptimization: false,
        },
      },
    },
    // CSS Configuration (NEM-3388)
    // Using PostCSS with Tailwind (defined in postcss.config.js)
    // Note: lightningcss incompatible with Tailwind's @apply/@tailwind directives
    // esbuild handles CSS minification (default) for best compatibility
    css: {
      // PostCSS config is auto-detected from postcss.config.js
      // Includes Tailwind CSS and Autoprefixer
      devSourcemap: true, // Source maps for dev debugging
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      // Exclude Playwright E2E tests - they should only be run via `npm run test:e2e`
      // Also exclude contract tests (Playwright-based API contract validation)
      exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**', 'tests/contract/**'],
      // Fork-based parallelization for better memory isolation (each fork is separate process)
      // Threads share memory which can cause accumulation issues during cleanup
      pool: 'forks',
      // Run test files sequentially within each shard to prevent memory accumulation
      // This is slower but prevents OOM by allowing cleanup between files
      fileParallelism: false,
      // Restart worker after each test file to prevent memory accumulation
      // This is critical for preventing OOM during long test runs
      isolate: true,
      // Test timeouts
      testTimeout: 30000,
      hookTimeout: 30000,
      // Force quick cleanup to prevent OOM during teardown
      // A shorter timeout forces cleanup to abort before OOM
      teardownTimeout: 3000,
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
