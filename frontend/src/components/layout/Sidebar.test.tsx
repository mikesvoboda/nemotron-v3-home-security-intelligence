import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Sidebar from './Sidebar';

describe('Sidebar', () => {
  const mockOnNavChange = vi.fn();

  beforeEach(() => {
    mockOnNavChange.mockClear();
  });

  it('renders without crashing', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('renders all navigation items', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Entities')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('highlights the active navigation item', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const dashboardButton = screen.getByRole('button', { name: /dashboard/i });
    expect(dashboardButton).toHaveClass('bg-[#76B900]', 'text-black', 'font-semibold');
  });

  it('does not highlight inactive navigation items', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const timelineButton = screen.getByRole('button', { name: /timeline/i });
    expect(timelineButton).toHaveClass('text-gray-300');
    expect(timelineButton).not.toHaveClass('bg-[#76B900]');
  });

  it('calls onNavChange when navigation item is clicked', async () => {
    const user = userEvent.setup();
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);

    const timelineButton = screen.getByRole('button', { name: /timeline/i });
    await user.click(timelineButton);

    expect(mockOnNavChange).toHaveBeenCalledWith('timeline');
    expect(mockOnNavChange).toHaveBeenCalledTimes(1);
  });

  it('calls onNavChange with correct id for each navigation item', async () => {
    const user = userEvent.setup();
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);

    await user.click(screen.getByRole('button', { name: /settings/i }));
    expect(mockOnNavChange).toHaveBeenCalledWith('settings');

    await user.click(screen.getByRole('button', { name: /alerts/i }));
    expect(mockOnNavChange).toHaveBeenCalledWith('alerts');
  });

  it('displays WIP badge on Entities item', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    expect(screen.getByText('WIP')).toBeInTheDocument();
  });

  it('WIP badge has correct styling', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const wipBadge = screen.getByText('WIP');
    expect(wipBadge).toHaveClass(
      'px-2',
      'py-0.5',
      'text-xs',
      'font-medium',
      'bg-yellow-500',
      'text-black',
      'rounded'
    );
  });

  it('renders icons for all navigation items', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const buttons = screen.getAllByRole('button');

    // Each button should have an icon (lucide-react icons render as SVG)
    buttons.forEach((button) => {
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  it('has correct sidebar styling', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const sidebar = screen.getByRole('complementary');
    expect(sidebar).toHaveClass('w-64', 'bg-[#1A1A1A]', 'border-r', 'border-gray-800');
  });

  it('navigation buttons have full width', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const buttons = screen.getAllByRole('button');

    buttons.forEach((button) => {
      expect(button).toHaveClass('w-full');
    });
  });

  it('changes active state when different nav is selected', () => {
    const { rerender } = render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);

    let dashboardButton = screen.getByRole('button', { name: /dashboard/i });
    expect(dashboardButton).toHaveClass('bg-[#76B900]');

    rerender(<Sidebar activeNav="timeline" onNavChange={mockOnNavChange} />);

    dashboardButton = screen.getByRole('button', { name: /dashboard/i });
    const timelineButton = screen.getByRole('button', { name: /timeline/i });

    expect(dashboardButton).not.toHaveClass('bg-[#76B900]');
    expect(timelineButton).toHaveClass('bg-[#76B900]');
  });

  it('renders all 5 navigation items', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(5);
  });

  it('navigation items have transition classes for smooth hover', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const buttons = screen.getAllByRole('button');

    buttons.forEach((button) => {
      expect(button).toHaveClass('transition-colors', 'duration-200');
    });
  });

  it('inactive items have hover classes', () => {
    render(<Sidebar activeNav="dashboard" onNavChange={mockOnNavChange} />);
    const timelineButton = screen.getByRole('button', { name: /timeline/i });
    expect(timelineButton).toHaveClass('hover:bg-gray-800', 'hover:text-white');
  });
});
