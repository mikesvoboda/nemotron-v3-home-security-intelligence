/**
 * Tests for Vite configuration optimizations
 *
 * These tests verify that the Vite configuration includes the required
 * performance optimizations for dev server warmup and module preloading.
 *
 * @module __tests__/vite-config.test
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { beforeAll, describe, expect, it } from 'vitest';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Vite Configuration', () => {
  const viteConfigPath = path.resolve(__dirname, '../../vite.config.ts');
  let viteConfigContent: string;

  // Read the Vite config file once for all tests
  beforeAll(() => {
    viteConfigContent = fs.readFileSync(viteConfigPath, 'utf-8');
  });

  describe('Dev Server Warmup (NEM-3784)', () => {
    it('has warmup configuration in server settings', () => {
      expect(viteConfigContent).toContain('warmup:');
    });

    it('pre-transforms main entry point', () => {
      expect(viteConfigContent).toContain('./src/main.tsx');
    });

    it('pre-transforms App component', () => {
      expect(viteConfigContent).toContain('./src/App.tsx');
    });

    it('pre-transforms DashboardPage (first page load)', () => {
      expect(viteConfigContent).toContain('./src/components/dashboard/DashboardPage.tsx');
    });

    it('pre-transforms Layout components', () => {
      expect(viteConfigContent).toContain('./src/components/layout/Layout.tsx');
      expect(viteConfigContent).toContain('./src/components/layout/Sidebar.tsx');
    });

    it('pre-transforms core hooks', () => {
      expect(viteConfigContent).toContain('./src/hooks/useEventsQuery.ts');
      expect(viteConfigContent).toContain('./src/hooks/useWebSocket.ts');
    });

    it('pre-transforms API service', () => {
      expect(viteConfigContent).toContain('./src/services/api.ts');
    });

    it('pre-transforms style entry point', () => {
      expect(viteConfigContent).toContain('./src/styles/index.css');
    });

    it('has clientFiles array for warmup', () => {
      expect(viteConfigContent).toContain('clientFiles:');
    });
  });

  describe('Module Preload Configuration (NEM-3783)', () => {
    it('has modulePreload configuration in build settings', () => {
      expect(viteConfigContent).toContain('modulePreload:');
    });

    it('enables modulePreload polyfill for older browsers', () => {
      expect(viteConfigContent).toContain('polyfill: true');
    });

    it('has resolveDependencies function for selective preloading', () => {
      expect(viteConfigContent).toContain('resolveDependencies:');
    });

    it('preloads critical vendor chunks (vendor-react, vendor-ui)', () => {
      expect(viteConfigContent).toContain('vendor-react');
      expect(viteConfigContent).toContain('vendor-ui');
    });

    it('filters dependencies to only preload critical chunks', () => {
      expect(viteConfigContent).toContain('criticalChunks');
      expect(viteConfigContent).toContain('.filter');
    });
  });

  describe('Dependency Pre-bundling (optimizeDeps)', () => {
    it('has optimizeDeps configuration', () => {
      expect(viteConfigContent).toContain('optimizeDeps:');
    });

    it('includes React ecosystem for pre-bundling', () => {
      expect(viteConfigContent).toContain("'react',");
      expect(viteConfigContent).toContain("'react-dom',");
      expect(viteConfigContent).toContain("'react-router-dom',");
    });

    it('includes UI libraries for pre-bundling', () => {
      expect(viteConfigContent).toContain("'@tremor/react',");
      expect(viteConfigContent).toContain("'@headlessui/react',");
      expect(viteConfigContent).toContain("'lucide-react',");
    });

    it('includes state management libraries', () => {
      expect(viteConfigContent).toContain("'zustand',");
      expect(viteConfigContent).toContain("'@tanstack/react-query',");
    });

    it('has esbuildOptions for optimization', () => {
      expect(viteConfigContent).toContain('esbuildOptions:');
      expect(viteConfigContent).toContain("target: 'es2020'");
    });
  });

  describe('Build Configuration', () => {
    it('has explicit ES2020 build target', () => {
      expect(viteConfigContent).toContain("target: 'es2020'");
    });

    it('uses esbuild minification', () => {
      expect(viteConfigContent).toContain("minify: 'esbuild'");
    });

    it('has tree shaking configuration', () => {
      expect(viteConfigContent).toContain('treeshake:');
      expect(viteConfigContent).toContain('propertyReadSideEffects: false');
    });

    it('has chunk naming convention', () => {
      expect(viteConfigContent).toContain("chunkFileNames: 'assets/[name]-[hash].js'");
    });
  });
});
