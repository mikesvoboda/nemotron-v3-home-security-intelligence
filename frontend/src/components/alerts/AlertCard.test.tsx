import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import AlertCard from './AlertCard';

import type { AlertCardProps } from './AlertCard';

describe('AlertCard', () => {
  const mockAlert: AlertCardProps = {
    id: 'alert-1',
    eventId: 123,
    severity: 'high',
    status: 'pending',
    timestamp: '2024-01-01T10:00:00Z',
    camera_name: 'Front Door',
    risk_score: 75,
    summary: 'Person detected near entrance',
    dedup_key: 'front_door:person',
    onAcknowledge: vi.fn(),
    onDismiss: vi.fn(),
    onSnooze: vi.fn(),
    onViewEvent: vi.fn(),
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

    it('calls onAcknowledge when acknowledge button is clicked', async () => {
      const handleAcknowledge = vi.fn();
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} onAcknowledge={handleAcknowledge} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeBtn);

      expect(handleAcknowledge).toHaveBeenCalledWith('alert-1');
    });

    it('displays dismiss button', () => {
      render(<AlertCard {...mockAlert} />);

      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('calls onDismiss when dismiss button is clicked', async () => {
      const handleDismiss = vi.fn();
      const user = userEvent.setup();

      render(<AlertCard {...mockAlert} onDismiss={handleDismiss} />);

      const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
      await user.click(dismissBtn);

      expect(handleDismiss).toHaveBeenCalledWith('alert-1');
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
