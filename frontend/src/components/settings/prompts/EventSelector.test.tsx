/**
 * Tests for EventSelector component
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import EventSelector from './EventSelector';

import type { Event } from '../../../types/generated';

// ============================================================================
// Test Data
// ============================================================================

const mockEvents: Event[] = [
  {
    id: 1234,
    camera_id: 'front_door',
    started_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    detection_count: 3,
    risk_level: 'high',
    risk_score: 72,
    reviewed: false,
  },
  {
    id: 1233,
    camera_id: 'backyard',
    started_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
    detection_count: 2,
    risk_level: 'medium',
    risk_score: 45,
    reviewed: true,
  },
  {
    id: 1232,
    camera_id: 'garage',
    started_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
    detection_count: 1,
    risk_level: 'low',
    risk_score: 15,
    reviewed: false,
  },
];

// ============================================================================
// Tests
// ============================================================================

describe('EventSelector', () => {
  describe('rendering', () => {
    it('renders the component with events', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByTestId('event-selector')).toBeInTheDocument();
      expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      expect(screen.getByText(/Event #1233/i)).toBeInTheDocument();
      expect(screen.getByText(/Event #1232/i)).toBeInTheDocument();
    });

    it('renders empty state when no events', () => {
      render(<EventSelector events={[]} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByText(/No events available/i)).toBeInTheDocument();
    });

    it('renders loading state', () => {
      render(
        <EventSelector events={[]} selectedEventId={null} onSelect={vi.fn()} isLoading={true} />
      );

      expect(screen.getByText(/Loading events/i)).toBeInTheDocument();
    });

    it('renders search input', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(
        screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i)
      ).toBeInTheDocument();
    });

    it('displays risk level badges', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByText(/High Risk/i)).toBeInTheDocument();
      expect(screen.getByText(/Medium Risk/i)).toBeInTheDocument();
      expect(screen.getByText(/Low Risk/i)).toBeInTheDocument();
    });

    it('displays camera names formatted correctly', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByText(/Front Door/i)).toBeInTheDocument();
      expect(screen.getByText(/Backyard/i)).toBeInTheDocument();
      expect(screen.getByText(/Garage/i)).toBeInTheDocument();
    });

    it('displays detection counts', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByText(/3 detections/i)).toBeInTheDocument();
      expect(screen.getByText(/2 detections/i)).toBeInTheDocument();
      expect(screen.getByText(/1 detection$/i)).toBeInTheDocument();
    });
  });

  describe('selection', () => {
    it('highlights selected event', () => {
      render(<EventSelector events={mockEvents} selectedEventId={1234} onSelect={vi.fn()} />);

      const selectedOption = screen.getByTestId('event-option-1234');
      expect(selectedOption).toHaveAttribute('aria-selected', 'true');
    });

    it('calls onSelect when event is clicked', async () => {
      const handleSelect = vi.fn();
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={handleSelect} />);

      await user.click(screen.getByTestId('event-option-1233'));

      expect(handleSelect).toHaveBeenCalledWith(1233);
    });

    it('does not call onSelect when disabled', async () => {
      const handleSelect = vi.fn();
      const user = userEvent.setup();

      render(
        <EventSelector
          events={mockEvents}
          selectedEventId={null}
          onSelect={handleSelect}
          disabled={true}
        />
      );

      await user.click(screen.getByTestId('event-option-1234'));

      expect(handleSelect).not.toHaveBeenCalled();
    });
  });

  describe('search/filtering', () => {
    it('filters events by camera name', async () => {
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      const searchInput = screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i);
      await user.type(searchInput, 'front');

      expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      expect(screen.queryByText(/Event #1233/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Event #1232/i)).not.toBeInTheDocument();
    });

    it('filters events by event ID', async () => {
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      const searchInput = screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i);
      await user.type(searchInput, '1233');

      expect(screen.queryByText(/Event #1234/i)).not.toBeInTheDocument();
      expect(screen.getByText(/Event #1233/i)).toBeInTheDocument();
      expect(screen.queryByText(/Event #1232/i)).not.toBeInTheDocument();
    });

    it('filters events by risk level', async () => {
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      const searchInput = screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i);
      await user.type(searchInput, 'high');

      expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      expect(screen.queryByText(/Event #1233/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Event #1232/i)).not.toBeInTheDocument();
    });

    it('shows no results message when search yields no matches', async () => {
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      const searchInput = screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i);
      await user.type(searchInput, 'nonexistent');

      expect(screen.getByText(/No events match your search/i)).toBeInTheDocument();
    });

    it('displays filtered count correctly', async () => {
      const user = userEvent.setup();

      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      // Initially shows all 3
      expect(screen.getByText(/Showing 3 of 3 events/i)).toBeInTheDocument();

      // After filtering
      const searchInput = screen.getByPlaceholderText(/Search by camera, event ID, or risk level/i);
      await user.type(searchInput, 'front');

      expect(screen.getByText(/Showing 1 of 3 event/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper listbox role', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });

    it('has proper option roles', () => {
      render(<EventSelector events={mockEvents} selectedEventId={null} onSelect={vi.fn()} />);

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(3);
    });

    it('has aria-selected on selected option', () => {
      render(<EventSelector events={mockEvents} selectedEventId={1234} onSelect={vi.fn()} />);

      const selectedOption = screen.getByRole('option', { selected: true });
      expect(selectedOption).toBeInTheDocument();
    });
  });
});
