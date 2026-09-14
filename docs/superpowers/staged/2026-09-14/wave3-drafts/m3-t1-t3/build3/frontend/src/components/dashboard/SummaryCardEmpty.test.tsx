import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { SummaryCardEmpty } from './SummaryCardEmpty';

describe('SummaryCardEmpty', () => {
  describe('rendering', () => {
    it('renders empty state container with correct test id for hourly', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const container = screen.getByTestId('summary-card-empty-hourly');
      expect(container).toBeInTheDocument();
    });

    it('renders empty state container with correct test id for daily', () => {
      render(<SummaryCardEmpty type="daily" />);
      const container = screen.getByTestId('summary-card-empty-daily');
      expect(container).toBeInTheDocument();
    });

    it('renders "Hourly Summary" title for hourly type', () => {
      render(<SummaryCardEmpty type="hourly" />);
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
    });

    it('renders "Daily Summary" title for daily type', () => {
      render(<SummaryCardEmpty type="daily" />);
      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
    });

    it('renders "No activity to summarize" message', () => {
      render(<SummaryCardEmpty type="hourly" />);
      expect(screen.getByText('No activity to summarize')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders clock icon for hourly type in header', () => {
      const { container } = render(<SummaryCardEmpty type="hourly" />);
      const clockIcons = container.querySelectorAll('svg.lucide-clock');
      // One in header, one in empty state content
      expect(clockIcons.length).toBe(2);
    });

    it('renders calendar icon for daily type in header', () => {
      const { container } = render(<SummaryCardEmpty type="daily" />);
      const calendarIcons = container.querySelectorAll('svg.lucide-calendar');
      // One in header, one in empty state content
      expect(calendarIcons.length).toBe(2);
    });

    it('header icon has aria-hidden attribute', () => {
      const { container } = render(<SummaryCardEmpty type="hourly" />);
      const icons = container.querySelectorAll('svg.lucide-clock');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  describe('timeframe messaging', () => {
    it('shows "the past hour" for hourly type', () => {
      render(<SummaryCardEmpty type="hourly" />);
      expect(
        screen.getByText('No high-priority events detected the past hour.')
      ).toBeInTheDocument();
    });

    it('shows "today" for daily type', () => {
      render(<SummaryCardEmpty type="daily" />);
      expect(screen.getByText('No high-priority events detected today.')).toBeInTheDocument();
    });
  });

  describe('view events button', () => {
    it('does not render button when onViewEvents is not provided', () => {
      render(<SummaryCardEmpty type="hourly" />);
      expect(screen.queryByText('View All Events')).not.toBeInTheDocument();
    });

    it('renders button when onViewEvents is provided', () => {
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="hourly" onViewEvents={handleViewEvents} />);
      expect(screen.getByText('View All Events')).toBeInTheDocument();
    });

    it('button has correct test id for hourly', () => {
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="hourly" onViewEvents={handleViewEvents} />);
      const button = screen.getByTestId('summary-card-empty-view-events-hourly');
      expect(button).toBeInTheDocument();
    });

    it('button has correct test id for daily', () => {
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="daily" onViewEvents={handleViewEvents} />);
      const button = screen.getByTestId('summary-card-empty-view-events-daily');
      expect(button).toBeInTheDocument();
    });

    it('calls onViewEvents when button is clicked', async () => {
      const user = userEvent.setup();
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="hourly" onViewEvents={handleViewEvents} />);

      const button = screen.getByText('View All Events');
      await user.click(button);

      expect(handleViewEvents).toHaveBeenCalledTimes(1);
    });

    it('button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="hourly" onViewEvents={handleViewEvents} />);

      const button = screen.getByText('View All Events');
      button.focus();
      await user.keyboard('{Enter}');

      expect(handleViewEvents).toHaveBeenCalledTimes(1);
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const container = screen.getByTestId('summary-card-empty-hourly');
      expect(container).toHaveClass('bg-[#1A1A1A]');
    });

    it('applies gray-500 border for empty state', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const container = screen.getByTestId('summary-card-empty-hourly');
      // gray-500 RGB value
      expect(container).toHaveStyle({ borderLeftColor: 'rgb(107, 114, 128)' });
    });

    it('applies border-l-4 class', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const container = screen.getByTestId('summary-card-empty-hourly');
      expect(container).toHaveClass('border-l-4');
    });

    it('applies custom className when provided', () => {
      render(<SummaryCardEmpty type="hourly" className="custom-class" />);
      const container = screen.getByTestId('summary-card-empty-hourly');
      expect(container).toHaveClass('custom-class');
    });

    it('button has NVIDIA green text color', () => {
      const handleViewEvents = vi.fn();
      render(<SummaryCardEmpty type="hourly" onViewEvents={handleViewEvents} />);
      const button = screen.getByText('View All Events');
      expect(button).toHaveClass('text-[#76B900]');
    });
  });

  describe('content structure', () => {
    it('includes content container with correct test id', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const content = screen.getByTestId('summary-card-empty-content-hourly');
      expect(content).toBeInTheDocument();
    });

    it('content is centered', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const content = screen.getByTestId('summary-card-empty-content-hourly');
      expect(content).toHaveClass('text-center');
      expect(content).toHaveClass('items-center');
    });

    it('includes icon container in content area', () => {
      render(<SummaryCardEmpty type="hourly" />);
      const content = screen.getByTestId('summary-card-empty-content-hourly');
      const iconContainer = content.querySelector('.rounded-full.bg-gray-800');
      expect(iconContainer).toBeInTheDocument();
    });
  });
});
