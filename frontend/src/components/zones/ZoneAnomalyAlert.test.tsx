/**
 * Tests for ZoneAnomalyAlert component (NEM-3199)
 *
 * This module tests the zone anomaly alert card:
 * - Rendering with different severity levels
 * - Displaying anomaly information
 * - Acknowledge button functionality
 * - Click handling
 * - Accessibility
 */
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ZoneAnomalyAlert } from './ZoneAnomalyAlert';
import { AnomalySeverity, AnomalyType } from '../../types/zoneAnomaly';

import type { ZoneAnomaly } from '../../types/zoneAnomaly';

// Helper to wrap component with router
function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('ZoneAnomalyAlert', () => {
  // Helper to create mock anomaly
  const createMockAnomaly = (overrides: Partial<ZoneAnomaly> = {}): ZoneAnomaly => ({
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual activity at 03:00',
    description: 'Activity detected in Front Door zone at 03:00 when typical activity is 0.1.',
    expected_value: 0.1,
    actual_value: 1.0,
    deviation: 3.5,
    detection_id: 12345,
    thumbnail_url: '/thumbnails/test.jpg',
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T03:00:00Z',
    created_at: '2024-01-15T03:00:00Z',
    updated_at: '2024-01-15T03:00:00Z',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the anomaly title', () => {
      const anomaly = createMockAnomaly({ title: 'Test Anomaly Title' });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Test Anomaly Title')).toBeInTheDocument();
    });

    it('renders the anomaly description', () => {
      const anomaly = createMockAnomaly({
        description: 'This is the anomaly description.',
      });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('This is the anomaly description.')).toBeInTheDocument();
    });

    it('renders zone name when provided', () => {
      const anomaly = createMockAnomaly();
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} zoneName="Front Door" />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('renders anomaly type badge', () => {
      const anomaly = createMockAnomaly({ anomaly_type: AnomalyType.UNUSUAL_TIME });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Unusual Time')).toBeInTheDocument();
    });

    it('renders expected/actual/deviation statistics', () => {
      const anomaly = createMockAnomaly({
        expected_value: 0.1,
        actual_value: 1.0,
        deviation: 3.5,
      });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Expected:')).toBeInTheDocument();
      expect(screen.getByText('0.1')).toBeInTheDocument();
      expect(screen.getByText('Actual:')).toBeInTheDocument();
      expect(screen.getByText('1.0')).toBeInTheDocument();
      expect(screen.getByText('Deviation:')).toBeInTheDocument();
      expect(screen.getByText('3.5 std')).toBeInTheDocument();
    });

    it('handles null statistics gracefully', () => {
      const anomaly = createMockAnomaly({
        expected_value: null,
        actual_value: null,
        deviation: null,
      });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.queryByText('Expected:')).not.toBeInTheDocument();
      expect(screen.queryByText('Actual:')).not.toBeInTheDocument();
      expect(screen.queryByText('Deviation:')).not.toBeInTheDocument();
    });

    it('renders relative timestamp', () => {
      // Use a fixed timestamp relative to now
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
      const anomaly = createMockAnomaly({ timestamp: oneHourAgo.toISOString() });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      // Should show something like "1 hour ago" or "about 1 hour ago"
      expect(screen.getByText(/hour ago/i)).toBeInTheDocument();
    });
  });

  describe('severity styling', () => {
    it('applies INFO severity styling', () => {
      const anomaly = createMockAnomaly({ severity: AnomalySeverity.INFO });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('data-severity', 'info');
      expect(alert).toHaveClass('bg-blue-500/10');
    });

    it('applies WARNING severity styling', () => {
      const anomaly = createMockAnomaly({ severity: AnomalySeverity.WARNING });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('data-severity', 'warning');
      expect(alert).toHaveClass('bg-yellow-500/10');
    });

    it('applies CRITICAL severity styling', () => {
      const anomaly = createMockAnomaly({ severity: AnomalySeverity.CRITICAL });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('data-severity', 'critical');
      expect(alert).toHaveClass('bg-red-500/10');
    });
  });

  describe('acknowledged state', () => {
    it('shows acknowledge button when not acknowledged', () => {
      const anomaly = createMockAnomaly({ acknowledged: false });
      const onAcknowledge = vi.fn();
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={onAcknowledge} />);

      expect(screen.getByRole('button', { name: /acknowledge/i })).toBeInTheDocument();
    });

    it('shows acknowledged badge when acknowledged', () => {
      const anomaly = createMockAnomaly({
        acknowledged: true,
        acknowledged_at: '2024-01-15T04:00:00Z',
      });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Acknowledged')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /acknowledge/i })).not.toBeInTheDocument();
    });

    it('applies reduced opacity when acknowledged', () => {
      const anomaly = createMockAnomaly({ acknowledged: true });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('data-acknowledged', 'true');
      expect(alert).toHaveClass('opacity-60');
    });

    it('does not show acknowledge button without onAcknowledge callback', () => {
      const anomaly = createMockAnomaly({ acknowledged: false });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.queryByRole('button', { name: /acknowledge/i })).not.toBeInTheDocument();
    });
  });

  describe('acknowledge button', () => {
    it('calls onAcknowledge with anomaly id when clicked', async () => {
      const user = userEvent.setup();
      const onAcknowledge = vi.fn();
      const anomaly = createMockAnomaly({ id: 'test-anomaly-id' });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={onAcknowledge} />);

      const button = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(button);

      expect(onAcknowledge).toHaveBeenCalledTimes(1);
      expect(onAcknowledge).toHaveBeenCalledWith('test-anomaly-id');
    });

    it('stops event propagation when clicked', async () => {
      const user = userEvent.setup();
      const onAcknowledge = vi.fn();
      const onClick = vi.fn();
      const anomaly = createMockAnomaly();

      renderWithRouter(
        <ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={onAcknowledge} onClick={onClick} />
      );

      const button = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(button);

      expect(onAcknowledge).toHaveBeenCalled();
      expect(onClick).not.toHaveBeenCalled();
    });

    it('is disabled when isAcknowledging is true', () => {
      const anomaly = createMockAnomaly();
      renderWithRouter(
        <ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={vi.fn()} isAcknowledging />
      );

      const button = screen.getByRole('button', { name: /acknowledge/i });
      expect(button).toBeDisabled();
    });

    it('has cursor-not-allowed when isAcknowledging', () => {
      const anomaly = createMockAnomaly();
      renderWithRouter(
        <ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={vi.fn()} isAcknowledging />
      );

      const button = screen.getByRole('button', { name: /acknowledge/i });
      expect(button).toHaveClass('cursor-not-allowed');
    });
  });

  describe('click handling', () => {
    it('calls onClick with anomaly when card is clicked', async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={onClick} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      await user.click(alert);

      expect(onClick).toHaveBeenCalledTimes(1);
      expect(onClick).toHaveBeenCalledWith(anomaly);
    });

    it('has cursor-pointer when onClick is provided', () => {
      const anomaly = createMockAnomaly();
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={vi.fn()} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveClass('cursor-pointer');
    });

    it('does not have cursor-pointer without onClick', () => {
      const anomaly = createMockAnomaly();
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).not.toHaveClass('cursor-pointer');
    });

    it('is clickable via keyboard when onClick provided', () => {
      const onClick = vi.fn();
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={onClick} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      fireEvent.keyDown(alert, { key: 'Enter' });

      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('is clickable via Space key', () => {
      const onClick = vi.fn();
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={onClick} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      fireEvent.keyDown(alert, { key: ' ' });

      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('expanded mode', () => {
    it('shows full description when expanded', () => {
      const longDescription =
        'This is a very long description that would normally be truncated when not expanded. It contains many words and should display fully when the expanded prop is true.';
      const anomaly = createMockAnomaly({ description: longDescription });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} expanded />);

      const descriptionElement = screen.getByText(longDescription);
      expect(descriptionElement).not.toHaveClass('line-clamp-2');
    });

    it('truncates description when not expanded', () => {
      const longDescription =
        'This is a very long description that should be truncated when not expanded.';
      const anomaly = createMockAnomaly({ description: longDescription });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} expanded={false} />);

      const descriptionElement = screen.getByText(longDescription);
      expect(descriptionElement).toHaveClass('line-clamp-2');
    });

    it('shows thumbnail when expanded and thumbnail_url exists', () => {
      const anomaly = createMockAnomaly({ thumbnail_url: '/test-thumbnail.jpg' });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} expanded />);

      const thumbnail = screen.getByRole('img');
      expect(thumbnail).toHaveAttribute('src', '/test-thumbnail.jpg');
    });

    it('does not show thumbnail when not expanded', () => {
      const anomaly = createMockAnomaly({ thumbnail_url: '/test-thumbnail.jpg' });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} expanded={false} />);

      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('shows zone details link when expanded', () => {
      const anomaly = createMockAnomaly({ zone_id: 'zone-123' });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} expanded />);

      const link = screen.getByRole('link', { name: /view zone details/i });
      expect(link).toHaveAttribute('href', '/zones/zone-123');
    });
  });

  describe('zone link', () => {
    it('links to zone details page', () => {
      const anomaly = createMockAnomaly({ zone_id: 'test-zone-id' });

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} zoneName="Test Zone" />);

      const link = screen.getByRole('link', { name: 'Test Zone' });
      expect(link).toHaveAttribute('href', '/zones/test-zone-id');
    });

    it('zone link click does not trigger card onClick', async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      const anomaly = createMockAnomaly();

      renderWithRouter(
        <ZoneAnomalyAlert anomaly={anomaly} zoneName="Test Zone" onClick={onClick} />
      );

      const link = screen.getByRole('link', { name: 'Test Zone' });
      await user.click(link);

      expect(onClick).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has correct role when clickable', () => {
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={vi.fn()} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('role', 'button');
    });

    it('has tabIndex when clickable', () => {
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onClick={vi.fn()} />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveAttribute('tabIndex', '0');
    });

    it('acknowledge button has aria-label', () => {
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={vi.fn()} />);

      const button = screen.getByRole('button', { name: /acknowledge anomaly/i });
      expect(button).toBeInTheDocument();
    });

    it('acknowledge button has title', () => {
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} onAcknowledge={vi.fn()} />);

      const button = screen.getByRole('button', { name: /acknowledge/i });
      expect(button).toHaveAttribute('title', 'Acknowledge anomaly');
    });
  });

  describe('anomaly types', () => {
    it('displays UNUSUAL_TIME type correctly', () => {
      const anomaly = createMockAnomaly({ anomaly_type: AnomalyType.UNUSUAL_TIME });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Unusual Time')).toBeInTheDocument();
    });

    it('displays UNUSUAL_FREQUENCY type correctly', () => {
      const anomaly = createMockAnomaly({ anomaly_type: AnomalyType.UNUSUAL_FREQUENCY });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('High Frequency')).toBeInTheDocument();
    });

    it('displays UNUSUAL_DWELL type correctly', () => {
      const anomaly = createMockAnomaly({ anomaly_type: AnomalyType.UNUSUAL_DWELL });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Extended Presence')).toBeInTheDocument();
    });

    it('displays UNUSUAL_ENTITY type correctly', () => {
      const anomaly = createMockAnomaly({ anomaly_type: AnomalyType.UNUSUAL_ENTITY });
      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} />);

      expect(screen.getByText('Unusual Entity')).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const anomaly = createMockAnomaly();

      renderWithRouter(<ZoneAnomalyAlert anomaly={anomaly} className="custom-class" />);

      const alert = screen.getByTestId('zone-anomaly-alert');
      expect(alert).toHaveClass('custom-class');
    });
  });
});
