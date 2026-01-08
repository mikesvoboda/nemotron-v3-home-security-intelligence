/**
 * Example test file demonstrating centralized mock usage.
 *
 * This file shows how to use the centralized mocks from frontend/src/__mocks__/
 * for testing components that depend on useEventStream, useSystemStatus, and api.
 *
 * Use this as a reference when refactoring existing tests or writing new ones.
 */

import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { createQueryClient } from '../services/queryClient';

// ============================================================================
// Step 1: Mock modules at top level (before any imports that use them)
// ============================================================================

vi.mock('../hooks/useEventStream');
vi.mock('../hooks/useSystemStatus');
vi.mock('../services/api');

// ============================================================================
// Step 2: Import mock utilities (after vi.mock declarations)
// ============================================================================

import {
  // Event stream mocks
  setMockEvents,
  setEventStreamConnectionState,
  createMockSecurityEvent,
  createMockSecurityEvents,

  // System status mocks
  setMockSystemStatus,
  setSystemStatusConnectionState,
  createMockStatusWithHealth,
  createHighLoadStatus,

  // API mocks
  setMockCameras,
  setMockFetchCamerasError,
  createMockCamera,

  // Global reset
  resetAllMocks,
} from './index';

// ============================================================================
// Step 3: Create a test component that uses the mocked hooks
// ============================================================================

// Example component that would use these hooks (inline for demonstration)
function TestDashboard() {
  // In a real scenario, these would be imported from the actual hooks
  // For this example, we're just demonstrating the mock setup pattern
  return (
    <div>
      <h1>Test Dashboard</h1>
      <div data-testid="events-section">Events Section</div>
      <div data-testid="status-section">Status Section</div>
    </div>
  );
}

// Wrapper for rendering with required providers
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

// ============================================================================
// Step 4: Write tests using centralized mocks
// ============================================================================

describe('Centralized Mock Usage Examples', () => {
  // Always reset mocks in beforeEach for test isolation
  beforeEach(() => {
    resetAllMocks();
  });

  describe('useEventStream mock examples', () => {
    it('configures events with factory function', () => {
      // Use factory to create events with defaults
      const events = createMockSecurityEvents(3, { camera_name: 'Test Camera' });
      setMockEvents(events);

      // The hook will now return these events
      // This would be verified by rendering a component that uses useEventStream
      expect(events).toHaveLength(3);
      expect(events[0].camera_name).toBe('Test Camera');
    });

    it('configures single event with specific values', () => {
      setMockEvents([
        createMockSecurityEvent({
          id: 'critical-event',
          risk_score: 95,
          risk_level: 'critical',
          summary: 'Unknown person at entrance',
        }),
      ]);

      // Verify the mock was configured correctly
      // In real tests, this would be verified by component behavior
    });

    it('simulates disconnected state', () => {
      setEventStreamConnectionState(false);
      setMockEvents([]); // No events when disconnected

      // Component should show disconnected indicator
    });
  });

  describe('useSystemStatus mock examples', () => {
    it('configures healthy system status', () => {
      setMockSystemStatus({
        health: 'healthy',
        gpu_utilization: 45,
        gpu_temperature: 65,
        active_cameras: 3,
      });

      // Component should show healthy status indicator
    });

    it('uses factory for degraded status', () => {
      const degradedStatus = createMockStatusWithHealth('degraded', {
        gpu_utilization: 85,
      });
      setMockSystemStatus(degradedStatus);

      expect(degradedStatus.health).toBe('degraded');
      expect(degradedStatus.gpu_utilization).toBe(85);
    });

    it('uses factory for high load status', () => {
      setMockSystemStatus(createHighLoadStatus());

      // Component should show warning indicator
    });

    it('simulates system disconnection', () => {
      setSystemStatusConnectionState(false);
      setMockSystemStatus(null); // No status when disconnected
    });
  });

  describe('API mock examples', () => {
    it('configures cameras with factory function', () => {
      setMockCameras([
        createMockCamera({ id: 'cam-1', name: 'Front Door', status: 'online' }),
        createMockCamera({ id: 'cam-2', name: 'Back Yard', status: 'offline' }),
      ]);

      // API calls will return these cameras
    });

    it('simulates API error', () => {
      setMockFetchCamerasError(new Error('Network error'));

      // Component should show error state
    });

    it('verifies API was called', () => {
      setMockCameras([createMockCamera()]);

      // After rendering a component that calls fetchCameras...
      // You can verify the mock was called:
      // expect(fetchCameras).toHaveBeenCalled();
    });
  });

  describe('Combined mock usage', () => {
    it('sets up complete dashboard state', () => {
      // Configure all mocks for a complete scenario
      setMockCameras([
        createMockCamera({ id: 'cam-1', name: 'Front Door' }),
        createMockCamera({ id: 'cam-2', name: 'Back Yard' }),
      ]);

      setMockEvents([
        createMockSecurityEvent({
          camera_id: 'cam-1',
          camera_name: 'Front Door',
          risk_score: 75,
        }),
        createMockSecurityEvent({
          camera_id: 'cam-2',
          camera_name: 'Back Yard',
          risk_score: 30,
        }),
      ]);

      setMockSystemStatus({
        health: 'healthy',
        active_cameras: 2,
        gpu_utilization: 50,
      });

      // All hooks and API calls are now configured for a complete test
    });

    it('renders test component successfully', () => {
      // Configure minimal state
      setMockCameras([createMockCamera()]);
      setMockEvents([]);
      setMockSystemStatus({ health: 'healthy' });

      renderWithProviders(<TestDashboard />);

      // Verify component renders
      expect(screen.getByText('Test Dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('events-section')).toBeInTheDocument();
      expect(screen.getByTestId('status-section')).toBeInTheDocument();
    });
  });

  describe('Error handling patterns', () => {
    it('tests error recovery flow', () => {
      // First, simulate error
      setMockFetchCamerasError(new Error('Initial error'));

      // Then, in a subsequent test or after user action, clear error
      setMockFetchCamerasError(null);
      setMockCameras([createMockCamera()]);

      // Component should recover and show data
    });
  });
});
