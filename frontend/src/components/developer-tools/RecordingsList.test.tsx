import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import RecordingsList from './RecordingsList';

import type { RecordingResponse } from '../../services/api';

describe('RecordingsList', () => {
  const mockRecordings: RecordingResponse[] = [
    {
      recording_id: 'rec-001',
      timestamp: '2025-01-17T10:00:00Z',
      method: 'GET',
      path: '/api/events',
      status_code: 200,
      duration_ms: 45.5,
      body_truncated: false,
    },
    {
      recording_id: 'rec-002',
      timestamp: '2025-01-17T10:01:00Z',
      method: 'POST',
      path: '/api/cameras',
      status_code: 201,
      duration_ms: 120.3,
      body_truncated: false,
    },
    {
      recording_id: 'rec-003',
      timestamp: '2025-01-17T10:02:00Z',
      method: 'DELETE',
      path: '/api/events/123',
      status_code: 404,
      duration_ms: 15.2,
      body_truncated: false,
    },
    {
      recording_id: 'rec-004',
      timestamp: '2025-01-17T10:03:00Z',
      method: 'PUT',
      path: '/api/config',
      status_code: 500,
      duration_ms: 250.0,
      body_truncated: true,
    },
  ];

  const defaultProps = {
    recordings: mockRecordings,
    onView: vi.fn(),
    onReplay: vi.fn(),
    onDelete: vi.fn(),
    isReplaying: false,
    isDeleting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders all recordings', () => {
      render(<RecordingsList {...defaultProps} />);

      expect(screen.getByText('/api/events')).toBeInTheDocument();
      expect(screen.getByText('/api/cameras')).toBeInTheDocument();
      expect(screen.getByText('/api/events/123')).toBeInTheDocument();
      expect(screen.getByText('/api/config')).toBeInTheDocument();
    });

    it('renders method badges with correct colors', () => {
      render(<RecordingsList {...defaultProps} />);

      // Method badges are in spans inside table cells
      const methodBadges = screen.getAllByText(/^(GET|POST|DELETE|PUT)$/);
      // Filter to only the badge elements (spans with border class), not dropdown options
      const badgeElements = methodBadges.filter(
        (el) => el.tagName === 'SPAN' && el.className.includes('border')
      );

      expect(badgeElements).toHaveLength(4);
      expect(badgeElements.some((el) => el.textContent === 'GET')).toBe(true);
      expect(badgeElements.some((el) => el.textContent === 'POST')).toBe(true);
      expect(badgeElements.some((el) => el.textContent === 'DELETE')).toBe(true);
      expect(badgeElements.some((el) => el.textContent === 'PUT')).toBe(true);
    });

    it('renders status codes with correct colors', () => {
      render(<RecordingsList {...defaultProps} />);

      expect(screen.getByText('200')).toBeInTheDocument();
      expect(screen.getByText('201')).toBeInTheDocument();
      expect(screen.getByText('404')).toBeInTheDocument();
      expect(screen.getByText('500')).toBeInTheDocument();
    });

    it('renders duration in ms', () => {
      render(<RecordingsList {...defaultProps} />);

      expect(screen.getByText('45.50 ms')).toBeInTheDocument();
      expect(screen.getByText('120.30 ms')).toBeInTheDocument();
    });

    it('renders empty state when no recordings', () => {
      render(<RecordingsList {...defaultProps} recordings={[]} />);

      expect(screen.getByText('No recordings yet')).toBeInTheDocument();
    });
  });

  describe('actions', () => {
    it('calls onView when View button is clicked', () => {
      render(<RecordingsList {...defaultProps} />);

      const viewButtons = screen.getAllByRole('button', { name: /view/i });
      fireEvent.click(viewButtons[0]);

      expect(defaultProps.onView).toHaveBeenCalledWith('rec-001');
    });

    it('calls onReplay when Replay button is clicked', () => {
      render(<RecordingsList {...defaultProps} />);

      const replayButtons = screen.getAllByRole('button', { name: /replay/i });
      fireEvent.click(replayButtons[0]);

      expect(defaultProps.onReplay).toHaveBeenCalledWith('rec-001');
    });

    it('calls onDelete when Delete button is clicked', () => {
      render(<RecordingsList {...defaultProps} />);

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      fireEvent.click(deleteButtons[0]);

      expect(defaultProps.onDelete).toHaveBeenCalledWith('rec-001');
    });

    it('disables action buttons when isReplaying is true', () => {
      render(<RecordingsList {...defaultProps} isReplaying={true} />);

      const replayButtons = screen.getAllByRole('button', { name: /replay/i });
      replayButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });

    it('disables action buttons when isDeleting is true', () => {
      render(<RecordingsList {...defaultProps} isDeleting={true} />);

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      deleteButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('filtering', () => {
    it('filters recordings by method', () => {
      render(<RecordingsList {...defaultProps} />);

      const methodSelect = screen.getByRole('combobox', { name: /filter by method/i });
      fireEvent.change(methodSelect, { target: { value: 'GET' } });

      expect(screen.getByText('/api/events')).toBeInTheDocument();
      expect(screen.queryByText('/api/cameras')).not.toBeInTheDocument();
    });

    it('filters recordings by path search', () => {
      render(<RecordingsList {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search path/i);
      fireEvent.change(searchInput, { target: { value: 'events' } });

      expect(screen.getByText('/api/events')).toBeInTheDocument();
      expect(screen.getByText('/api/events/123')).toBeInTheDocument();
      expect(screen.queryByText('/api/cameras')).not.toBeInTheDocument();
    });

    it('filters recordings by status code type', () => {
      render(<RecordingsList {...defaultProps} />);

      const statusSelect = screen.getByRole('combobox', { name: /filter by status/i });
      fireEvent.change(statusSelect, { target: { value: '4xx' } });

      expect(screen.getByText('/api/events/123')).toBeInTheDocument();
      expect(screen.queryByText('/api/events')).not.toBeInTheDocument();
    });

    it('shows no results message when filters match nothing', () => {
      render(<RecordingsList {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search path/i);
      fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

      expect(screen.getByText(/no recordings match/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible table structure', () => {
      render(<RecordingsList {...defaultProps} />);

      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getAllByRole('columnheader')).toHaveLength(6);
      expect(screen.getAllByRole('row')).toHaveLength(mockRecordings.length + 1); // +1 for header
    });

    it('has accessible action buttons with aria-labels', () => {
      render(<RecordingsList {...defaultProps} />);

      expect(screen.getAllByRole('button', { name: /view recording/i })).toHaveLength(4);
      expect(screen.getAllByRole('button', { name: /replay recording/i })).toHaveLength(4);
      expect(screen.getAllByRole('button', { name: /delete recording/i })).toHaveLength(4);
    });
  });
});
