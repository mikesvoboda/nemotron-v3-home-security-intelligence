import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ReplayResultsModal from './ReplayResultsModal';

import type { ReplayResponse } from '../../services/api';

describe('ReplayResultsModal', () => {
  const mockSuccessResult: ReplayResponse = {
    recording_id: 'rec-001',
    original_status_code: 200,
    replay_status_code: 200,
    replay_response: { id: 1, status: 'success' },
    replay_metadata: {
      original_timestamp: '2025-01-17T10:00:00Z',
      original_path: '/api/events',
      original_method: 'GET',
      replay_duration_ms: 45.5,
      replayed_at: '2025-01-17T11:00:00Z',
    },
    timestamp: '2025-01-17T11:00:00Z',
  };

  const mockDifferentStatusResult: ReplayResponse = {
    recording_id: 'rec-002',
    original_status_code: 200,
    replay_status_code: 404,
    replay_response: { error: 'Not found' },
    replay_metadata: {
      original_timestamp: '2025-01-17T10:00:00Z',
      original_path: '/api/events/123',
      original_method: 'GET',
      replay_duration_ms: 15.2,
      replayed_at: '2025-01-17T11:00:00Z',
    },
    timestamp: '2025-01-17T11:00:00Z',
  };

  const mockErrorResult: ReplayResponse = {
    recording_id: 'rec-003',
    original_status_code: 200,
    replay_status_code: 500,
    replay_response: { error: 'Internal server error' },
    replay_metadata: {
      original_timestamp: '2025-01-17T10:00:00Z',
      original_path: '/api/events',
      original_method: 'POST',
      replay_duration_ms: 250.0,
      replayed_at: '2025-01-17T11:00:00Z',
    },
    timestamp: '2025-01-17T11:00:00Z',
  };

  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    result: mockSuccessResult,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders modal when isOpen is true', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(<ReplayResultsModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders replay results title', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      expect(screen.getByText(/replay results/i)).toBeInTheDocument();
    });

    it('renders null state when result is null', () => {
      render(<ReplayResultsModal {...defaultProps} result={null} />);

      expect(screen.getByText(/no replay results/i)).toBeInTheDocument();
    });
  });

  describe('status comparison', () => {
    it('shows matching status codes when they are the same', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      // Both original and replay show 200, so use getAllByText
      const statusBadges = screen.getAllByText('200');
      expect(statusBadges).toHaveLength(2); // Original and replay
      expect(screen.getByText(/match/i)).toBeInTheDocument();
    });

    it('shows different status codes when they differ', () => {
      render(<ReplayResultsModal {...defaultProps} result={mockDifferentStatusResult} />);

      // Should show both status codes
      expect(screen.getByText('200')).toBeInTheDocument();
      expect(screen.getByText('404')).toBeInTheDocument();
      expect(screen.getByText(/differ/i)).toBeInTheDocument();
    });

    it('shows error indicator for 5xx status', () => {
      render(<ReplayResultsModal {...defaultProps} result={mockErrorResult} />);

      expect(screen.getByText('500')).toBeInTheDocument();
    });
  });

  describe('duration comparison', () => {
    it('shows replay duration', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      expect(screen.getByText(/45\.50\s*ms/)).toBeInTheDocument();
    });
  });

  describe('response body comparison', () => {
    it('shows replay response body', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      // Response body section should exist
      expect(screen.getByText(/replay response/i)).toBeInTheDocument();
    });

    it('formats JSON response body', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      // Should contain JSON formatted content
      expect(screen.getByText(/"status":/)).toBeInTheDocument();
    });
  });

  describe('metadata', () => {
    it('shows original path and method', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      expect(screen.getByText('/api/events')).toBeInTheDocument();
      expect(screen.getByText('GET')).toBeInTheDocument();
    });

    it('shows replay timestamp', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      // Should show replayed at time
      expect(screen.getByText(/replayed at/i)).toBeInTheDocument();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button is clicked', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });

  describe('visual indicators', () => {
    it('shows success indicator for matching status codes', () => {
      render(<ReplayResultsModal {...defaultProps} />);

      // Should have a success visual indicator (green)
      const statusSection = screen.getByTestId('status-comparison');
      expect(statusSection).toHaveClass('border-green-500/20');
    });

    it('shows warning indicator for different status codes', () => {
      render(<ReplayResultsModal {...defaultProps} result={mockDifferentStatusResult} />);

      const statusSection = screen.getByTestId('status-comparison');
      expect(statusSection).toHaveClass('border-yellow-500/20');
    });
  });
});
