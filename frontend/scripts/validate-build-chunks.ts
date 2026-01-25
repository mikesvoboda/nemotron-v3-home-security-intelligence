#!/usr/bin/env node
/**
 * Build Chunk Validation Script
 *
 * This script analyzes production build chunks for circular dependency patterns
 * that could cause TDZ (Temporal Dead Zone) errors at runtime.
 *
 * Background (NEM-3494):
 * Vite's manual chunk splitting was disabled after circular import deadlocks
 * between vendor chunks caused production errors. This script detects such issues.
 *
 * Usage:
 *   npm run build
 *   npm run validate:build-chunks
 *
 * Exit codes:
 *   0 - No issues detected
 *   1 - Circular dependency patterns detected
 *   2 - Build directory not found
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DIST_PATH = path.join(__dirname, '../dist');
const ASSETS_PATH = path.join(DIST_PATH, 'assets');

interface AnalysisResults {
  totalChunks: number;
  chunksAnalyzed: string[];
  potentialIssues: Array<{ file: string; issue: string; pattern: string }>;
  interopHelperUsage: Record<string, number>;
  chunkSizes: Record<string, number>;
}

/**
 * Analyze JavaScript chunks for circular import patterns
 */
function analyzeChunksForCircularDeps(): AnalysisResults {
  if (!fs.existsSync(ASSETS_PATH)) {
    console.error(`❌ Assets directory not found: ${ASSETS_PATH}`);
    console.error('   Run "npm run build" first to generate production build.');
    process.exit(2);
  }

  const jsFiles = fs.readdirSync(ASSETS_PATH)
    .filter(file => file.endsWith('.js') && !file.endsWith('.map'));

  const results: AnalysisResults = {
    totalChunks: jsFiles.length,
    chunksAnalyzed: [],
    potentialIssues: [],
    interopHelperUsage: {},
    chunkSizes: {},
  };

  for (const file of jsFiles) {
    const filePath = path.join(ASSETS_PATH, file);
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

    // Pattern 1: Self-referencing variable initialization (TDZ risk)
    // Example: var x = _interopDefault(x);
    const selfReferencePattern = /var\s+(\w+)\s+=\s+_interop\w+\(\1\)/g;
    const selfReferences = Array.from(content.matchAll(selfReferencePattern));

    if (selfReferences.length > 0) {
      for (const match of selfReferences) {
        results.potentialIssues.push({
          file,
          issue: 'Self-referencing variable initialization (TDZ risk)',
          pattern: match[0],
        });
      }
    }

    // Pattern 2: Circular module initialization patterns
    // Look for: function init() { ... return module; } ... module = init();
    // BUT: Ignore minified single-letter variables (common in production builds)
    const circularInitPattern = /function\s+\w+\(\)\s*{[\s\S]{0,200}return\s+(\w{2,})[\s\S]{0,50}}\s*;\s*\1\s*=/g;
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

    // Pattern 3: Excessive imports from same module (>10 is suspicious)
    // This can indicate chunking issues where same module is imported multiple times
    const importPattern = /import\s+.*?\s+from\s+['"](.+?)['"]/g;
    const imports = Array.from(content.matchAll(importPattern));
    const importCounts = new Map<string, number>();

    for (const match of imports) {
      const moduleName = match[1];
      importCounts.set(moduleName, (importCounts.get(moduleName) || 0) + 1);
    }

    for (const [module, count] of importCounts.entries()) {
      if (count > 10) {
        results.potentialIssues.push({
          file,
          issue: 'Excessive imports from same module (possible chunk duplication)',
          pattern: `${count} imports from "${module}"`,
        });
      }
    }
  }

  return results;
}

/**
 * Main execution
 */
function main() {
  console.log('🔍 Analyzing production build chunks for circular dependencies...\n');

  const analysis = analyzeChunksForCircularDeps();

  // Print summary
  console.log('=== Chunk Analysis Summary ===');
  console.log(`Total chunks: ${analysis.totalChunks}`);
  console.log(`Chunks analyzed: ${analysis.chunksAnalyzed.length}\n`);

  // Print interop helper usage
  if (Object.keys(analysis.interopHelperUsage).length > 0) {
    console.log('Interop helper usage:');
    for (const [helper, count] of Object.entries(analysis.interopHelperUsage)) {
      console.log(`  ${helper}: ${count} occurrences`);
    }
    console.log();
  }

  // Print large chunks (>500KB)
  const largeChunks = Object.entries(analysis.chunkSizes)
    .filter(([_, size]) => size > 500 * 1024)
    .sort(([, a], [, b]) => b - a);

  if (largeChunks.length > 0) {
    console.log('Large chunks (>500KB):');
    for (const [file, size] of largeChunks) {
      console.log(`  ${file}: ${(size / 1024).toFixed(2)} KB`);
    }
    console.log();
  }

  // Print potential issues
  if (analysis.potentialIssues.length > 0) {
    console.error('⚠️  === Potential Issues Detected ===\n');
    for (const issue of analysis.potentialIssues) {
      console.error(`File: ${issue.file}`);
      console.error(`Issue: ${issue.issue}`);
      console.error(`Pattern: ${issue.pattern}\n`);
    }

    console.error(`\n❌ Found ${analysis.potentialIssues.length} potential circular dependency issue(s)`);
    console.error('   These patterns may cause TDZ errors at runtime.');
    console.error('   Review vite.config.ts rollupOptions.output.manualChunks configuration.');
    process.exit(1);
  }

  // Success
  console.log('✅ No circular dependency patterns detected');
  console.log('   Build chunks are safe for production deployment.\n');
  process.exit(0);
}

main();
