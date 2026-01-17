import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import RecordingDetailModal from './RecordingDetailModal';

import type { RecordingDetailResponse } from '../../services/api';

// Mock navigator.clipboard
const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.assign(navigator, { clipboard: mockClipboard });

describe('RecordingDetailModal', () => {
  const mockRecording: RecordingDetailResponse = {
    recording_id: 'rec-001',
    timestamp: '2025-01-17T10:00:00Z',
    method: 'POST',
    path: '/api/events',
    status_code: 200,
    duration_ms: 45.5,
    body_truncated: false,
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer secret-token',
      'X-Request-ID': 'req-123',
    },
    query_params: {
      limit: '10',
      offset: '0',
    },
    body: {
      name: 'Test Event',
      camera_id: 'cam-001',
    },
    response_body: {
      id: 1,
      status: 'success',
    },
    response_headers: {
      'Content-Type': 'application/json',
    },
    retrieved_at: '2025-01-17T11:00:00Z',
  };

  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    recording: mockRecording,
    isLoading: false,
    error: null as Error | null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders modal when isOpen is true', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(<RecordingDetailModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders method and path in header', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByText('POST')).toBeInTheDocument();
      expect(screen.getByText('/api/events')).toBeInTheDocument();
    });

    it('renders status code', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByText('200')).toBeInTheDocument();
    });

    it('renders duration', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByText(/45\.50\s*ms/)).toBeInTheDocument();
    });

    it('renders loading state', () => {
      render(<RecordingDetailModal {...defaultProps} recording={null} isLoading={true} />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('renders error state', () => {
      render(
        <RecordingDetailModal
          {...defaultProps}
          recording={null}
          error={new Error('Failed to load recording')}
        />
      );

      expect(screen.getByText(/failed to load recording/i)).toBeInTheDocument();
    });
  });

  describe('headers section', () => {
    it('renders request headers', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByText('Content-Type')).toBeInTheDocument();
      expect(screen.getByText('application/json')).toBeInTheDocument();
    });

    it('redacts sensitive header values', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      // Authorization header value should be redacted
      expect(screen.queryByText('Bearer secret-token')).not.toBeInTheDocument();
      expect(screen.getByText(/\[REDACTED\]/)).toBeInTheDocument();
    });
  });

  describe('body sections', () => {
    it('renders request body as formatted JSON', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      // The body should be rendered in a code block
      const requestBodySection = screen.getByText(/request body/i);
      expect(requestBodySection).toBeInTheDocument();
    });

    it('renders response body as formatted JSON', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      const responseBodySection = screen.getByText(/response body/i);
      expect(responseBodySection).toBeInTheDocument();
    });
  });

  describe('copy as cURL', () => {
    it('renders Copy as cURL button', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /copy as curl/i })).toBeInTheDocument();
    });

    it('copies cURL command to clipboard when clicked', async () => {
      render(<RecordingDetailModal {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy as curl/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(mockClipboard.writeText).toHaveBeenCalled();
      });

      // Verify cURL command format
      const curlCall = mockClipboard.writeText.mock.calls[0][0];
      expect(curlCall).toContain('curl');
      expect(curlCall).toContain('-X POST');
      expect(curlCall).toContain('/api/events');
    });

    it('shows copied feedback after copying', async () => {
      render(<RecordingDetailModal {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy as curl/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText(/copied/i)).toBeInTheDocument();
      });
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button is clicked', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });

  describe('query params', () => {
    it('renders query parameters if present', () => {
      render(<RecordingDetailModal {...defaultProps} />);

      expect(screen.getByText('limit')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });
  });
});
