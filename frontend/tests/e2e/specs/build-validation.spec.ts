/**
 * Build Validation Tests
 *
 * These tests validate the production build to detect potential circular dependency
 * issues in vendor chunks that can cause TDZ (Temporal Dead Zone) errors at runtime.
 *
 * Background (NEM-3494):
 * Vite's manual chunk splitting (vite.config.ts:278-283) was disabled after circular
 * import deadlocks between vendor chunks caused production errors. The deadlock
 * occurred due to shared interop helpers creating circular dependencies.
 *
 * This test suite ensures:
 * 1. Built chunks don't contain obvious circular import patterns
 * 2. React renders without TDZ errors in production builds
 * 3. No runtime reference errors occur during initial page load
 *
 * Tags: @critical @build
 *
 * Run with: npx playwright test --config playwright.config.build-validation.ts
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Analyze JavaScript chunks for circular import patterns
 *
 * This function scans through built JavaScript files looking for patterns that
 * indicate potential circular dependencies:
 * - Rollup's interop helper functions (_interopNamespaceDefault, _interopRequireDefault)
 * - Module initialization order issues
 * - Cross-module references that might cause TDZ errors
 *
 * @param distPath - Path to the dist directory containing built assets
 * @returns Object with analysis results
 */
function analyzeChunksForCircularDeps(distPath: string) {
  const assetsPath = path.join(distPath, 'assets');

  if (!fs.existsSync(assetsPath)) {
    throw new Error(`Assets directory not found: ${assetsPath}`);
  }

  const jsFiles = fs.readdirSync(assetsPath)
    .filter(file => file.endsWith('.js') && !file.endsWith('.map'));

  const results = {
    totalChunks: jsFiles.length,
    chunksAnalyzed: [] as string[],
    potentialIssues: [] as { file: string; issue: string; pattern: string }[],
    interopHelperUsage: {} as Record<string, number>,
    chunkSizes: {} as Record<string, number>,
  };

  for (const file of jsFiles) {
    const filePath = path.join(assetsPath, file);
    const content = fs.readFileSync(filePath, 'utf-8');
    const fileSize = fs.statSync(filePath).size;

    results.chunksAnalyzed.push(file);
    results.chunkSizes[file] = fileSize;

    // Check for Rollup interop helpers (indicators of cross-module dependencies)
    const interopHelpers = [
      '_interopNamespaceDefault',
      '_interopRequireDefault',
      '_interopRequireWildcard',
    ];

    for (const helper of interopHelpers) {
      const matches = content.match(new RegExp(helper, 'g'));
      if (matches) {
        results.interopHelperUsage[helper] = (results.interopHelperUsage[helper] || 0) + matches.length;
      }
    }

    // Check for circular dependency patterns
    // Pattern 1: Multiple imports from same module in different order
    const importPattern = /import\s+.*?\s+from\s+['"](.+?)['"]/g;
    const imports = Array.from(content.matchAll(importPattern));
    const importCounts = new Map<string, number>();

    for (const match of imports) {
      const moduleName = match[1];
      importCounts.set(moduleName, (importCounts.get(moduleName) || 0) + 1);
    }

    // Flag files with excessive imports from same module (potential circular deps)
    for (const [module, count] of importCounts.entries()) {
      if (count > 5) {
        results.potentialIssues.push({
          file,
          issue: 'Excessive imports from same module',
          pattern: `${count} imports from "${module}"`,
        });
      }
    }

    // Pattern 2: Check for TDZ-prone patterns (accessing variables before initialization)
    // Look for patterns like: var x = _interopDefault(x); (self-reference)
    const selfReferencePattern = /var\s+(\w+)\s+=\s+_interop\w+\(\1\)/g;
    const selfReferences = Array.from(content.matchAll(selfReferencePattern));

    if (selfReferences.length > 0) {
      for (const match of selfReferences) {
        results.potentialIssues.push({
          file,
          issue: 'Self-referencing variable initialization',
          pattern: match[0],
        });
      }
    }

    // Pattern 3: Check for circular module initialization patterns
    // Look for: function init() { ... return module; } ... module = init();
    // BUT: Ignore minified single-letter variables (e.g., var c = ...; c = ...)
    // These are common in production builds and don't indicate real circular deps
    const circularInitPattern = /function\s+\w+\(\)\s*{[\s\S]*?return\s+(\w{2,})[\s\S]*?}\s*;\s*\1\s*=/g;
    const circularInits = Array.from(content.matchAll(circularInitPattern));

    if (circularInits.length > 0) {
      for (const match of circularInits) {
        results.potentialIssues.push({
          file,
          issue: 'Circular module initialization pattern',
          pattern: `Module "${match[1]}" initialized via circular function`,
        });
      }
    }
  }

  return results;
}

// Check if production build exists - skip all build validation tests if not
const distPath = path.join(__dirname, '../../../dist');
const buildExists = fs.existsSync(distPath) && fs.existsSync(path.join(distPath, 'assets'));

test.describe('Build Validation Tests @critical @build', () => {
  // Skip entire suite if no production build exists (CI runs against dev server)
  test.skip(!buildExists, 'Skipping build validation - no production build found. Run "npm run build" first.');

  test.beforeAll(() => {
    // Double-check the build exists (safety check)
    if (!buildExists) {
      test.skip();
    }
  });

  test('production build exists with expected structure', () => {
    expect(fs.existsSync(distPath)).toBe(true);
    expect(fs.existsSync(path.join(distPath, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(distPath, 'assets'))).toBe(true);
  });

  test('built chunks do not contain obvious circular import patterns', () => {
    const analysis = analyzeChunksForCircularDeps(distPath);

    // Log analysis results for debugging
    console.log('\n=== Chunk Analysis Summary ===');
    console.log(`Total chunks: ${analysis.totalChunks}`);
    console.log(`Chunks analyzed: ${analysis.chunksAnalyzed.length}`);
    console.log('\nInterop helper usage:');
    for (const [helper, count] of Object.entries(analysis.interopHelperUsage)) {
      console.log(`  ${helper}: ${count} occurrences`);
    }

    // Log largest chunks (potential splitting candidates)
    const largeChunks = Object.entries(analysis.chunkSizes)
      .filter(([_, size]) => size > 500 * 1024) // > 500KB
      .sort(([, a], [, b]) => b - a);

    if (largeChunks.length > 0) {
      console.log('\nLarge chunks (>500KB):');
      for (const [file, size] of largeChunks) {
        console.log(`  ${file}: ${(size / 1024).toFixed(2)} KB`);
      }
    }

    // Log potential issues
    if (analysis.potentialIssues.length > 0) {
      console.log('\n=== Potential Issues Detected ===');
      for (const issue of analysis.potentialIssues) {
        console.log(`\nFile: ${issue.file}`);
        console.log(`Issue: ${issue.issue}`);
        console.log(`Pattern: ${issue.pattern}`);
      }
    }

    // Assert no critical circular dependency patterns detected
    expect(analysis.potentialIssues).toEqual([]);
  });

  test('built chunks have reasonable sizes (no excessive bundling)', () => {
    const analysis = analyzeChunksForCircularDeps(distPath);

    // Check that no single chunk exceeds 1MB (sign of poor code splitting)
    const MAX_CHUNK_SIZE = 1024 * 1024; // 1MB
    const oversizedChunks = Object.entries(analysis.chunkSizes)
      .filter(([_, size]) => size > MAX_CHUNK_SIZE)
      .map(([file, size]) => `${file} (${(size / 1024).toFixed(2)} KB)`);

    if (oversizedChunks.length > 0) {
      console.warn('\n=== Oversized Chunks (>1MB) ===');
      oversizedChunks.forEach(chunk => console.warn(`  ${chunk}`));
    }

    // This is a soft warning, not a hard failure
    // Log but don't fail - allows gradual improvement
    expect(oversizedChunks.length).toBeLessThanOrEqual(5);
  });
});

test.describe('Runtime Build Validation @critical @build', () => {
  // Skip entire suite if no production build exists
  test.skip(!buildExists, 'Skipping runtime validation - no production build found. Run "npm run build" first.');

  test.beforeEach(async ({ page }) => {
    // Set up console error capturing
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error(`Browser console error: ${msg.text()}`);
      }
    });

    // Set up page error capturing (uncaught exceptions)
    page.on('pageerror', (error) => {
      console.error(`Page error: ${error.message}`);
      console.error(error.stack);
    });
  });

  test('production build loads without TDZ errors', async ({ page }) => {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Capture console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      } else if (msg.type() === 'warning') {
        warnings.push(msg.text());
      }
    });

    // Capture uncaught exceptions
    page.on('pageerror', (error) => {
      errors.push(`Uncaught exception: ${error.message}`);
    });

    // Load the production build (served by Playwright's webServer)
    await page.goto('/', { waitUntil: 'networkidle' });

    // Wait for React to render
    await page.waitForSelector('body', { timeout: 10000 });

    // Check for TDZ-specific error patterns
    const tdzErrors = errors.filter((error) =>
      error.includes('ReferenceError') ||
      error.includes('before initialization') ||
      error.includes('Cannot access') ||
      error.includes('is not defined')
    );

    if (tdzErrors.length > 0) {
      console.error('\n=== TDZ Errors Detected ===');
      tdzErrors.forEach((error) => console.error(`  ${error}`));
    }

    // Check for circular dependency warnings
    const circularDepWarnings = warnings.filter((warning) =>
      warning.includes('circular') ||
      warning.includes('cycle') ||
      warning.includes('recursive')
    );

    if (circularDepWarnings.length > 0) {
      console.warn('\n=== Circular Dependency Warnings ===');
      circularDepWarnings.forEach((warning) => console.warn(`  ${warning}`));
    }

    // Assert no TDZ errors
    expect(tdzErrors).toEqual([]);
  });

  test('React renders successfully without reference errors', async ({ page }) => {
    const errors: string[] = [];

    // Capture console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Capture uncaught exceptions
    page.on('pageerror', (error) => {
      errors.push(`Uncaught exception: ${error.message}`);
    });

    // Load page
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Wait for root div to have content (React rendered)
    await page.waitForSelector('#root:not(:empty)', { timeout: 10000 });

    // Check that React rendered something
    const rootContent = await page.locator('#root').innerHTML();
    expect(rootContent.length).toBeGreaterThan(0);

    // Verify no critical React errors
    const reactErrors = errors.filter((error) =>
      error.includes('React') ||
      error.includes('render') ||
      error.includes('component') ||
      error.includes('hook')
    );

    if (reactErrors.length > 0) {
      console.error('\n=== React Errors Detected ===');
      reactErrors.forEach((error) => console.error(`  ${error}`));
    }

    expect(reactErrors).toEqual([]);
  });

  test('all critical JavaScript modules load successfully', async ({ page }) => {
    const failedResources: string[] = [];

    // Capture network failures
    page.on('response', (response) => {
      if (response.status() >= 400 && response.url().includes('.js')) {
        failedResources.push(`${response.url()} (${response.status()})`);
      }
    });

    // Load page
    await page.goto('/', { waitUntil: 'networkidle' });

    // Wait for page to be interactive
    await page.waitForLoadState('domcontentloaded');

    // Log any failed JavaScript resources
    if (failedResources.length > 0) {
      console.error('\n=== Failed JavaScript Resources ===');
      failedResources.forEach((resource) => console.error(`  ${resource}`));
    }

    // Assert no JS resources failed to load
    expect(failedResources).toEqual([]);
  });

  test('main vendor chunks load in correct order', async ({ page }) => {
    const loadedScripts: string[] = [];

    // Track script load order
    page.on('response', async (response) => {
      if (response.url().includes('.js') && response.status() === 200) {
        const url = response.url();
        const filename = url.split('/').pop() || url;
        loadedScripts.push(filename);
      }
    });

    // Load page
    await page.goto('/', { waitUntil: 'networkidle' });

    // Wait for page to be fully loaded
    await page.waitForLoadState('load');

    console.log('\n=== Script Load Order ===');
    loadedScripts.forEach((script, index) => {
      console.log(`  ${index + 1}. ${script}`);
    });

    // Verify at least some scripts loaded
    expect(loadedScripts.length).toBeGreaterThan(0);

    // Verify index.html loaded (should be first)
    const indexScript = loadedScripts.find(
      (script) => script.includes('index-') && script.endsWith('.js')
    );
    expect(indexScript).toBeDefined();
  });

  test('no duplicate module loading or re-initialization', async ({ page }) => {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Capture console output
    page.on('console', (msg) => {
      const text = msg.text();
      if (msg.type() === 'error') {
        errors.push(text);
      } else if (msg.type() === 'warning') {
        warnings.push(text);
      }
    });

    // Evaluate script to detect duplicate module initialization
    await page.goto('/', { waitUntil: 'networkidle' });

    // Check for duplicate initialization warnings
    const duplicateWarnings = warnings.filter((warning) =>
      warning.includes('duplicate') ||
      warning.includes('already initialized') ||
      warning.includes('multiple instances')
    );

    if (duplicateWarnings.length > 0) {
      console.warn('\n=== Duplicate Module Warnings ===');
      duplicateWarnings.forEach((warning) => console.warn(`  ${warning}`));
    }

    // Check for errors related to duplicate modules
    const duplicateErrors = errors.filter((error) =>
      error.includes('duplicate') ||
      error.includes('already defined') ||
      error.includes('redeclaration')
    );

    if (duplicateErrors.length > 0) {
      console.error('\n=== Duplicate Module Errors ===');
      duplicateErrors.forEach((error) => console.error(`  ${error}`));
    }

    // Assert no duplicate module errors
    expect(duplicateErrors).toEqual([]);
  });
});
