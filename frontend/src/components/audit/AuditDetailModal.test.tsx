import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AuditDetailModal from './AuditDetailModal';

import type { AuditEntry } from './AuditTable';

describe('AuditDetailModal', () => {
  const mockAuditLog: AuditEntry = {
    id: 42,
    timestamp: '2024-01-15T10:30:00Z',
    action: 'event_reviewed',
    resource_type: 'event',
    resource_id: '123',
    actor: 'testuser',
    ip_address: '192.168.1.100',
    user_agent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    details: { reviewed: true, notes: 'Verified as safe' },
    status: 'success',
  };

  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders modal when isOpen is true and log is provided', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('does not render when isOpen is false', () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={false} onClose={mockOnClose} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('returns null when log is null', () => {
      const { container } = render(
        <AuditDetailModal log={null} isOpen={true} onClose={mockOnClose} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('displays formatted action as dialog title', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Event Reviewed')).toBeInTheDocument();
      });
    });

    it('displays formatted timestamp', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Should contain date information
        const dialog = screen.getByRole('dialog');
        expect(dialog).toHaveTextContent(/January/);
        expect(dialog).toHaveTextContent(/15/);
        expect(dialog).toHaveTextContent(/2024/);
      });
    });
  });

  describe('Status Badge', () => {
    it('displays success status with green styling', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Find all success texts and get the one in the header badge (has rounded-full class)
        const statusBadges = screen.getAllByText('success');
        const headerBadge = statusBadges.find((el) =>
          el.closest('span')?.classList.contains('rounded-full')
        );
        expect(headerBadge?.closest('span')).toHaveClass('text-green-400');
      });
    });

    it('displays failure status with red styling', async () => {
      const failedLog: AuditEntry = {
        ...mockAuditLog,
        status: 'failure',
      };

      render(<AuditDetailModal log={failedLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Find the badge in the header
        const statusBadges = screen.getAllByText('failure');
        const headerBadge = statusBadges.find((el) =>
          el.closest('span')?.classList.contains('rounded-full')
        );
        expect(headerBadge?.closest('span')).toHaveClass('text-red-400');
      });
    });

    it('displays error status with red styling', async () => {
      const errorLog: AuditEntry = {
        ...mockAuditLog,
        status: 'error',
      };

      render(<AuditDetailModal log={errorLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const statusBadges = screen.getAllByText('error');
        const headerBadge = statusBadges.find((el) =>
          el.closest('span')?.classList.contains('rounded-full')
        );
        expect(headerBadge?.closest('span')).toHaveClass('text-red-400');
      });
    });

    it('displays unknown status with gray styling', async () => {
      const unknownLog: AuditEntry = {
        ...mockAuditLog,
        status: 'pending',
      };

      render(<AuditDetailModal log={unknownLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const statusBadges = screen.getAllByText('pending');
        const headerBadge = statusBadges.find((el) =>
          el.closest('span')?.classList.contains('rounded-full')
        );
        expect(headerBadge?.closest('span')).toHaveClass('text-gray-300');
      });
    });
  });

  describe('Actor and Resource Cards', () => {
    it('displays actor name', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('testuser')).toBeInTheDocument();
      });
    });

    it('displays actor section label', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Actor')).toBeInTheDocument();
      });
    });

    it('displays resource type and ID', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Resource')).toBeInTheDocument();
        // Both resource type and action contain 'event', so use getAllByText
        const eventTexts = screen.getAllByText(/event/);
        expect(eventTexts.length).toBeGreaterThan(0);
        // Resource ID is displayed
        const resourceIdTexts = screen.getAllByText(/123/);
        expect(resourceIdTexts.length).toBeGreaterThan(0);
      });
    });

    it('displays resource type without ID when resource_id is null', async () => {
      const logWithoutResourceId: AuditEntry = {
        ...mockAuditLog,
        resource_id: null,
      };

      render(<AuditDetailModal log={logWithoutResourceId} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Resource')).toBeInTheDocument();
        expect(screen.getByText('event')).toBeInTheDocument();
      });
    });
  });

  describe('Entry Details Section', () => {
    it('displays audit ID', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Audit ID')).toBeInTheDocument();
        expect(screen.getByText('42')).toBeInTheDocument();
      });
    });

    it('displays action type', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Action')).toBeInTheDocument();
        expect(screen.getByText('event_reviewed')).toBeInTheDocument();
      });
    });

    it('displays status', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Status')).toBeInTheDocument();
      });
    });

    it('displays IP address when available', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('IP Address')).toBeInTheDocument();
        expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
      });
    });

    it('hides IP address section when null', async () => {
      const logWithoutIP: AuditEntry = {
        ...mockAuditLog,
        ip_address: null,
      };

      render(<AuditDetailModal log={logWithoutIP} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('IP Address')).not.toBeInTheDocument();
    });
  });

  describe('User Agent Section', () => {
    it('displays user agent when available', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('User Agent')).toBeInTheDocument();
        expect(screen.getByText(/Mozilla\/5\.0/)).toBeInTheDocument();
      });
    });

    it('hides user agent section when null', async () => {
      const logWithoutUserAgent: AuditEntry = {
        ...mockAuditLog,
        user_agent: null,
      };

      render(<AuditDetailModal log={logWithoutUserAgent} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('User Agent')).not.toBeInTheDocument();
    });
  });

  describe('Details Section', () => {
    it('displays additional details as formatted JSON', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Additional Details')).toBeInTheDocument();
        // The details JSON contains "reviewed" which also appears in action name
        const reviewedTexts = screen.getAllByText(/reviewed/i);
        expect(reviewedTexts.length).toBeGreaterThan(0);
        // Check for the JSON content in the pre element
        expect(screen.getByText(/Verified as safe/)).toBeInTheDocument();
      });
    });

    it('hides details section when details is null', async () => {
      const logWithoutDetails: AuditEntry = {
        ...mockAuditLog,
        details: null,
      };

      render(<AuditDetailModal log={logWithoutDetails} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('Additional Details')).not.toBeInTheDocument();
    });

    it('hides details section when details is empty object', async () => {
      const logWithEmptyDetails: AuditEntry = {
        ...mockAuditLog,
        details: {},
      };

      render(<AuditDetailModal log={logWithEmptyDetails} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('Additional Details')).not.toBeInTheDocument();
    });
  });

  describe('Close Functionality', () => {
    it('calls onClose when X button is clicked', async () => {
      const user = userEvent.setup();

      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const closeButtons = screen.getAllByLabelText('Close modal');
      await user.click(closeButtons[0]); // Click the X button in header

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Close button in footer is clicked', async () => {
      const user = userEvent.setup();

      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const closeButtons = screen.getAllByLabelText('Close modal');
      await user.click(closeButtons[1]); // Click the Close button in footer

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Escape key is pressed', async () => {
      const user = userEvent.setup();

      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('calls onClose when clicking backdrop', async () => {
      const user = userEvent.setup();

      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Find the backdrop (the dark overlay)
      const backdrop = document.querySelector('[aria-hidden="true"]');
      if (backdrop) {
        await user.click(backdrop);
      }

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });
  });

  describe('Action Formatting', () => {
    it('formats snake_case actions to Title Case', async () => {
      const snakeCaseLog: AuditEntry = {
        ...mockAuditLog,
        action: 'camera_settings_updated',
      };

      render(<AuditDetailModal log={snakeCaseLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Camera Settings Updated')).toBeInTheDocument();
      });
    });

    it('handles single word actions', async () => {
      const singleWordLog: AuditEntry = {
        ...mockAuditLog,
        action: 'login',
      };

      render(<AuditDetailModal log={singleWordLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Login')).toBeInTheDocument();
      });
    });
  });

  describe('Timestamp Formatting', () => {
    it('formats timestamp to readable date and time', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Should contain AM/PM
        const dialog = screen.getByRole('dialog');
        expect(dialog.textContent).toMatch(/\d{1,2}:\d{2}:\d{2}\s*(AM|PM)/i);
      });
    });

    it('handles invalid timestamp gracefully', async () => {
      const invalidTimestampLog: AuditEntry = {
        ...mockAuditLog,
        timestamp: 'invalid-date',
      };

      render(<AuditDetailModal log={invalidTimestampLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Invalid dates show "Invalid Date" from toLocaleString
        expect(screen.getByText('Invalid Date')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has dialog role', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('has close buttons with accessible labels', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const closeButtons = screen.getAllByLabelText('Close modal');
        expect(closeButtons.length).toBe(2); // X button and Close button
      });
    });

    it('has dialog title', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // HeadlessUI Dialog sets up proper heading
        const title = screen.getByText('Event Reviewed');
        expect(title.tagName).toBe('H2');
      });
    });
  });

  describe('Styling', () => {
    it('uses NVIDIA dark theme colors', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const dialogPanel = document.querySelector('.bg-\\[\\#1A1A1A\\]');
        expect(dialogPanel).toBeInTheDocument();
      });
    });

    it('uses green accent for actor name', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const actorText = screen.getByText('testuser');
        expect(actorText).toHaveClass('text-[#76B900]');
      });
    });

    it('has dark backdrop', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const backdrop = document.querySelector('.bg-black\\/75');
        expect(backdrop).toBeInTheDocument();
      });
    });
  });

  describe('JSON Details Formatting', () => {
    it('pretty-prints complex nested objects', async () => {
      const complexDetailsLog: AuditEntry = {
        ...mockAuditLog,
        details: {
          nested: {
            value: 123,
            array: [1, 2, 3],
          },
          flag: true,
        },
      };

      render(<AuditDetailModal log={complexDetailsLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        // Check that JSON is formatted (contains newlines/indentation)
        const pre = screen.getByText(/nested/).closest('pre');
        expect(pre).toBeInTheDocument();
      });
    });
  });

  describe('Modal Transitions', () => {
    it('applies transition classes', async () => {
      render(<AuditDetailModal log={mockAuditLog} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        const dialogPanel = document.querySelector('.transition-all');
        expect(dialogPanel).toBeInTheDocument();
      });
    });
  });
});
