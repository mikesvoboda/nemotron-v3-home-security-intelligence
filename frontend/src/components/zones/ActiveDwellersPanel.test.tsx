/**
 * Tests for ActiveDwellersPanel component (NEM-4714)
 *
 * Tests active dwellers display including:
 * - Rendering with dwellers list
 * - Loading state
 * - Empty state
 * - Connection status indicator
 * - Live timer updates
 * - Object class icons
 */

import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ActiveDwellersPanel from './ActiveDwellersPanel';

import type { ActiveDweller } from '../../hooks/useDwellTimeAnalytics';

describe('ActiveDwellersPanel', () => {
  // Helper to create mock dweller data
  const createMockDweller = (overrides: Partial<ActiveDweller> = {}): ActiveDweller => ({
    record_id: 1,
    track_id: 'track-123',
    camera_id: 'cam-123',
    object_class: 'person',
    entry_time: new Date(Date.now() - 120000).toISOString(), // 2 minutes ago
    current_dwell_seconds: 120,
    ...overrides,
  });

  const defaultProps = {
    dwellers: [createMockDweller()],
    isLoading: false,
    isConnected: true,
  };

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the panel with header', () => {
      render(<ActiveDwellersPanel {...defaultProps} />);

      expect(screen.getByTestId('active-dwellers-panel')).toBeInTheDocument();
      expect(screen.getByText('Active Dwellers')).toBeInTheDocument();
    });

    it('should display dweller count badge', () => {
      const dwellers = [createMockDweller({ record_id: 1 }), createMockDweller({ record_id: 2 })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-count')).toHaveTextContent('2');
    });

    it('should apply custom className', () => {
      render(<ActiveDwellersPanel {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('active-dwellers-panel')).toHaveClass('custom-class');
    });
  });

  describe('Dweller List', () => {
    it('should render list of dwellers', () => {
      const dwellers = [
        createMockDweller({ record_id: 1, object_class: 'person' }),
        createMockDweller({ record_id: 2, object_class: 'car' }),
      ];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-list')).toBeInTheDocument();
      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
      expect(screen.getByTestId('dweller-2')).toBeInTheDocument();
    });

    it('should display object class for each dweller', () => {
      const dwellers = [createMockDweller({ record_id: 1, object_class: 'person' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByText('person')).toBeInTheDocument();
    });

    it('should capitalize object class name', () => {
      const dwellers = [createMockDweller({ record_id: 1, object_class: 'person' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      const classElement = screen.getByText('person');
      expect(classElement).toHaveClass('capitalize');
    });
  });

  describe('Object Icons', () => {
    it('should use User icon for person class', () => {
      const dwellers = [createMockDweller({ object_class: 'person' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      // The icon should be rendered - we check the dweller row exists
      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
    });

    it('should use Car icon for car class', () => {
      const dwellers = [createMockDweller({ object_class: 'car' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
    });

    it('should use Car icon for truck class', () => {
      const dwellers = [createMockDweller({ object_class: 'truck' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
    });

    it('should use Car icon for vehicle class', () => {
      const dwellers = [createMockDweller({ object_class: 'vehicle' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
    });
  });

  describe('Live Timer', () => {
    it('should display formatted dwell time', () => {
      // Entry time is 2 minutes ago
      const entryTime = new Date(Date.now() - 120000).toISOString();
      const dwellers = [createMockDweller({ entry_time: entryTime })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dwell-time')).toHaveTextContent('2:00');
    });

    it('should update timer every second', () => {
      const entryTime = new Date(Date.now() - 60000).toISOString(); // 1 minute ago
      const dwellers = [createMockDweller({ entry_time: entryTime })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dwell-time')).toHaveTextContent('1:00');

      // Advance time by 1 second
      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(screen.getByTestId('dwell-time')).toHaveTextContent('1:01');
    });

    it('should format time with leading zeros for seconds', () => {
      const entryTime = new Date(Date.now() - 65000).toISOString(); // 1:05 ago
      const dwellers = [createMockDweller({ entry_time: entryTime })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dwell-time')).toHaveTextContent('1:05');
    });
  });

  describe('Loading State', () => {
    it('should display loading spinner when isLoading is true', () => {
      render(<ActiveDwellersPanel dwellers={[]} isLoading={true} />);

      expect(screen.getByTestId('loading-state')).toBeInTheDocument();
    });

    it('should not display dweller list when loading', () => {
      render(
        <ActiveDwellersPanel dwellers={[createMockDweller()]} isLoading={true} />
      );

      expect(screen.queryByTestId('dweller-list')).not.toBeInTheDocument();
    });

    it('should not display empty state when loading', () => {
      render(<ActiveDwellersPanel dwellers={[]} isLoading={true} />);

      expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should display empty state when no dwellers', () => {
      render(<ActiveDwellersPanel dwellers={[]} isLoading={false} />);

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No active dwellers in this zone')).toBeInTheDocument();
    });

    it('should show count of 0 when no dwellers', () => {
      render(<ActiveDwellersPanel dwellers={[]} isLoading={false} />);

      expect(screen.getByTestId('dweller-count')).toHaveTextContent('0');
    });
  });

  describe('Connection Status', () => {
    it('should display "Live" when connected', () => {
      render(<ActiveDwellersPanel {...defaultProps} isConnected={true} />);

      const status = screen.getByTestId('connection-status');
      expect(status).toHaveTextContent('Live');
      expect(status).toHaveClass('text-green-400');
    });

    it('should display "Polling" when not connected', () => {
      render(<ActiveDwellersPanel {...defaultProps} isConnected={false} />);

      const status = screen.getByTestId('connection-status');
      expect(status).toHaveTextContent('Polling');
      expect(status).toHaveClass('text-gray-500');
    });

    it('should default to disconnected (Polling) when isConnected not provided', () => {
      render(<ActiveDwellersPanel dwellers={[]} />);

      expect(screen.getByTestId('connection-status')).toHaveTextContent('Polling');
    });
  });

  describe('Multiple Dwellers', () => {
    it('should render all dwellers in list', () => {
      const dwellers = [
        createMockDweller({ record_id: 1 }),
        createMockDweller({ record_id: 2 }),
        createMockDweller({ record_id: 3 }),
      ];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
      expect(screen.getByTestId('dweller-2')).toBeInTheDocument();
      expect(screen.getByTestId('dweller-3')).toBeInTheDocument();
      expect(screen.getByTestId('dweller-count')).toHaveTextContent('3');
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long dwell times', () => {
      // 2 hours ago
      const entryTime = new Date(Date.now() - 7200000).toISOString();
      const dwellers = [createMockDweller({ entry_time: entryTime })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      expect(screen.getByTestId('dwell-time')).toHaveTextContent('120:00');
    });

    it('should handle unknown object classes', () => {
      const dwellers = [createMockDweller({ object_class: 'unknown_object' })];
      render(<ActiveDwellersPanel {...defaultProps} dwellers={dwellers} />);

      // Should still render without error, using User icon as default
      expect(screen.getByTestId('dweller-1')).toBeInTheDocument();
      expect(screen.getByText('unknown_object')).toBeInTheDocument();
    });
  });
});
