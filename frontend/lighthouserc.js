module.exports = {
  ci: {
    collect: {
      // Use static dist directory from Vite build
      // LHCI will automatically start a server
      staticDistDir: "./dist",
      // Number of runs per URL for more reliable scores
      numberOfRuns: 3,
      // Key pages to test (relative paths - LHCI appends to server URL)
      url: ["/", "/timeline", "/settings", "/system"],
      // Lighthouse settings
      settings: {
        // Use desktop preset for consistent CI testing
        preset: "desktop",
        // Skip network throttling for CI speed
        throttlingMethod: "provided",
      },
    },
    assert: {
      assertions: {
        // Category thresholds (scores are 0-1, so 70 = 0.7)
        "categories:performance": ["error", { minScore: 0.7 }],
        "categories:accessibility": ["error", { minScore: 0.8 }],
        "categories:best-practices": ["error", { minScore: 0.8 }],
        "categories:seo": ["error", { minScore: 0.7 }],
        // Core Web Vitals (warnings for now)
        "first-contentful-paint": ["warn", { maxNumericValue: 2000 }],
        "largest-contentful-paint": ["warn", { maxNumericValue: 4000 }],
        "cumulative-layout-shift": ["warn", { maxNumericValue: 0.1 }],
        "total-blocking-time": ["warn", { maxNumericValue: 300 }],
        // Additional performance metrics
        "speed-index": ["warn", { maxNumericValue: 4000 }],
        "interactive": ["warn", { maxNumericValue: 5000 }],
      },
    },
    upload: {
      // Use temporary public storage for CI reports
      target: "temporary-public-storage",
    },
  },
};
