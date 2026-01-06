/**
 * Services Index
 *
 * Central export point for all service modules.
 *
 * @module services
 */

// API client and types
export * from './api';

// A/B Test Execution Service
export {
  abTestService,
  type ABTestService,
  type ABTestResult,
  type ModelConfig,
  type EventSummary,
  type TestPromptResponse,
} from './abTestService';

// Metrics Parser
export * from './metricsParser';

// TanStack Query Configuration
export {
  queryClient,
  createQueryClient,
  queryKeys,
  DEFAULT_STALE_TIME,
  REALTIME_STALE_TIME,
  STATIC_STALE_TIME,
} from './queryClient';
