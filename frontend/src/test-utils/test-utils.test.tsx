/**
 * Tests for the test utilities themselves.
 *
 * This file validates that the test utilities work correctly and can be
 * used as documentation for how to use them.
 */
import { describe, expect, it, vi } from 'vitest';

import {
  // Render utilities
  renderWithProviders,
  screen,
  // Factories
  createDetection,
  createDetections,
  createEvent,
  createEvents,
  createCamera,
  createCameras,
  createServiceStatus,
  createAllServiceStatuses,
  createGpuStats,
  createSystemHealth,
  createTimestamp,
  createFixedTimestamp,
  createWsEventMessage,
  createWsServiceStatusMessage,
  createWsGpuStatsMessage,
  // Accessibility
  checkAccessibility,
  getAccessibilityResults,
  formatViolations,
} from './index';

// Simple test component for render utilities
function TestComponent({ message = 'Hello' }: { message?: string }) {
  return (
    <div>
      <h1>{message}</h1>
      <button type="button">Click me</button>
    </div>
  );
}

describe('Test Utilities', () => {
  describe('renderWithProviders', () => {
    it('renders component with default providers', () => {
      renderWithProviders(<TestComponent />);
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    it('returns user event instance', () => {
      const { user } = renderWithProviders(<TestComponent />);
      expect(user).toBeDefined();
      expect(typeof user.click).toBe('function');
    });

    it('allows interaction with userEvent', async () => {
      const handleClick = vi.fn();
      const { user } = renderWithProviders(
        <button onClick={handleClick}>Click me</button>
      );

      await user.click(screen.getByRole('button'));
      expect(handleClick).toHaveBeenCalled();
    });

    it('wraps with MemoryRouter by default', () => {
      // This shouldn't throw - proves router context is available
      renderWithProviders(<TestComponent />);
      expect(screen.getByRole('heading')).toBeInTheDocument();
    });

    it('supports custom route', () => {
      renderWithProviders(<TestComponent />, { route: '/settings' });
      // Component renders, proving route was accepted
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    it('supports disabling router wrapper', () => {
      // Should not throw even without router
      renderWithProviders(<TestComponent />, { withRouter: false });
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    it('supports custom sidebar context', () => {
      const mockToggle = vi.fn();
      renderWithProviders(<TestComponent />, {
        sidebarContext: {
          isMobileMenuOpen: true,
          toggleMobileMenu: mockToggle,
        },
      });
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });
  });

  describe('Detection Factories', () => {
    it('createDetection returns detection with defaults', () => {
      const detection = createDetection();
      expect(detection.label).toBe('person');
      expect(detection.confidence).toBe(0.95);
      expect(detection.bbox).toBeDefined();
    });

    it('createDetection allows overrides', () => {
      const detection = createDetection({
        label: 'car',
        confidence: 0.8,
      });
      expect(detection.label).toBe('car');
      expect(detection.confidence).toBe(0.8);
    });

    it('createDetections returns array of detections', () => {
      const detections = createDetections(3);
      expect(detections).toHaveLength(3);
      expect(detections[0].label).toBe('person');
      expect(detections[1].label).toBe('car');
      expect(detections[2].label).toBe('dog');
    });

    it('createDetections has decreasing confidence', () => {
      const detections = createDetections(3);
      expect(detections[0].confidence).toBeGreaterThan(detections[1].confidence);
      expect(detections[1].confidence).toBeGreaterThan(detections[2].confidence);
    });
  });

  describe('Event Factories', () => {
    it('createEvent returns event with defaults', () => {
      const event = createEvent();
      expect(event.id).toBeDefined();
      expect(event.camera_name).toBe('Front Door');
      expect(event.risk_score).toBe(45);
      expect(event.detections).toHaveLength(1);
    });

    it('createEvent allows overrides', () => {
      const event = createEvent({
        camera_name: 'Back Door',
        risk_score: 85,
      });
      expect(event.camera_name).toBe('Back Door');
      expect(event.risk_score).toBe(85);
    });

    it('createEvents returns array with varied data', () => {
      const events = createEvents(4);
      expect(events).toHaveLength(4);
      // Check varied risk scores
      const riskScores = events.map((e) => e.risk_score);
      expect(new Set(riskScores).size).toBeGreaterThan(1);
    });
  });

  describe('Camera Factories', () => {
    it('createCamera returns camera with defaults', () => {
      const camera = createCamera();
      expect(camera.id).toBeDefined();
      expect(camera.name).toBe('Front Door Camera');
      expect(camera.status).toBe('online');
      expect(camera.enabled).toBe(true);
    });

    it('createCamera allows overrides', () => {
      const camera = createCamera({
        name: 'Kitchen',
        status: 'offline',
      });
      expect(camera.name).toBe('Kitchen');
      expect(camera.status).toBe('offline');
    });

    it('createCameras returns array of cameras', () => {
      const cameras = createCameras(3);
      expect(cameras).toHaveLength(3);
      // All should have unique IDs
      const ids = cameras.map((c) => c.id);
      expect(new Set(ids).size).toBe(3);
    });
  });

  describe('Service Status Factories', () => {
    it('createServiceStatus returns status with defaults', () => {
      const status = createServiceStatus('rtdetr');
      expect(status.service).toBe('rtdetr');
      expect(status.status).toBe('healthy');
      expect(status.timestamp).toBeDefined();
    });

    it('createServiceStatus allows custom status', () => {
      const status = createServiceStatus('nemotron', 'unhealthy', 'Connection failed');
      expect(status.service).toBe('nemotron');
      expect(status.status).toBe('unhealthy');
      expect(status.message).toBe('Connection failed');
    });

    it('createAllServiceStatuses returns all services', () => {
      const services = createAllServiceStatuses();
      expect(services.redis).toBeDefined();
      expect(services.rtdetr).toBeDefined();
      expect(services.nemotron).toBeDefined();
    });

    it('createAllServiceStatuses allows overrides', () => {
      const services = createAllServiceStatuses({ nemotron: 'unhealthy' });
      expect(services.nemotron?.status).toBe('unhealthy');
      expect(services.rtdetr?.status).toBe('healthy');
    });
  });

  describe('GPU Stats Factories', () => {
    it('createGpuStats returns stats with defaults', () => {
      const stats = createGpuStats();
      expect(stats.gpu_name).toBe('NVIDIA RTX A5500');
      expect(stats.gpu_utilization).toBe(45);
      expect(stats.memory_total_mb).toBe(24576);
    });

    it('createGpuStats allows overrides', () => {
      const stats = createGpuStats({ gpu_utilization: 95 });
      expect(stats.gpu_utilization).toBe(95);
    });
  });

  describe('System Health Factories', () => {
    it('createSystemHealth returns health with defaults', () => {
      const health = createSystemHealth();
      expect(health.status).toBe('healthy');
      expect(health.database.connected).toBe(true);
      expect(health.redis.connected).toBe(true);
    });

    it('createSystemHealth allows overrides', () => {
      const health = createSystemHealth({
        status: 'degraded',
        redis: { status: 'unhealthy', connected: false },
      });
      expect(health.status).toBe('degraded');
      expect(health.redis.connected).toBe(false);
    });
  });

  describe('Timestamp Utilities', () => {
    it('createTimestamp returns ISO timestamp', () => {
      const timestamp = createTimestamp();
      expect(new Date(timestamp).toISOString()).toBe(timestamp);
    });

    it('createTimestamp with minutes ago', () => {
      const now = Date.now();
      const fiveMinutesAgo = createTimestamp(5);
      const parsed = new Date(fiveMinutesAgo).getTime();
      // Should be approximately 5 minutes ago
      expect(now - parsed).toBeGreaterThan(4.5 * 60 * 1000);
      expect(now - parsed).toBeLessThan(5.5 * 60 * 1000);
    });

    it('createFixedTimestamp returns consistent timestamp', () => {
      const timestamp = createFixedTimestamp('2024-01-15T10:00:00Z');
      expect(timestamp).toBe('2024-01-15T10:00:00.000Z');
    });
  });

  describe('WebSocket Message Factories', () => {
    it('createWsEventMessage returns valid message', () => {
      const message = createWsEventMessage({ risk_score: 85 });
      expect(message.type).toBe('new_event');
      expect(message.data.risk_score).toBe(85);
      expect(message.timestamp).toBeDefined();
    });

    it('createWsServiceStatusMessage returns valid message', () => {
      const message = createWsServiceStatusMessage('rtdetr', 'healthy');
      expect(message.type).toBe('service_status');
      expect(message.data.service).toBe('rtdetr');
      expect(message.data.status).toBe('healthy');
    });

    it('createWsGpuStatsMessage returns valid message', () => {
      const message = createWsGpuStatsMessage({ gpu_utilization: 80 });
      expect(message.type).toBe('gpu_stats');
      expect(message.data.gpu_utilization).toBe(80);
    });
  });

  describe('Accessibility Utilities', () => {
    it('checkAccessibility passes for accessible component', async () => {
      const { container } = renderWithProviders(
        <div>
          <h1>Accessible Page</h1>
          <button type="button">Click me</button>
        </div>
      );

      // Should not throw
      await expect(checkAccessibility(container)).resolves.not.toThrow();
    });

    it('getAccessibilityResults returns results object', async () => {
      const { container } = renderWithProviders(<TestComponent />);
      const results = await getAccessibilityResults(container);

      expect(results).toBeDefined();
      expect(results.violations).toBeDefined();
      expect(Array.isArray(results.violations)).toBe(true);
    });

    it('formatViolations returns message for no violations', () => {
      const message = formatViolations([]);
      expect(message).toBe('No accessibility violations found.');
    });
  });
});
