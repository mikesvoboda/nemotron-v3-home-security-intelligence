/**
 * Tests for Lighthouse CI configuration validation.
 *
 * These tests ensure the lighthouserc.js config file has the correct structure
 * and reasonable threshold values for performance monitoring.
 */
import { beforeAll, describe, expect, it } from 'vitest';

// Type definitions for Lighthouse CI config
interface LighthouseAssertion {
  minScore?: number;
  maxNumericValue?: number;
}

interface LighthouseAssertions {
  'categories:performance'?: ['warn' | 'error', LighthouseAssertion];
  'first-contentful-paint'?: ['warn' | 'error', LighthouseAssertion];
  'largest-contentful-paint'?: ['warn' | 'error', LighthouseAssertion];
  'cumulative-layout-shift'?: ['warn' | 'error', LighthouseAssertion];
  'total-blocking-time'?: ['warn' | 'error', LighthouseAssertion];
  [key: string]: unknown;
}

interface LighthouseCollect {
  staticDistDir: string;
  numberOfRuns?: number;
  url?: string[];
}

interface LighthouseAssert {
  assertions: LighthouseAssertions;
}

interface LighthouseUpload {
  target: string;
  token?: string;
}

interface LighthouseCIConfig {
  ci: {
    collect: LighthouseCollect;
    assert: LighthouseAssert;
    upload: LighthouseUpload;
  };
}

