/**
 * Tests for CameraUptimeCard component
 *
 * Tests cover:
 * - Rendering with camera uptime data
 * - Empty state when no cameras
 * - Loading state
 * - Error state
 * - Color coding based on uptime percentage
 * - Date range display in title
 * - Sorting by uptime percentage
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CameraUptimeCard from './CameraUptimeCard';
import * as useCameraUptimeQueryModule from '../../hooks/useCameraUptimeQuery';

// Mock the hook
vi.mock('../../hooks/useCameraUptimeQuery', () => ({
  useCameraUptimeQuery: vi.fn(),
}));

describe('CameraUptimeCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockCameras = [
    {
      camera_id: 'front-door',
      camera_name: 'Front Door',
      uptime_percentage: 99.2,
      detection_count: 156,
    },
    {
      camera_id: 'backyard',
      camera_name: 'Backyard',
      uptime_percentage: 87.5,
      detection_count: 89,
    },
    {
      camera_id: 'garage',
      camera_name: 'Garage',
      uptime_percentage: 62.1,
      detection_count: 34,
    },
    {
      camera_id: 'driveway',
      camera_name: 'Driveway',
      uptime_percentage: 45.0,
      detection_count: 12,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: mockCameras,
        data: {
          cameras: mockCameras,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('renders the card title with date range', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByText('Camera Uptime')).toBeInTheDocument();
    });

    it('renders all cameras', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
    });

    it('displays uptime percentages formatted to 1 decimal place', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByText('99.2%')).toBeInTheDocument();
      expect(screen.getByText('87.5%')).toBeInTheDocument();
      expect(screen.getByText('62.1%')).toBeInTheDocument();
      expect(screen.getByText('45.0%')).toBeInTheDocument();
    });

    it('displays cameras sorted by uptime percentage (highest first)', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      // Get all camera names in order
      const cameraNames = screen.getAllByTestId(/^camera-uptime-item-/);
      expect(cameraNames[0]).toHaveAttribute('data-testid', 'camera-uptime-item-front-door');
      expect(cameraNames[1]).toHaveAttribute('data-testid', 'camera-uptime-item-backyard');
      expect(cameraNames[2]).toHaveAttribute('data-testid', 'camera-uptime-item-garage');
      expect(cameraNames[3]).toHaveAttribute('data-testid', 'camera-uptime-item-driveway');
    });
  });

  describe('color coding', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: mockCameras,
        data: {
          cameras: mockCameras,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('assigns green color for uptime >= 95%', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      const frontDoorItem = screen.getByTestId('camera-uptime-item-front-door');
      expect(frontDoorItem).toHaveAttribute('data-uptime-status', 'healthy');
    });

    it('assigns yellow color for uptime 80-94%', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      const backyardItem = screen.getByTestId('camera-uptime-item-backyard');
      expect(backyardItem).toHaveAttribute('data-uptime-status', 'degraded');
    });

    it('assigns orange color for uptime 60-79%', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      const garageItem = screen.getByTestId('camera-uptime-item-garage');
      expect(garageItem).toHaveAttribute('data-uptime-status', 'warning');
    });

    it('assigns red color for uptime < 60%', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      const drivewayItem = screen.getByTestId('camera-uptime-item-driveway');
      expect(drivewayItem).toHaveAttribute('data-uptime-status', 'critical');
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: [],
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-uptime-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: [],
        data: undefined,
        isLoading: false,
        error: new Error('Failed to fetch'),
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-uptime-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load camera uptime/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: [],
        data: {
          cameras: [],
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no cameras', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-uptime-empty')).toBeInTheDocument();
      expect(screen.getByText(/No cameras available/)).toBeInTheDocument();
    });
  });

  describe('date range label', () => {
    beforeEach(() => {
      vi.mocked(useCameraUptimeQueryModule.useCameraUptimeQuery).mockReturnValue({
        cameras: mockCameras,
        data: {
          cameras: mockCameras,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('shows date range as subtitle', () => {
      render(<CameraUptimeCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });
  });
});
