import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertCard from './AlertCard';

import type { AlertActionParams, AlertCardProps } from './AlertCard';

// Helper to create a timestamp X minutes ago
const minutesAgo = (minutes: number): string => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - minutes);
  return date.toISOString();
};

describe('AlertCard', () => {
  // Use vi.fn() fresh in each test with proper types for NEM-3626
  let mockOnAcknowledge: ReturnType<typeof vi.fn<(params: AlertActionParams) => void>>;
  let mockOnDismiss: ReturnType<typeof vi.fn<(params: AlertActionParams) => void>>;
  let mockOnSnooze: ReturnType<typeof vi.fn<(alertId: string, seconds: number) => void>>;
  let mockOnViewEvent: ReturnType<typeof vi.fn<(eventId: number) => void>>;

  beforeEach(() => {
    mockOnAcknowledge = vi.fn();
    mockOnDismiss = vi.fn();
    mockOnSnooze = vi.fn();
    mockOnViewEvent = vi.fn();
  });

  const createMockAlert = (overrides?: Partial<AlertCardProps>): AlertCardProps => ({
    id: 'alert-1',
    eventId: 123,
    severity: 'high',
    status: 'pending',
    timestamp: minutesAgo(30), // 30 minutes ago for relative time display
    camera_name: 'Front Door',
    risk_score: 75,
    summary: 'Person detected near entrance',
    dedup_key: 'front_door:person',
    version_id: 1,
    onAcknowledge: mockOnAcknowledge,
    onDismiss: mockOnDismiss,
    onSnooze: mockOnSnooze,
    onViewEvent: mockOnViewEvent,
    ...overrides,
  });

  // Legacy mock for backward compatibility with existing tests
  // Note: The callbacks use AlertActionParams now (NEM-3626)
  const mockAlert: AlertCardProps = {
    id: 'alert-1',
    eventId: 123,
    severity: 'high',
    status: 'pending',
    timestamp: minutesAgo(30),
    camera_name: 'Front Door',
    risk_score: 75,
    summary: 'Person detected near entrance',
    dedup_key: 'front_door:person',
    onAcknowledge: vi.fn() as unknown as AlertCardProps['onAcknowledge'],
    onDismiss: vi.fn() as unknown as AlertCardProps['onDismiss'],
    onSnooze: vi.fn() as unknown as AlertCardProps['onSnooze'],
    onViewEvent: vi.fn() as unknown as AlertCardProps['onViewEvent'],
  };

  describe('Rendering', () => {
    it('renders alert summary and camera name', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('displays timestamp in relative format', () => {
      render(<AlertCard {...mockAlert} />);

      // Should show relative time like "X hours ago"
      expect(screen.getByText(/ago$/)).toBeInTheDocument();
    });

    it('displays risk score with badge', () => {
      render(<AlertCard {...mockAlert} />);

      // Check for risk badge presence
      const badge = screen.getByText('High');
      expect(badge).toBeInTheDocument();
    });

    it('shows severity indicator with correct color for critical', () => {
      render(<AlertCard {...mockAlert} severity="critical" />);

      const card = screen.getByRole('article');
      // Critical should have red border/accent
      expect(card).toHaveClass(/border-red/);
    });

    it('shows severity indicator with correct color for high', () => {
      render(<AlertCard {...mockAlert} severity="high" />);

      const card = screen.getByRole('article');
      // High should have orange border/accent
      expect(card).toHaveClass(/border-orange/);
    });

    it('shows severity indicator with correct color for medium', () => {
      render(<AlertCard {...mockAlert} severity="medium" />);

      const card = screen.getByRole('article');
      // Medium should have yellow border/accent
      expect(card).toHaveClass(/border-yellow/);
    });
  });

  describe('Status Display', () => {
    it('shows unacknowledged badge for pending status', () => {
      render(<AlertCard {...mockAlert} status="pending" />);

      expect(screen.getByText('Unacknowledged')).toBeInTheDocument();
    });

    it('shows acknowledged badge for acknowledged status', () => {
      render(<AlertCard {...mockAlert} status="acknowledged" />);

      expect(screen.getByText('Acknowledged')).toBeInTheDocument();
    });

    it('does not show status badge for dismissed status', () => {
      render(<AlertCard {...mockAlert} status="dismissed" />);

      expect(screen.queryByText('Unacknowledged')).not.toBeInTheDocument();
      expect(screen.queryByText('Acknowledged')).not.toBeInTheDocument();
    });
  });

  describe('Actions', () => {
    it('displays acknowledge button for pending alerts', () => {
      render(<AlertCard {...mockAlert} status="pending" />);

      expect(screen.getByRole('button', { name: /acknowledge/i })).toBeInTheDocument();
    });

    it('calls onAcknowledge with alertId and versionId when acknowledge button is clicked', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ version_id: 5 });

      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeBtn);

      expect(mockOnAcknowledge).toHaveBeenCalledWith({
        alertId: 'alert-1',
        versionId: 5,
      });
    });

    it('calls onAcknowledge with undefined versionId when version_id not provided', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ version_id: undefined });

      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeBtn);

      expect(mockOnAcknowledge).toHaveBeenCalledWith({
        alertId: 'alert-1',
        versionId: undefined,
      });
    });

    it('displays dismiss button', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('calls onDismiss with alertId and versionId when dismiss button is clicked', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ version_id: 3 });

      render(<AlertCard {...alert} />);

      const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
      await user.click(dismissBtn);

      expect(mockOnDismiss).toHaveBeenCalledWith({
        alertId: 'alert-1',
        versionId: 3,
      });
    });

    it('displays view event button', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByRole('button', { name: /view event/i })).toBeInTheDocument();
    });

    it('calls onViewEvent when view event button is clicked', async () => {
      const handleViewEvent = vi.fn();
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} onViewEvent={handleViewEvent} />);

      const viewBtn = screen.getByRole('button', { name: /view event/i });
      await user.click(viewBtn);

      expect(handleViewEvent).toHaveBeenCalledWith(123);
    });

    it('displays snooze dropdown menu', async () => {
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} />);

      // Click the dropdown trigger button
      const menuBtn = screen.getByRole('button', { name: /more options/i });
      await user.click(menuBtn);

      // Should show snooze options
      await waitFor(() => {
        expect(screen.getByText('Snooze 15 min')).toBeInTheDocument();
      });
    });

    it('calls onSnooze with correct duration when snooze option is clicked', async () => {
      const handleSnooze = vi.fn();
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} onSnooze={handleSnooze} />);

      // Open dropdown
      const menuBtn = screen.getByRole('button', { name: /more options/i });
      await user.click(menuBtn);

      // Click 1 hour snooze
      await waitFor(() => {
        expect(screen.getByText('Snooze 1 hour')).toBeInTheDocument();
      });

      const snoozeOption = screen.getByText('Snooze 1 hour');
      await user.click(snoozeOption);

      expect(handleSnooze).toHaveBeenCalledWith('alert-1', 3600);
    });

    it('does not show acknowledge button for acknowledged alerts', () => {
      render(<AlertCard {...mockAlert} status="acknowledged" />);

      expect(screen.queryByRole('button', { name: /acknowledge/i })).not.toBeInTheDocument();
    });
  });

  describe('Loading State (NEM-3626)', () => {
    it('disables acknowledge button when isLoading is true', () => {
      const alert = createMockAlert({ isLoading: true });
      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      expect(acknowledgeBtn).toBeDisabled();
    });

    it('disables dismiss button when isLoading is true', () => {
      const alert = createMockAlert({ isLoading: true });
      render(<AlertCard {...alert} />);

      const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
      expect(dismissBtn).toBeDisabled();
    });

    it('shows loading spinner on acknowledge button when isLoading', () => {
      const alert = createMockAlert({ isLoading: true });
      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      // Check for animate-spin class on the icon
      const spinner = acknowledgeBtn.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('buttons are enabled when isLoading is false', () => {
      const alert = createMockAlert({ isLoading: false });
      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      const dismissBtn = screen.getByRole('button', { name: /dismiss/i });

      expect(acknowledgeBtn).not.toBeDisabled();
      expect(dismissBtn).not.toBeDisabled();
    });

    it('does not call onAcknowledge when button clicked while loading', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ isLoading: true });

      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeBtn);

      expect(mockOnAcknowledge).not.toHaveBeenCalled();
    });
  });

  describe('Optimistic Locking (NEM-3626)', () => {
    it('includes version_id in acknowledge callback params', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ version_id: 42 });

      render(<AlertCard {...alert} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeBtn);

      expect(mockOnAcknowledge).toHaveBeenCalledWith(
        expect.objectContaining({ versionId: 42 })
      );
    });

    it('includes version_id in dismiss callback params', async () => {
      const user = userEvent.setup();
      const alert = createMockAlert({ version_id: 99 });

      render(<AlertCard {...alert} />);

      const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
      await user.click(dismissBtn);

      expect(mockOnDismiss).toHaveBeenCalledWith(
        expect.objectContaining({ versionId: 99 })
      );
    });
  });

  describe('Checkbox Selection', () => {
    it('displays checkbox when selected prop is provided', () => {
      render(<AlertCard {...mockAlert} selected={false} onSelectChange={vi.fn()} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).not.toBeChecked();
    });

    it('checkbox is checked when selected is true', () => {
      render(<AlertCard {...mockAlert} selected={true} onSelectChange={vi.fn()} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('calls onSelectChange when checkbox is clicked', async () => {
      const handleSelectChange = vi.fn();
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} selected={false} onSelectChange={handleSelectChange} />);

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(handleSelectChange).toHaveBeenCalledWith('alert-1', true);
    });

    it('does not display checkbox when selected prop is not provided', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper article role for semantic HTML', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByRole('article')).toBeInTheDocument();
    });

    it('action buttons have accessible labels', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByRole('button', { name: /acknowledge/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /view event/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /more options/i })).toBeInTheDocument();
    });
  });
});
