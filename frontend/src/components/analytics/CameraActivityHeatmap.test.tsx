/**
 * Tests for CameraActivityHeatmap component
 *
 * Tests cover:
 * - Rendering camera activity grid with color intensity based on event count
 * - Thumbnail display for highest-risk detection per camera
 * - Risk color mapping (red=high activity, green=low activity)
 * - Loading state
 * - Error state
 * - Empty state
 * - Interaction (camera click to navigate)
 *
 * @see NEM-5388, NEM-5389, NEM-5390, NEM-5391 - Camera Activity Heatmap feature
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CameraActivityHeatmap from './CameraActivityHeatmap';
import { useCameraActivityQuery } from '../../hooks/useCameraActivityQuery';

// Mock the hook
vi.mock('../../hooks/useCameraActivityQuery', () => ({
  useCameraActivityQuery: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

describe('CameraActivityHeatmap', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockCameras = [
    {
      camera_id: 'front-door',
      camera_name: 'Front Door',
      event_count: 87,
      max_risk_score: 92,
      risk_level: 'critical' as const,
      thumbnail_path: '/data/thumbnails/front_door_high.jpg',
    },
    {
      camera_id: 'backyard',
      camera_name: 'Backyard',
      event_count: 45,
      max_risk_score: 65,
      risk_level: 'high' as const,
      thumbnail_path: '/data/thumbnails/backyard_high.jpg',
    },
    {
      camera_id: 'garage',
      camera_name: 'Garage',
      event_count: 12,
      max_risk_score: 35,
      risk_level: 'medium' as const,
      thumbnail_path: '/data/thumbnails/garage_med.jpg',
    },
    {
      camera_id: 'driveway',
      camera_name: 'Driveway',
      event_count: 3,
      max_risk_score: 15,
      risk_level: 'low' as const,
      thumbnail_path: null,
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
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('renders the card title', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText('Camera Activity')).toBeInTheDocument();
    });

    it('renders all cameras', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
    });

    it('displays event counts for each camera', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText('87 events')).toBeInTheDocument();
      expect(screen.getByText('45 events')).toBeInTheDocument();
      expect(screen.getByText('12 events')).toBeInTheDocument();
      expect(screen.getByText('3 events')).toBeInTheDocument();
    });

    it('displays cameras sorted by event count (highest first)', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const cameraItems = screen.getAllByTestId(/^camera-activity-item-/);
      expect(cameraItems[0]).toHaveAttribute('data-testid', 'camera-activity-item-front-door');
      expect(cameraItems[1]).toHaveAttribute('data-testid', 'camera-activity-item-backyard');
      expect(cameraItems[2]).toHaveAttribute('data-testid', 'camera-activity-item-garage');
      expect(cameraItems[3]).toHaveAttribute('data-testid', 'camera-activity-item-driveway');
    });

    it('shows thumbnails when available', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      // Check that thumbnails are rendered for cameras with thumbnail_path
      const frontDoorThumbnail = screen.getByTestId('camera-thumbnail-front-door');
      expect(frontDoorThumbnail).toBeInTheDocument();
      expect(frontDoorThumbnail).toHaveAttribute('src', expect.stringContaining('front_door_high'));

      const backyardThumbnail = screen.getByTestId('camera-thumbnail-backyard');
      expect(backyardThumbnail).toBeInTheDocument();
    });

    it('shows placeholder when thumbnail is not available', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      // Driveway has no thumbnail
      const drivewayPlaceholder = screen.getByTestId('camera-placeholder-driveway');
      expect(drivewayPlaceholder).toBeInTheDocument();
    });
  });

  describe('color coding by activity level', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('assigns critical color for highest activity (critical risk level)', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const frontDoorItem = screen.getByTestId('camera-activity-item-front-door');
      expect(frontDoorItem).toHaveAttribute('data-risk-level', 'critical');
    });

    it('assigns high color for elevated activity', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const backyardItem = screen.getByTestId('camera-activity-item-backyard');
      expect(backyardItem).toHaveAttribute('data-risk-level', 'high');
    });

    it('assigns medium color for moderate activity', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const garageItem = screen.getByTestId('camera-activity-item-garage');
      expect(garageItem).toHaveAttribute('data-risk-level', 'medium');
    });

    it('assigns low color for minimal activity', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const drivewayItem = screen.getByTestId('camera-activity-item-driveway');
      expect(drivewayItem).toHaveAttribute('data-risk-level', 'low');
    });
  });

  describe('risk score display', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('displays max risk score for each camera', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText('Risk: 92')).toBeInTheDocument();
      expect(screen.getByText('Risk: 65')).toBeInTheDocument();
      expect(screen.getByText('Risk: 35')).toBeInTheDocument();
      expect(screen.getByText('Risk: 15')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        cameras: [],
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-activity-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        cameras: [],
        data: undefined,
        isLoading: false,
        error: new Error('Failed to fetch'),
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-activity-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load camera activity/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByTestId('camera-activity-empty')).toBeInTheDocument();
      expect(screen.getByText(/No camera activity/)).toBeInTheDocument();
    });
  });

  describe('date range label', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });
  });

  describe('camera click interaction', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('navigates to timeline when camera is clicked', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const frontDoorItem = screen.getByTestId('camera-activity-item-front-door');
      fireEvent.click(frontDoorItem);

      expect(mockNavigate).toHaveBeenCalledWith('/timeline?camera=front-door');
    });

    it('calls onCameraClick callback when provided', () => {
      const onCameraClick = vi.fn();
      render(<CameraActivityHeatmap dateRange={mockDateRange} onCameraClick={onCameraClick} />);

      const backyardItem = screen.getByTestId('camera-activity-item-backyard');
      fireEvent.click(backyardItem);

      expect(onCameraClick).toHaveBeenCalledWith('backyard');
    });
  });

  describe('legend', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('displays risk level legend', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    beforeEach(() => {
      (useCameraActivityQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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

    it('camera items have accessible labels', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const frontDoorItem = screen.getByTestId('camera-activity-item-front-door');
      expect(frontDoorItem).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Front Door: 87 events, risk score 92')
      );
    });

    it('camera items are keyboard focusable', () => {
      render(<CameraActivityHeatmap dateRange={mockDateRange} />);

      const cameraItems = screen.getAllByTestId(/^camera-activity-item-/);
      cameraItems.forEach((item) => {
        expect(item).toHaveAttribute('tabIndex', '0');
      });
    });
  });
});
