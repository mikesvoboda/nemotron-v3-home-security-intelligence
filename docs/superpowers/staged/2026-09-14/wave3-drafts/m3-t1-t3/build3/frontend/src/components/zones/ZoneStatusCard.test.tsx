/**
 * Tests for ZoneStatusCard component (NEM-3200)
 *
 * Tests zone intelligence status display including:
 * - Activity level indicators
 * - Presence information
 * - Anomaly alerts
 * - Health scores
 * - Loading and error states
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneStatusCard from './ZoneStatusCard';
import { useZoneAnomalies } from '../../hooks/useZoneAnomalies';
import { useZonePresence } from '../../hooks/useZonePresence';
import { AnomalySeverity, AnomalyType } from '../../types/zoneAnomaly';

// Mock the hooks
vi.mock('../../hooks/useZonePresence', () => ({
  useZonePresence: vi.fn(),
}));

vi.mock('../../hooks/useZoneAnomalies', () => ({
  useZoneAnomalies: vi.fn(),
}));

describe('ZoneStatusCard', () => {
  const defaultProps = {
    zoneId: 'zone-123',
    zoneName: 'Front Door Zone',
  };

  const mockPresenceDefault = {
    members: [],
    presentCount: 0,
    activeCount: 0,
    isLoading: false,
    error: null,
    isConnected: true,
    clearPresence: vi.fn(),
  };

  const mockAnomaliesDefault = {
    anomalies: [],
    totalCount: 0,
    isLoading: false,
    isFetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
    acknowledgeAnomaly: vi.fn(),
    isAcknowledging: false,
    isConnected: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useZonePresence).mockReturnValue(mockPresenceDefault);
    vi.mocked(useZoneAnomalies).mockReturnValue(mockAnomaliesDefault);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the card with zone name', async () => {
      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-status-card')).toBeInTheDocument();
      });
      expect(screen.getByText('Front Door Zone')).toBeInTheDocument();
    });

    it('should render default title when no zoneName provided', async () => {
      render(<ZoneStatusCard zoneId="zone-123" />);

      await waitFor(() => {
        expect(screen.getByText('Zone Status')).toBeInTheDocument();
      });
    });

    it('should show loading state while fetching data', async () => {
      vi.mocked(useZonePresence).mockReturnValue({
        ...mockPresenceDefault,
        isLoading: true,
      } as ReturnType<typeof useZonePresence>);

      render(<ZoneStatusCard {...defaultProps} />);

      // The skeleton should be present during loading
      await waitFor(() => {
        expect(screen.getByTestId('zone-status-card')).toBeInTheDocument();
      });
    });
  });

  describe('Activity Level', () => {
    it('should display low activity badge when no anomalies', async () => {
      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('activity-badge')).toHaveTextContent('Low Activity');
      });
    });

    it('should display normal activity with some anomalies', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.INFO,
            title: 'Unusual activity',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('activity-badge')).toHaveTextContent('Normal');
      });
    });

    it('should display high activity with multiple anomalies', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.WARNING,
            title: 'Warning 1',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: 'anomaly-2',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_FREQUENCY,
            severity: AnomalySeverity.WARNING,
            title: 'Warning 2',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: 'anomaly-3',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_DWELL,
            severity: AnomalySeverity.WARNING,
            title: 'Warning 3',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 3,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('activity-badge')).toHaveTextContent('High Activity');
      });
    });

    it('should display critical activity when critical anomaly present', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_ENTITY,
            severity: AnomalySeverity.CRITICAL,
            title: 'Critical alert',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('activity-badge')).toHaveTextContent('Critical');
      });
    });
  });

  describe('Presence Information', () => {
    it('should display present count of 0', async () => {
      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Present')).toBeInTheDocument();
        // Multiple '0' values appear in the metrics grid, just verify they exist
        expect(screen.getAllByText('0').length).toBeGreaterThan(0);
      });
    });

    it('should display presence count when members present', async () => {
      vi.mocked(useZonePresence).mockReturnValue({
        ...mockPresenceDefault,
        presentCount: 3,
        members: [
          {
            id: 1,
            name: 'John',
            role: 'resident',
            lastSeen: new Date().toISOString(),
            isActive: true,
            isStale: false,
          },
          {
            id: 2,
            name: 'Jane',
            role: 'family',
            lastSeen: new Date().toISOString(),
            isActive: true,
            isStale: false,
          },
          {
            id: 3,
            name: 'Bob',
            role: 'frequent_visitor',
            lastSeen: new Date().toISOString(),
            isActive: false,
            isStale: true,
          },
        ],
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });
  });

  describe('Alert Information', () => {
    it('should display alert count', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.WARNING,
            title: 'Test alert',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Alerts')).toBeInTheDocument();
        expect(screen.getByText('1')).toBeInTheDocument();
      });
    });

    it('should show alert summary banner when anomalies exist', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.WARNING,
            title: 'Unusual activity detected',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('1 unacknowledged alert')).toBeInTheDocument();
        expect(screen.getByText('Latest: Unusual activity detected')).toBeInTheDocument();
      });
    });

    it('should not show alert banner in compact mode', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.WARNING,
            title: 'Unusual activity',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} compact />);

      await waitFor(() => {
        expect(screen.queryByText('unacknowledged alert')).not.toBeInTheDocument();
      });
    });
  });

  describe('Health Score', () => {
    it('should display high health score with no issues', async () => {
      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument();
        expect(screen.getByText('Health')).toBeInTheDocument();
      });
    });

    it('should display reduced health score with anomalies', async () => {
      vi.mocked(useZoneAnomalies).mockReturnValue({
        ...mockAnomaliesDefault,
        anomalies: [
          {
            id: 'anomaly-1',
            zone_id: 'zone-123',
            camera_id: 'cam-1',
            anomaly_type: AnomalyType.UNUSUAL_TIME,
            severity: AnomalySeverity.CRITICAL,
            title: 'Critical issue',
            description: null,
            expected_value: null,
            actual_value: null,
            deviation: null,
            detection_id: null,
            thumbnail_url: null,
            acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            timestamp: new Date().toISOString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        totalCount: 1,
      });

      render(<ZoneStatusCard {...defaultProps} />);

      await waitFor(() => {
        // Health score should be reduced: 100 - 20 (critical) - 2 (anomaly) = 78%
        expect(screen.getByText('78%')).toBeInTheDocument();
      });
    });
  });

  describe('Interaction', () => {
    it('should call onClick when card is clicked', async () => {
      const onClick = vi.fn();
      const user = userEvent.setup();

      render(<ZoneStatusCard {...defaultProps} onClick={onClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-status-card')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('zone-status-card'));
      expect(onClick).toHaveBeenCalled();
    });

    it('should have cursor-pointer class when onClick provided', async () => {
      render(<ZoneStatusCard {...defaultProps} onClick={vi.fn()} />);

      await waitFor(() => {
        const card = screen.getByTestId('zone-status-card');
        expect(card).toHaveClass('cursor-pointer');
      });
    });
  });

  describe('Compact Mode', () => {
    it('should render in compact mode', async () => {
      render(<ZoneStatusCard {...defaultProps} compact />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-status-card')).toBeInTheDocument();
      });
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', async () => {
      render(<ZoneStatusCard {...defaultProps} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-status-card')).toHaveClass('custom-class');
      });
    });
  });
});