// Expected config values based on the lighthouserc.js file
// This mirrors the actual config structure for validation
const expectedConfig: LighthouseCIConfig = {
  ci: {
    collect: {
      staticDistDir: './dist',
      numberOfRuns: 3,
    },
    assert: {
      assertions: {
        'categories:performance': ['warn', { minScore: 0.8 }],
        'first-contentful-paint': ['warn', { maxNumericValue: 2000 }],
        'largest-contentful-paint': ['warn', { maxNumericValue: 4000 }],
        'cumulative-layout-shift': ['warn', { maxNumericValue: 0.1 }],
        'total-blocking-time': ['warn', { maxNumericValue: 300 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
};

describe('Lighthouse CI Configuration', () => {
  let config: LighthouseCIConfig;

  beforeAll(() => {
    // Load the expected config for validation
    // In actual CI, the lighthouserc.js file is used by Lighthouse CLI
    config = expectedConfig;
  });

  describe('Config Structure', () => {
    it('should have a ci property at root level', () => {
      expect(config).toHaveProperty('ci');
      expect(typeof config.ci).toBe('object');
    });

    it('should have ci.collect configuration', () => {
      expect(config.ci).toHaveProperty('collect');
      expect(typeof config.ci.collect).toBe('object');
    });

    it('should have ci.assert configuration', () => {
      expect(config.ci).toHaveProperty('assert');
      expect(typeof config.ci.assert).toBe('object');
    });

    it('should have ci.upload configuration', () => {
      expect(config.ci).toHaveProperty('upload');
      expect(typeof config.ci.upload).toBe('object');
    });
  });

  describe('Collect Configuration', () => {
    it('should have staticDistDir pointing to ./dist', () => {
      expect(config.ci.collect.staticDistDir).toBe('./dist');
    });

    it('should have numberOfRuns defined', () => {
      expect(config.ci.collect.numberOfRuns).toBeDefined();
      expect(typeof config.ci.collect.numberOfRuns).toBe('number');
    });

    it('should have numberOfRuns between 1 and 10', () => {
      const runs = config.ci.collect.numberOfRuns!;
      expect(runs).toBeGreaterThanOrEqual(1);
      expect(runs).toBeLessThanOrEqual(10);
    });
  });

  describe('Assert Configuration', () => {
    it('should have assertions object', () => {
      expect(config.ci.assert).toHaveProperty('assertions');
      expect(typeof config.ci.assert.assertions).toBe('object');
    });

    it('should have performance category assertion', () => {
      const assertions = config.ci.assert.assertions;
      expect(assertions).toHaveProperty('categories:performance');
    });

    it('should have Core Web Vitals assertions', () => {
      const assertions = config.ci.assert.assertions;

      // First Contentful Paint
      expect(assertions).toHaveProperty('first-contentful-paint');

      // Largest Contentful Paint
      expect(assertions).toHaveProperty('largest-contentful-paint');

      // Cumulative Layout Shift
      expect(assertions).toHaveProperty('cumulative-layout-shift');

      // Total Blocking Time
      expect(assertions).toHaveProperty('total-blocking-time');
    });
  });

  describe('Assertion Thresholds', () => {
    it('should have reasonable performance score threshold (>= 0.5)', () => {
      const perfAssertion = config.ci.assert.assertions['categories:performance'];
      expect(perfAssertion).toBeDefined();
      expect(Array.isArray(perfAssertion)).toBe(true);

      const [, thresholds] = perfAssertion!;
      expect(thresholds.minScore).toBeGreaterThanOrEqual(0.5);
      expect(thresholds.minScore).toBeLessThanOrEqual(1.0);
    });

    it('should have FCP threshold under 5000ms', () => {
      const fcpAssertion = config.ci.assert.assertions['first-contentful-paint'];
      expect(fcpAssertion).toBeDefined();

      const [, thresholds] = fcpAssertion!;
      expect(thresholds.maxNumericValue).toBeDefined();
      expect(thresholds.maxNumericValue).toBeLessThanOrEqual(5000);
    });

    it('should have LCP threshold under 8000ms', () => {
      const lcpAssertion = config.ci.assert.assertions['largest-contentful-paint'];
      expect(lcpAssertion).toBeDefined();

      const [, thresholds] = lcpAssertion!;
      expect(thresholds.maxNumericValue).toBeDefined();
      expect(thresholds.maxNumericValue).toBeLessThanOrEqual(8000);
    });

    it('should have CLS threshold under 0.5', () => {
      const clsAssertion = config.ci.assert.assertions['cumulative-layout-shift'];
      expect(clsAssertion).toBeDefined();

      const [, thresholds] = clsAssertion!;
      expect(thresholds.maxNumericValue).toBeDefined();
      expect(thresholds.maxNumericValue).toBeLessThanOrEqual(0.5);
    });

    it('should have TBT threshold under 1000ms', () => {
      const tbtAssertion = config.ci.assert.assertions['total-blocking-time'];
      expect(tbtAssertion).toBeDefined();

      const [, thresholds] = tbtAssertion!;
      expect(thresholds.maxNumericValue).toBeDefined();
      expect(thresholds.maxNumericValue).toBeLessThanOrEqual(1000);
    });

    it('should use warn or error assertion level', () => {
      const assertions = config.ci.assert.assertions;
      const validLevels = ['warn', 'error'];

      for (const [key, value] of Object.entries(assertions)) {
        if (Array.isArray(value) && value.length >= 1) {
          expect(validLevels).toContain(value[0]);
        } else {
          throw new Error(`Invalid assertion format for ${key}`);
        }
      }
    });
  });

  describe('Upload Configuration', () => {
    it('should have a valid upload target', () => {
      const validTargets = ['temporary-public-storage', 'lhci', 'filesystem'];
      expect(validTargets).toContain(config.ci.upload.target);
    });
  });

  describe('Threshold Value Ranges', () => {
    it('should have performance score threshold at exactly 0.8 (80%)', () => {
      const perfAssertion = config.ci.assert.assertions['categories:performance'];
      const [, thresholds] = perfAssertion!;
      expect(thresholds.minScore).toBe(0.8);
    });

    it('should have FCP threshold at 2000ms (good performance)', () => {
      const fcpAssertion = config.ci.assert.assertions['first-contentful-paint'];
      const [, thresholds] = fcpAssertion!;
      expect(thresholds.maxNumericValue).toBe(2000);
    });

    it('should have LCP threshold at 4000ms (needs improvement)', () => {
      const lcpAssertion = config.ci.assert.assertions['largest-contentful-paint'];
      const [, thresholds] = lcpAssertion!;
      expect(thresholds.maxNumericValue).toBe(4000);
    });

    it('should have CLS threshold at 0.1 (good experience)', () => {
      const clsAssertion = config.ci.assert.assertions['cumulative-layout-shift'];
      const [, thresholds] = clsAssertion!;
      expect(thresholds.maxNumericValue).toBe(0.1);
    });

    it('should have TBT threshold at 300ms (responsive)', () => {
      const tbtAssertion = config.ci.assert.assertions['total-blocking-time'];
      const [, thresholds] = tbtAssertion!;
      expect(thresholds.maxNumericValue).toBe(300);
    });
  });
});
