/**
 * Test utilities for the Home Security Intelligence frontend.
 *
 * This module provides a centralized export of all test utilities, making it
 * easy to import everything needed for testing from a single location.
 *
 * @example
 * import {
 *   renderWithProviders,
 *   screen,
 *   createEvent,
 *   createDetection,
 * } from '../test-utils';
 *
 * describe('MyComponent', () => {
 *   it('renders correctly', async () => {
 *     const event = createEvent({ risk_score: 85 });
 *     const { user } = renderWithProviders(<MyComponent event={event} />);
 *
 *     expect(screen.getByRole('article')).toBeInTheDocument();
 *   });
 * });
 */

// Render utilities
export {
  renderWithProviders,
  screen,
  within,
  waitFor,
  act,
  userEvent,
} from './renderWithProviders';

export type {
  RenderWithProvidersOptions,
  RenderWithProvidersResult,
} from './renderWithProviders';

// Test data factories
export {
  // Detection factories
  createDetection,
  createDetections,
  // Event factories
  createEvent,
  createEvents,
  // Camera factories
  createCamera,
  createCameras,
  // Service status factories
  createServiceStatus,
  createAllServiceStatuses,
  // GPU stats factories
  createGpuStats,
  // System health factories
  createSystemHealth,
  // Timestamp utilities
  createTimestamp,
  createFixedTimestamp,
  // WebSocket message factories
  createWsEventMessage,
  createWsServiceStatusMessage,
  createWsGpuStatsMessage,
  // API Response factories
  createCameraResponse,
  createCamerasResponse,
  createHealthResponse,
  createEventListResponse,
  createErrorResponse,
  createGPUStatsResponse,
  createEventResponse,
} from './factories';

export type {
  BoundingBox,
  Detection,
  Event,
  Camera,
  ServiceName,
  ServiceStatusType,
  ServiceStatus,
  GpuStats,
  HealthStatus,
  SystemHealth,
  // API Response types
  HealthServiceStatus,
  HealthResponse,
  EventListResponse,
  CameraListResponse,
  GPUStatsResponse,
  ErrorResponse,
} from './factories';
