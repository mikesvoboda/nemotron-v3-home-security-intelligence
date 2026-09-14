/**
 * Tests for LineZoneCrossingCard component (NEM-4714)
 *
 * Tests line zone crossing display including:
 * - Rendering zone information
 * - Displaying counts (in, out, net)
 * - Reset button functionality
 * - Confirmation flow
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LineZoneCrossingCard from './LineZoneCrossingCard';

import type { LineZoneWithCounts } from '../../types/zoneAnalytics';

describe('LineZoneCrossingCard', () => {
  // Helper to create mock zone data
  const createMockZone = (overrides: Partial<LineZoneWithCounts> = {}): LineZoneWithCounts => ({
    id: 1,
    name: 'Front Door Line',
    camera_id: 'cam-123',
    in_count: 25,
    out_count: 20,
    enabled: true,
    ...overrides,
  });

  const defaultProps = {
    zone: createMockZone(),
    onReset: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the card with zone name', () => {
      render(<LineZoneCrossingCard {...defaultProps} />);

      expect(screen.getByTestId('line-zone-card-1')).toBeInTheDocument();
      expect(screen.getByText('Front Door Line')).toBeInTheDocument();
    });

    it('should display Active badge when zone is enabled', () => {
      render(<LineZoneCrossingCard {...defaultProps} />);

      expect(screen.getByTestId('zone-status-badge')).toHaveTextContent('Active');
    });

    it('should display Inactive badge when zone is disabled', () => {
      const zone = createMockZone({ enabled: false });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('zone-status-badge')).toHaveTextContent('Inactive');
    });

    it('should apply custom className', () => {
      render(<LineZoneCrossingCard {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('line-zone-card-1')).toHaveClass('custom-class');
    });
  });

  describe('Counts Display', () => {
    it('should display in count', () => {
      render(<LineZoneCrossingCard {...defaultProps} />);

      expect(screen.getByTestId('in-count')).toHaveTextContent('25');
      expect(screen.getByText('In')).toBeInTheDocument();
    });

    it('should display out count', () => {
      render(<LineZoneCrossingCard {...defaultProps} />);

      expect(screen.getByTestId('out-count')).toHaveTextContent('20');
      expect(screen.getByText('Out')).toBeInTheDocument();
    });

    it('should display positive net flow with plus sign', () => {
      const zone = createMockZone({ in_count: 30, out_count: 20 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveTextContent('+10');
    });

    it('should display negative net flow without plus sign', () => {
      const zone = createMockZone({ in_count: 10, out_count: 25 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveTextContent('-15');
    });

    it('should display zero net flow', () => {
      const zone = createMockZone({ in_count: 20, out_count: 20 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveTextContent('0');
    });

    it('should display zero counts', () => {
      const zone = createMockZone({ in_count: 0, out_count: 0 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('in-count')).toHaveTextContent('0');
      expect(screen.getByTestId('out-count')).toHaveTextContent('0');
      expect(screen.getByTestId('net-flow')).toHaveTextContent('0');
    });
  });

  describe('Reset Button', () => {
    it('should render reset button', () => {
      render(<LineZoneCrossingCard {...defaultProps} />);

      expect(screen.getByTestId('reset-button')).toBeInTheDocument();
      expect(screen.getByTestId('reset-button')).toHaveTextContent('Reset Counts');
    });

    it('should show confirmation on first click', async () => {
      const user = userEvent.setup();
      render(<LineZoneCrossingCard {...defaultProps} />);

      await user.click(screen.getByTestId('reset-button'));

      expect(screen.getByTestId('reset-button')).toHaveTextContent('Confirm Reset');
      expect(screen.getByTestId('cancel-reset-button')).toBeInTheDocument();
    });

    it('should call onReset on confirmation click', async () => {
      const onReset = vi.fn();
      const user = userEvent.setup();
      render(<LineZoneCrossingCard {...defaultProps} onReset={onReset} />);

      // First click shows confirmation
      await user.click(screen.getByTestId('reset-button'));
      // Second click confirms
      await user.click(screen.getByTestId('reset-button'));

      expect(onReset).toHaveBeenCalledWith(1);
    });

    it('should cancel confirmation when cancel button clicked', async () => {
      const onReset = vi.fn();
      const user = userEvent.setup();
      render(<LineZoneCrossingCard {...defaultProps} onReset={onReset} />);

      // Show confirmation
      await user.click(screen.getByTestId('reset-button'));
      expect(screen.getByTestId('reset-button')).toHaveTextContent('Confirm Reset');

      // Cancel
      await user.click(screen.getByTestId('cancel-reset-button'));

      expect(screen.getByTestId('reset-button')).toHaveTextContent('Reset Counts');
      expect(screen.queryByTestId('cancel-reset-button')).not.toBeInTheDocument();
      expect(onReset).not.toHaveBeenCalled();
    });

    it('should disable button when isResetting is true', () => {
      render(<LineZoneCrossingCard {...defaultProps} isResetting />);

      expect(screen.getByTestId('reset-button')).toBeDisabled();
      expect(screen.getByTestId('reset-button')).toHaveTextContent('Resetting...');
    });

    it('should not call onReset when disabled', async () => {
      const onReset = vi.fn();
      const user = userEvent.setup();
      render(<LineZoneCrossingCard {...defaultProps} onReset={onReset} isResetting />);

      await user.click(screen.getByTestId('reset-button'));

      expect(onReset).not.toHaveBeenCalled();
    });
  });

  describe('Net Flow Styling', () => {
    it('should have green color for positive net flow', () => {
      const zone = createMockZone({ in_count: 30, out_count: 10 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveClass('text-green-400');
    });

    it('should have red color for negative net flow', () => {
      const zone = createMockZone({ in_count: 10, out_count: 30 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveClass('text-red-400');
    });

    it('should have gray color for zero net flow', () => {
      const zone = createMockZone({ in_count: 20, out_count: 20 });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('net-flow')).toHaveClass('text-gray-400');
    });
  });

  describe('Status Badge Styling', () => {
    it('should have green styling for active zone', () => {
      const zone = createMockZone({ enabled: true });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      const badge = screen.getByTestId('zone-status-badge');
      expect(badge).toHaveClass('bg-green-500/20');
      expect(badge).toHaveClass('text-green-400');
    });

    it('should have gray styling for inactive zone', () => {
      const zone = createMockZone({ enabled: false });
      render(<LineZoneCrossingCard {...defaultProps} zone={zone} />);

      const badge = screen.getByTestId('zone-status-badge');
      expect(badge).toHaveClass('bg-gray-500/20');
      expect(badge).toHaveClass('text-gray-400');
    });
  });
});
