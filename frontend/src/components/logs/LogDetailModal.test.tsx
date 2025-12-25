import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LogDetailModal, { type LogEntry } from './LogDetailModal';

describe('LogDetailModal', () => {
  const mockLog: LogEntry = {
    id: 1,
    timestamp: '2024-01-15T10:30:45Z',
    level: 'ERROR',
    component: 'api',
    message: 'Failed to process request due to database timeout',
    camera_id: 'camera-1',
    event_id: 123,
    request_id: 'req-abc-123',
    detection_id: 456,
    duration_ms: 5000,
    extra: {
      error_code: 500,
      retry_count: 3,
      stack_trace: 'Error at line 42',
    },
    source: 'backend',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  };

  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('does not render when isOpen is false', () => {
      render(<LogDetailModal log={mockLog} isOpen={false} onClose={mockOnClose} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders when isOpen is true', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render when log is null', () => {
      render(<LogDetailModal log={null} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('displays component name as title', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('api')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'api' })).toBeInTheDocument();
    });

    it('displays formatted timestamp', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      // Should display a human-readable date
      expect(screen.getByText(/January 15, 2024/i)).toBeInTheDocument();
    });

    it('displays log message', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Failed to process request due to database timeout')).toBeInTheDocument();
    });
  });

  describe('Level Badge', () => {
    it('displays ERROR badge with correct styling', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const errorBadge = screen.getByText('ERROR');
      expect(errorBadge).toHaveClass('text-red-400');
    });

    it('displays WARNING badge with correct styling', () => {
      const warningLog: LogEntry = {
        ...mockLog,
        level: 'WARNING',
      };

      render(<LogDetailModal log={warningLog} isOpen={true} onClose={mockOnClose} />);

      const warningBadge = screen.getByText('WARNING');
      expect(warningBadge).toHaveClass('text-yellow-400');
    });

    it('displays INFO badge with correct styling', () => {
      const infoLog: LogEntry = {
        ...mockLog,
        level: 'INFO',
      };

      render(<LogDetailModal log={infoLog} isOpen={true} onClose={mockOnClose} />);

      const infoBadge = screen.getByText('INFO');
      expect(infoBadge).toHaveClass('text-blue-400');
    });

    it('displays DEBUG badge with correct styling', () => {
      const debugLog: LogEntry = {
        ...mockLog,
        level: 'DEBUG',
      };

      render(<LogDetailModal log={debugLog} isOpen={true} onClose={mockOnClose} />);

      const debugBadge = screen.getByText('DEBUG');
      expect(debugBadge).toHaveClass('text-gray-300');
    });

    it('displays CRITICAL badge with correct styling', () => {
      const criticalLog: LogEntry = {
        ...mockLog,
        level: 'CRITICAL',
      };

      render(<LogDetailModal log={criticalLog} isOpen={true} onClose={mockOnClose} />);

      const criticalBadge = screen.getByText('CRITICAL');
      expect(criticalBadge).toHaveClass('text-white');
      expect(criticalBadge).toHaveClass('bg-red-600');
    });
  });

  describe('Log Details', () => {
    it('displays log ID', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Log ID')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('displays component', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const detailsSection = screen.getByText('Log Details').closest('div');
      expect(detailsSection).toBeInTheDocument();

      if (detailsSection) {
        expect(within(detailsSection).getByText('Component')).toBeInTheDocument();
        expect(within(detailsSection).getAllByText('api').length).toBeGreaterThan(0);
      }
    });

    it('displays source', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Source')).toBeInTheDocument();
      expect(screen.getByText('backend')).toBeInTheDocument();
    });

    it('displays camera ID when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Camera ID')).toBeInTheDocument();
      expect(screen.getByText('camera-1')).toBeInTheDocument();
    });

    it('does not display camera ID when null', () => {
      const logWithoutCamera: LogEntry = {
        ...mockLog,
        camera_id: null,
      };

      render(<LogDetailModal log={logWithoutCamera} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Camera ID')).not.toBeInTheDocument();
    });

    it('displays event ID when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Event ID')).toBeInTheDocument();
      expect(screen.getByText('123')).toBeInTheDocument();
    });

    it('does not display event ID when null', () => {
      const logWithoutEvent: LogEntry = {
        ...mockLog,
        event_id: null,
      };

      render(<LogDetailModal log={logWithoutEvent} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Event ID')).not.toBeInTheDocument();
    });

    it('displays detection ID when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Detection ID')).toBeInTheDocument();
      expect(screen.getByText('456')).toBeInTheDocument();
    });

    it('does not display detection ID when null', () => {
      const logWithoutDetection: LogEntry = {
        ...mockLog,
        detection_id: null,
      };

      render(<LogDetailModal log={logWithoutDetection} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Detection ID')).not.toBeInTheDocument();
    });

    it('displays request ID when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Request ID')).toBeInTheDocument();
      expect(screen.getByText('req-abc-123')).toBeInTheDocument();
    });

    it('does not display request ID when null', () => {
      const logWithoutRequest: LogEntry = {
        ...mockLog,
        request_id: null,
      };

      render(<LogDetailModal log={logWithoutRequest} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Request ID')).not.toBeInTheDocument();
    });

    it('displays duration when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Duration')).toBeInTheDocument();
      expect(screen.getByText('5000 ms')).toBeInTheDocument();
    });

    it('does not display duration when null', () => {
      const logWithoutDuration: LogEntry = {
        ...mockLog,
        duration_ms: null,
      };

      render(<LogDetailModal log={logWithoutDuration} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Duration')).not.toBeInTheDocument();
    });

    it('displays duration when zero', () => {
      const logWithZeroDuration: LogEntry = {
        ...mockLog,
        duration_ms: 0,
      };

      render(<LogDetailModal log={logWithZeroDuration} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Duration')).toBeInTheDocument();
      expect(screen.getByText('0 ms')).toBeInTheDocument();
    });
  });

  describe('User Agent', () => {
    it('displays user agent when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('User Agent')).toBeInTheDocument();
      expect(screen.getByText(/Mozilla\/5\.0/)).toBeInTheDocument();
    });

    it('does not display user agent section when null', () => {
      const logWithoutUserAgent: LogEntry = {
        ...mockLog,
        user_agent: null,
      };

      render(<LogDetailModal log={logWithoutUserAgent} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('User Agent')).not.toBeInTheDocument();
    });
  });

  describe('Extra Data', () => {
    it('displays extra data section when present', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Additional Data')).toBeInTheDocument();
    });

    it('displays formatted JSON in extra data', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const extraSection = screen.getByText('Additional Data').closest('div');
      expect(extraSection).toBeInTheDocument();

      if (extraSection) {
        const preElement = extraSection.querySelector('pre');
        expect(preElement).toBeInTheDocument();
        expect(preElement?.textContent).toContain('error_code');
        expect(preElement?.textContent).toContain('500');
        expect(preElement?.textContent).toContain('retry_count');
      }
    });

    it('does not display extra data section when null', () => {
      const logWithoutExtra: LogEntry = {
        ...mockLog,
        extra: null,
      };

      render(<LogDetailModal log={logWithoutExtra} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Additional Data')).not.toBeInTheDocument();
    });

    it('does not display extra data section when empty object', () => {
      const logWithEmptyExtra: LogEntry = {
        ...mockLog,
        extra: {},
      };

      render(<LogDetailModal log={logWithEmptyExtra} isOpen={true} onClose={mockOnClose} />);

      expect(screen.queryByText('Additional Data')).not.toBeInTheDocument();
    });

    it('handles complex nested extra data', () => {
      const logWithComplexExtra: LogEntry = {
        ...mockLog,
        extra: {
          nested: {
            level1: {
              level2: 'deep value',
            },
          },
          array: [1, 2, 3],
        },
      };

      render(<LogDetailModal log={logWithComplexExtra} isOpen={true} onClose={mockOnClose} />);

      const extraSection = screen.getByText('Additional Data').closest('div');
      if (extraSection) {
        const preElement = extraSection.querySelector('pre');
        expect(preElement?.textContent).toContain('nested');
        expect(preElement?.textContent).toContain('array');
      }
    });
  });

  describe('Close Interaction', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const closeButtons = screen.getAllByLabelText('Close modal');
      await user.click(closeButtons[0]);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when footer close button is clicked', async () => {
      const user = userEvent.setup();
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const closeButtons = screen.getAllByLabelText('Close modal');
      const footerCloseButton = closeButtons[closeButtons.length - 1];

      await user.click(footerCloseButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when escape key is pressed', async () => {
      const user = userEvent.setup();
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      await user.keyboard('{Escape}');

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose for other keys', async () => {
      const user = userEvent.setup();
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      await user.keyboard('{Enter}');
      await user.keyboard('{Space}');

      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('cleans up escape key listener on unmount', () => {
      const { unmount } = render(
        <LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />
      );

      unmount();

      // Should not throw errors
      expect(() => {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      }).not.toThrow();
    });
  });

  describe('Timestamp Formatting', () => {
    it('formats timestamp in readable format', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      // Should display a formatted date like "January 15, 2024 at 10:30:45 AM"
      const timestampText = screen.getByText(/January 15, 2024/i);
      expect(timestampText).toBeInTheDocument();
      expect(timestampText.textContent).toMatch(/\d{1,2}:\d{2}:\d{2}/);
    });

    it('handles invalid timestamp gracefully', () => {
      const logWithInvalidTimestamp: LogEntry = {
        ...mockLog,
        timestamp: 'invalid-date',
      };

      render(<LogDetailModal log={logWithInvalidTimestamp} isOpen={true} onClose={mockOnClose} />);

      // Should still display something (fallback to original string)
      expect(screen.getByText('invalid-date')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible dialog role', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has accessible title', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');
    });

    it('close buttons have aria-label', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      const closeButtons = screen.getAllByLabelText('Close modal');
      expect(closeButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Visual Styling', () => {
    it('uses NVIDIA dark theme colors', () => {
      const { container } = render(
        <LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />
      );

      const dialogPanel = container.querySelector('.bg-\\[\\#1A1A1A\\]');
      expect(dialogPanel).toBeInTheDocument();
    });

    it('displays green accent for extra data section', () => {
      const { container } = render(
        <LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />
      );

      const extraDataSection = container.querySelector('.bg-\\[\\#76B900\\]\\/10');
      expect(extraDataSection).toBeInTheDocument();
    });
  });

  describe('Multiple Log Types', () => {
    it('handles minimal log with only required fields', () => {
      const minimalLog: LogEntry = {
        id: 1,
        timestamp: '2024-01-01T10:00:00Z',
        level: 'INFO',
        component: 'test',
        message: 'Test message',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
        user_agent: null,
      };

      render(<LogDetailModal log={minimalLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('test')).toBeInTheDocument();
      expect(screen.getByText('Test message')).toBeInTheDocument();
      expect(screen.queryByText('Camera ID')).not.toBeInTheDocument();
      expect(screen.queryByText('Event ID')).not.toBeInTheDocument();
      expect(screen.queryByText('User Agent')).not.toBeInTheDocument();
      expect(screen.queryByText('Additional Data')).not.toBeInTheDocument();
    });

    it('handles log with all optional fields', () => {
      render(<LogDetailModal log={mockLog} isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Camera ID')).toBeInTheDocument();
      expect(screen.getByText('Event ID')).toBeInTheDocument();
      expect(screen.getByText('Detection ID')).toBeInTheDocument();
      expect(screen.getByText('Request ID')).toBeInTheDocument();
      expect(screen.getByText('Duration')).toBeInTheDocument();
      expect(screen.getByText('User Agent')).toBeInTheDocument();
      expect(screen.getByText('Additional Data')).toBeInTheDocument();
    });
  });
});
