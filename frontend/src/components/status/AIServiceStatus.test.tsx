/**
 * Tests for AIServiceStatus component.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { AIServiceStatus } from './AIServiceStatus';

import type { DegradationLevel, AIServiceState } from '../../hooks/useAIServiceStatus';

// Mock the useAIServiceStatus hook
const mockUseAIServiceStatus = vi.fn();

vi.mock('../../hooks/useAIServiceStatus', async () => {
  const actual = await vi.importActual('../../hooks/useAIServiceStatus');
  return {
    ...actual,
    useAIServiceStatus: () => mockUseAIServiceStatus(),
  };
});

const createMockServiceState = (
  service: string,
  status: 'healthy' | 'degraded' | 'unavailable' = 'healthy',
  circuitState: 'closed' | 'half_open' | 'open' = 'closed',
  failureCount: number = 0
): AIServiceState => ({
  service: service as 'rtdetr' | 'nemotron' | 'florence' | 'clip',
  status,
  circuit_state: circuitState,
  last_success: status === 'healthy' ? '2024-01-15T12:00:00Z' : null,
  failure_count: failureCount,
  error_message: status === 'unavailable' ? 'Connection refused' : null,
  last_check: '2024-01-15T12:00:00Z',
});

const createDefaultMockReturn = (overrides: Partial<ReturnType<typeof mockUseAIServiceStatus>> = {}) => ({
  degradationMode: 'normal' as DegradationLevel,
  services: {
    rtdetr: createMockServiceState('rtdetr'),
    nemotron: createMockServiceState('nemotron'),
    florence: createMockServiceState('florence'),
    clip: createMockServiceState('clip'),
  },
  availableFeatures: ['object_detection', 'risk_analysis', 'image_captioning', 'entity_tracking'],
  hasUnavailableService: false,
  isOffline: false,
  isDegraded: false,
  getServiceState: vi.fn(),
  isFeatureAvailable: vi.fn(),
  lastUpdate: '2024-01-15T12:00:00Z',
  ...overrides,
});

describe('AIServiceStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAIServiceStatus.mockReturnValue(createDefaultMockReturn());
  });

  describe('Normal mode', () => {
    it('renders normal status header', () => {
      render(<AIServiceStatus />);

      expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
      expect(screen.getByText(/All AI services are healthy/)).toBeInTheDocument();
    });

    it('renders with green styling in normal mode', () => {
      const { container } = render(<AIServiceStatus />);

      const wrapper = container.querySelector('.bg-green-50');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Degraded mode', () => {
    it('renders degraded status header', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          degradationMode: 'degraded',
          isDegraded: true,
          services: {
            rtdetr: createMockServiceState('rtdetr'),
            nemotron: createMockServiceState('nemotron'),
            florence: createMockServiceState('florence', 'unavailable', 'open', 5),
            clip: createMockServiceState('clip'),
          },
          hasUnavailableService: true,
        })
      );

      render(<AIServiceStatus />);

      expect(screen.getByText('Degraded Mode')).toBeInTheDocument();
      expect(screen.getByText(/non-critical AI services/)).toBeInTheDocument();
    });

    it('renders with yellow styling in degraded mode', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({ degradationMode: 'degraded', isDegraded: true })
      );

      const { container } = render(<AIServiceStatus />);

      const wrapper = container.querySelector('.bg-yellow-50');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Minimal mode', () => {
    it('renders minimal status header', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          degradationMode: 'minimal',
          isDegraded: true,
          services: {
            rtdetr: createMockServiceState('rtdetr', 'unavailable', 'open', 3),
            nemotron: createMockServiceState('nemotron'),
            florence: createMockServiceState('florence'),
            clip: createMockServiceState('clip'),
          },
          hasUnavailableService: true,
        })
      );

      render(<AIServiceStatus />);

      expect(screen.getByText('Minimal Mode')).toBeInTheDocument();
      expect(screen.getByText(/Critical AI services/)).toBeInTheDocument();
    });

    it('renders with orange styling in minimal mode', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({ degradationMode: 'minimal', isDegraded: true })
      );

      const { container } = render(<AIServiceStatus />);

      const wrapper = container.querySelector('.bg-orange-50');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Offline mode', () => {
    it('renders offline status header', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          degradationMode: 'offline',
          isOffline: true,
          isDegraded: true,
          services: {
            rtdetr: createMockServiceState('rtdetr', 'unavailable', 'open', 5),
            nemotron: createMockServiceState('nemotron', 'unavailable', 'open', 5),
            florence: createMockServiceState('florence', 'unavailable', 'open', 5),
            clip: createMockServiceState('clip', 'unavailable', 'open', 5),
          },
          hasUnavailableService: true,
          availableFeatures: ['event_history', 'camera_feeds'],
        })
      );

      render(<AIServiceStatus />);

      expect(screen.getByText('AI Services Offline')).toBeInTheDocument();
      expect(screen.getByText(/Historical data viewable/)).toBeInTheDocument();
    });

    it('renders with red styling in offline mode', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({ degradationMode: 'offline', isOffline: true, isDegraded: true })
      );

      const { container } = render(<AIServiceStatus />);

      const wrapper = container.querySelector('.bg-red-50');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Expandable details', () => {
    it('expands to show service details when clicked', () => {
      render(<AIServiceStatus showDetails={true} defaultExpanded={false} />);

      // Initially collapsed
      expect(screen.queryByText('Service Status')).not.toBeInTheDocument();

      // Click to expand
      const header = screen.getByRole('button');
      fireEvent.click(header);

      // Now expanded
      expect(screen.getByText('Service Status')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
      expect(screen.getByText('Florence-2')).toBeInTheDocument();
      expect(screen.getByText('CLIP')).toBeInTheDocument();
    });

    it('renders expanded by default when defaultExpanded is true', () => {
      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      expect(screen.getByText('Service Status')).toBeInTheDocument();
    });

    it('does not render expand button when showDetails is false', () => {
      render(<AIServiceStatus showDetails={false} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('Service status rows', () => {
    it('shows circuit breaker state badges', () => {
      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      const closedBadges = screen.getAllByText('Closed');
      expect(closedBadges.length).toBeGreaterThan(0);
    });

    it('shows failure count for unhealthy services', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          degradationMode: 'degraded',
          services: {
            rtdetr: createMockServiceState('rtdetr'),
            nemotron: createMockServiceState('nemotron'),
            florence: createMockServiceState('florence', 'unavailable', 'open', 5),
            clip: createMockServiceState('clip'),
          },
        })
      );

      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      expect(screen.getByText('5 failures')).toBeInTheDocument();
    });

    it('shows error message for unavailable services', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          degradationMode: 'degraded',
          services: {
            rtdetr: createMockServiceState('rtdetr'),
            nemotron: createMockServiceState('nemotron'),
            florence: createMockServiceState('florence', 'unavailable', 'open', 5),
            clip: createMockServiceState('clip'),
          },
        })
      );

      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      expect(screen.getByText('Connection refused')).toBeInTheDocument();
    });
  });

  describe('Available features list', () => {
    it('renders available features when expanded', () => {
      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      expect(screen.getByText('Available Features')).toBeInTheDocument();
      expect(screen.getByText('object detection')).toBeInTheDocument();
      expect(screen.getByText('risk analysis')).toBeInTheDocument();
    });
  });

  describe('Compact mode', () => {
    it('renders as compact badge when compact is true', () => {
      render(<AIServiceStatus compact={true} />);

      // Should not show full details
      expect(screen.queryByText('All AI services are healthy')).not.toBeInTheDocument();

      // Should show compact badge
      expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
    });

    it('shows degradation status in compact badge', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({ degradationMode: 'degraded' })
      );

      render(<AIServiceStatus compact={true} />);

      expect(screen.getByText('Degraded Mode')).toBeInTheDocument();
    });
  });

  describe('Last update timestamp', () => {
    it('shows last update time', () => {
      render(<AIServiceStatus />);

      // Should show some form of timestamp (the exact format depends on formatTimestamp)
      // The timestamp from mock is '2024-01-15T12:00:00Z' which will show as full date format
      // since it's over 24 hours old from "now"
      const timestampElement = screen.getByText(/ago|Never|Unknown|2024/);
      expect(timestampElement).toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('shows loading text for services with null state', () => {
      mockUseAIServiceStatus.mockReturnValue(
        createDefaultMockReturn({
          services: {
            rtdetr: null,
            nemotron: null,
            florence: null,
            clip: null,
          },
        })
      );

      render(<AIServiceStatus showDetails={true} defaultExpanded={true} />);

      const loadingTexts = screen.getAllByText('Loading...');
      expect(loadingTexts.length).toBe(4);
    });
  });
});
