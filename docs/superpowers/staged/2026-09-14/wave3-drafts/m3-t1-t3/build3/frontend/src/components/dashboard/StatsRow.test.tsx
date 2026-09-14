import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import StatsRow from './StatsRow';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Helper to render with router
const renderWithRouter = (props = {}) => {
  const defaultProps = {
    activeCameras: 5,
    eventsToday: 12,
    currentRiskScore: 45,
    systemStatus: 'healthy' as const,
  };

  return render(
    <MemoryRouter>
      <StatsRow {...defaultProps} {...props} />
    </MemoryRouter>
  );
};

describe('StatsRow', () => {
  const defaultProps = {
    activeCameras: 5,
    eventsToday: 12,
    currentRiskScore: 45,
    systemStatus: 'healthy' as const,
  };

  beforeEach(() => {
    mockNavigate.mockClear();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      renderWithRouter();
      expect(screen.getByRole('region', { name: /dashboard statistics/i })).toBeInTheDocument();
    });

    it('renders all four stat cards', () => {
      renderWithRouter();

      // Check for stat labels
      expect(screen.getByText('Active Cameras')).toBeInTheDocument();
      expect(screen.getByText('Events Today')).toBeInTheDocument();
      expect(screen.getByText('System Status')).toBeInTheDocument();

      // Risk label is dynamic based on score
      expect(screen.getByTestId('risk-label')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = renderWithRouter({ className: 'custom-class' });
      const statsRow = container.querySelector('.custom-class');
      expect(statsRow).toBeInTheDocument();
    });
  });

  describe('Active Cameras Display', () => {
    it('displays correct active cameras count', () => {
      renderWithRouter({ activeCameras: 8 });
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('8');
    });

    it('displays zero cameras', () => {
      renderWithRouter({ activeCameras: 0 });
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('0');
    });

    it('displays large camera count', () => {
      renderWithRouter({ activeCameras: 99 });
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('99');
    });
  });

  describe('Events Today Display', () => {
    it('displays correct events today count', () => {
      renderWithRouter({ eventsToday: 25 });
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('25');
    });

    it('displays zero events', () => {
      renderWithRouter({ eventsToday: 0 });
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('0');
    });

    it('displays large event count', () => {
      renderWithRouter({ eventsToday: 150 });
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('150');
    });
  });

  describe('Risk Level Display', () => {
    it('displays low risk correctly', () => {
      renderWithRouter({ currentRiskScore: 15 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('15');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');
    });

    it('displays medium risk correctly', () => {
      renderWithRouter({ currentRiskScore: 45 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('45');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Medium');
    });

    it('displays high risk correctly', () => {
      renderWithRouter({ currentRiskScore: 65 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('65');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('High');
    });

    it('displays critical risk correctly', () => {
      renderWithRouter({ currentRiskScore: 85 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('85');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('displays zero risk score', () => {
      renderWithRouter({ currentRiskScore: 0 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('0');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');
    });

    it('displays maximum risk score', () => {
      renderWithRouter({ currentRiskScore: 100 });
      expect(screen.getByTestId('risk-score')).toHaveTextContent('100');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('displays risk color styling', () => {
      renderWithRouter({ currentRiskScore: 85 });
      const riskLabel = screen.getByTestId('risk-label');
      // Check that color style is applied (critical risk = red)
      expect(riskLabel).toHaveAttribute('style');
      expect(riskLabel.getAttribute('style')).toContain('color');
    });
  });

  describe('System Status Display', () => {
    it('displays healthy status', () => {
      renderWithRouter({ systemStatus: 'healthy' });
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Online');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-green-500');
      expect(indicator).toHaveClass('animate-pulse');
    });

    it('displays degraded status', () => {
      renderWithRouter({ systemStatus: 'degraded' });
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Degraded');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('displays unhealthy status', () => {
      renderWithRouter({ systemStatus: 'unhealthy' });
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Offline');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-red-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('displays unknown status', () => {
      renderWithRouter({ systemStatus: 'unknown' });
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Unknown');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-gray-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('has correct aria-hidden for status indicator dot (decorative)', () => {
      renderWithRouter({ systemStatus: 'healthy' });
      const indicator = screen.getByTestId('status-indicator');
      // The color dot is decorative (aria-hidden), status is conveyed by icon + text
      expect(indicator).toHaveAttribute('aria-hidden', 'true');
    });

    it('renders status icon for accessibility (not color-only)', () => {
      renderWithRouter({ systemStatus: 'healthy' });
      const icon = screen.getByTestId('status-icon');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveAttribute('aria-hidden', 'true');
      // Icon visually conveys status, sr-only text provides screen reader alternative
    });
  });

  describe('Layout and Styling', () => {
    it('has responsive grid layout', () => {
      const { container } = renderWithRouter();
      const grid = container.firstChild;
      expect(grid).toHaveClass('grid');
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('sm:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-4');
    });

    it('has correct dark theme styling', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('.bg-\\[\\#1A1A1A\\]');
      expect(cards.length).toBe(4); // All four stat cards
    });

    it('has proper gap spacing', () => {
      const { container } = renderWithRouter();
      const grid = container.firstChild;
      expect(grid).toHaveClass('gap-4');
    });

    it('cards have borders', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('.border-gray-800');
      expect(cards.length).toBe(4);
    });

    it('cards have shadow', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('.shadow-sm');
      expect(cards.length).toBe(4);
    });
  });

  describe('Icons', () => {
    it('renders all icons', () => {
      const { container } = renderWithRouter();

      // Check for SVG elements (icons are rendered as SVG)
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThanOrEqual(4);
    });

    it('icons have aria-hidden attribute', () => {
      const { container } = renderWithRouter();

      // Icons should be hidden from screen readers
      const hiddenIcons = container.querySelectorAll('[aria-hidden="true"]');
      expect(hiddenIcons.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Accessibility', () => {
    it('has proper region role', () => {
      renderWithRouter();
      expect(screen.getByRole('region')).toBeInTheDocument();
    });

    it('has descriptive aria-label for region', () => {
      renderWithRouter();
      const region = screen.getByRole('region');
      expect(region).toHaveAttribute('aria-label', 'Dashboard statistics');
    });

    it('status indicator uses aria-hidden with icon for visual accessibility', () => {
      renderWithRouter({ systemStatus: 'healthy' });
      const indicator = screen.getByTestId('status-indicator');
      // The color dot is decorative, aria-hidden; status conveyed by icon + text
      expect(indicator).toHaveAttribute('aria-hidden', 'true');
      // Verify the icon is also present for visual accessibility
      const icon = screen.getByTestId('status-icon');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles very large numbers', () => {
      renderWithRouter({
        activeCameras: 9999,
        eventsToday: 10000,
        currentRiskScore: 100,
      });

      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('9999');
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('10000');
      expect(screen.getByTestId('risk-score')).toHaveTextContent('100');
    });

    it('handles all zero values', () => {
      renderWithRouter({
        activeCameras: 0,
        eventsToday: 0,
        currentRiskScore: 0,
        systemStatus: 'unhealthy',
      });

      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('0');
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('0');
      expect(screen.getByTestId('risk-score')).toHaveTextContent('0');
    });
  });

  describe('Integration', () => {
    it('updates when props change', () => {
      const { rerender } = render(
        <MemoryRouter>
          <StatsRow {...defaultProps} activeCameras={5} />
        </MemoryRouter>
      );
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('5');

      rerender(
        <MemoryRouter>
          <StatsRow {...defaultProps} activeCameras={10} />
        </MemoryRouter>
      );
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('10');
    });

    it('updates risk level when score changes', () => {
      const { rerender } = render(
        <MemoryRouter>
          <StatsRow {...defaultProps} currentRiskScore={15} />
        </MemoryRouter>
      );
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');

      rerender(
        <MemoryRouter>
          <StatsRow {...defaultProps} currentRiskScore={85} />
        </MemoryRouter>
      );
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('updates system status indicator', () => {
      const { rerender } = render(
        <MemoryRouter>
          <StatsRow {...defaultProps} systemStatus="healthy" />
        </MemoryRouter>
      );
      expect(screen.getByTestId('status-indicator')).toHaveClass('bg-green-500');

      rerender(
        <MemoryRouter>
          <StatsRow {...defaultProps} systemStatus="unhealthy" />
        </MemoryRouter>
      );
      expect(screen.getByTestId('status-indicator')).toHaveClass('bg-red-500');
    });
  });

  describe('Visual Consistency', () => {
    it('all stat cards have consistent structure', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('.rounded-lg.border.border-gray-800');

      // Should have 4 cards
      expect(cards.length).toBe(4);

      // Each card should have consistent styling
      cards.forEach((card) => {
        expect(card).toHaveClass('bg-[#1A1A1A]');
        expect(card).toHaveClass('p-4');
        expect(card).toHaveClass('shadow-sm');
      });
    });

    it('all icons have consistent container styling', () => {
      const { container } = renderWithRouter();
      const iconContainers = container.querySelectorAll('.h-12.w-12.rounded-lg');

      // Should have 4 icon containers
      expect(iconContainers.length).toBeGreaterThanOrEqual(4);

      // Each should have size and shape classes
      iconContainers.forEach((iconContainer) => {
        expect(iconContainer).toHaveClass('flex');
        expect(iconContainer).toHaveClass('items-center');
        expect(iconContainer).toHaveClass('justify-center');
      });
    });

    it('all stat values have consistent font styling', () => {
      const { container } = renderWithRouter();
      const statValues = container.querySelectorAll(
        '[data-testid$="-count"], [data-testid="risk-score"]'
      );

      // Should have camera count, events count, and risk score
      expect(statValues.length).toBeGreaterThanOrEqual(3);

      // Each should have bold, large text
      statValues.forEach((value) => {
        expect(value).toHaveClass('text-2xl');
        expect(value).toHaveClass('font-bold');
        expect(value).toHaveClass('text-white');
      });
    });
  });

  describe('Navigation', () => {
    it('cameras card navigates to settings when clicked', () => {
      renderWithRouter();
      const camerasCard = screen.getByTestId('cameras-card');
      fireEvent.click(camerasCard);
      expect(mockNavigate).toHaveBeenCalledWith('/settings');
    });

    it('events card navigates to timeline when clicked', () => {
      renderWithRouter();
      const eventsCard = screen.getByTestId('events-card');
      fireEvent.click(eventsCard);
      expect(mockNavigate).toHaveBeenCalledWith('/timeline');
    });

    it('risk card navigates to alerts when clicked', () => {
      renderWithRouter();
      const riskCard = screen.getByTestId('risk-card');
      fireEvent.click(riskCard);
      expect(mockNavigate).toHaveBeenCalledWith('/alerts');
    });

    it('system card navigates to operations page when clicked', () => {
      renderWithRouter();
      const systemCard = screen.getByTestId('system-card');
      fireEvent.click(systemCard);
      expect(mockNavigate).toHaveBeenCalledWith('/operations');
    });

    it('all cards are rendered as buttons', () => {
      renderWithRouter();
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBe(4);
    });

    it('cameras card has correct aria-label', () => {
      renderWithRouter({ activeCameras: 5 });
      const camerasCard = screen.getByTestId('cameras-card');
      expect(camerasCard).toHaveAttribute(
        'aria-label',
        'Active cameras: 5. Click to view camera settings.'
      );
    });

    it('events card has correct aria-label', () => {
      renderWithRouter({ eventsToday: 12 });
      const eventsCard = screen.getByTestId('events-card');
      expect(eventsCard).toHaveAttribute(
        'aria-label',
        'Events today: 12. Click to view event timeline.'
      );
    });

    it('risk card has correct aria-label', () => {
      renderWithRouter({ currentRiskScore: 45 });
      const riskCard = screen.getByTestId('risk-card');
      expect(riskCard).toHaveAttribute(
        'aria-label',
        'Current risk: Medium (45). Click to view alerts.'
      );
    });

    it('system card has correct aria-label', () => {
      renderWithRouter({ systemStatus: 'healthy' });
      const systemCard = screen.getByTestId('system-card');
      expect(systemCard).toHaveAttribute(
        'aria-label',
        'System status: Online. Click to view system monitoring.'
      );
    });
  });

  describe('Hover States', () => {
    it('cards have hover transition classes', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('button[data-testid$="-card"]');

      cards.forEach((card) => {
        expect(card).toHaveClass('transition-all');
        expect(card).toHaveClass('duration-200');
      });
    });

    it('cards have cursor-pointer class', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('button[data-testid$="-card"]');

      cards.forEach((card) => {
        expect(card).toHaveClass('cursor-pointer');
      });
    });

    it('cards have focus ring styles for accessibility', () => {
      const { container } = renderWithRouter();
      const cards = container.querySelectorAll('button[data-testid$="-card"]');

      cards.forEach((card) => {
        expect(card).toHaveClass('focus:outline-none');
        expect(card).toHaveClass('focus:ring-2');
      });
    });

    it('cameras card has green hover border', () => {
      renderWithRouter();
      const camerasCard = screen.getByTestId('cameras-card');
      expect(camerasCard).toHaveClass('hover:border-[#76B900]/50');
    });

    it('events card has blue hover border', () => {
      renderWithRouter();
      const eventsCard = screen.getByTestId('events-card');
      expect(eventsCard).toHaveClass('hover:border-blue-500/50');
    });
  });

  describe('Risk History Sparkline', () => {
    it('renders sparkline when riskHistory has more than one entry', () => {
      const history = [10, 20, 30, 40, 50];
      renderWithRouter({ riskHistory: history });
      expect(screen.getByTestId('risk-sparkline')).toBeInTheDocument();
    });

    it('does not render sparkline when riskHistory is not provided', () => {
      renderWithRouter();
      expect(screen.queryByTestId('risk-sparkline')).not.toBeInTheDocument();
    });

    it('does not render sparkline when riskHistory is empty', () => {
      renderWithRouter({ riskHistory: [] });
      expect(screen.queryByTestId('risk-sparkline')).not.toBeInTheDocument();
    });

    it('does not render sparkline when riskHistory has only one entry', () => {
      renderWithRouter({ riskHistory: [50] });
      expect(screen.queryByTestId('risk-sparkline')).not.toBeInTheDocument();
    });

    it('renders sparkline with two entries', () => {
      const history = [20, 80];
      renderWithRouter({ riskHistory: history });
      expect(screen.getByTestId('risk-sparkline')).toBeInTheDocument();
    });

    it('sparkline has correct SVG structure', () => {
      const history = [10, 30, 50, 70, 90];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      expect(sparkline).toHaveAttribute('width', '60');
      expect(sparkline).toHaveAttribute('height', '24');
      expect(sparkline).toHaveAttribute('viewBox', '0 0 60 24');

      // Should have two path elements (filled area and line)
      const paths = sparkline.querySelectorAll('path');
      expect(paths.length).toBe(2);
    });

    it('sparkline paths have correct attributes', () => {
      const history = [10, 30, 50, 70, 90];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');

      // First path is filled area
      expect(paths[0]).toHaveAttribute('stroke', 'none');
      expect(paths[0].getAttribute('fill')).toBeTruthy();

      // Second path is the line
      expect(paths[1]).toHaveAttribute('fill', 'none');
      expect(paths[1].getAttribute('stroke')).toBeTruthy();
      expect(paths[1]).toHaveAttribute('stroke-width', '1.5');
      expect(paths[1]).toHaveAttribute('stroke-linecap', 'round');
      expect(paths[1]).toHaveAttribute('stroke-linejoin', 'round');
    });

    it('sparkline color matches risk level color', () => {
      // Low risk (green)
      const { rerender } = render(
        <MemoryRouter>
          <StatsRow
            activeCameras={5}
            eventsToday={12}
            currentRiskScore={20}
            systemStatus="healthy"
            riskHistory={[10, 20, 30]}
          />
        </MemoryRouter>
      );

      let sparkline = screen.getByTestId('risk-sparkline');
      let linePath = sparkline.querySelectorAll('path')[1];
      expect(linePath.getAttribute('stroke')).toBe('#22c55e'); // NVIDIA green

      // Critical risk (red)
      rerender(
        <MemoryRouter>
          <StatsRow
            activeCameras={5}
            eventsToday={12}
            currentRiskScore={90}
            systemStatus="healthy"
            riskHistory={[80, 85, 90]}
          />
        </MemoryRouter>
      );

      sparkline = screen.getByTestId('risk-sparkline');
      linePath = sparkline.querySelectorAll('path')[1];
      expect(linePath.getAttribute('stroke')).toBe('#ef4444'); // red-500
    });

    it('sparkline is hidden from accessibility tree', () => {
      renderWithRouter({ riskHistory: [10, 20, 30] });
      const sparkline = screen.getByTestId('risk-sparkline');
      expect(sparkline).toHaveAttribute('aria-hidden', 'true');
    });

    it('handles history with same values (division by zero protection)', () => {
      const history = [50, 50, 50, 50];
      renderWithRouter({ riskHistory: history });

      // Should render without errors
      expect(screen.getByTestId('risk-sparkline')).toBeInTheDocument();

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');
      expect(paths.length).toBe(2);
    });

    it('handles history with extreme values', () => {
      const history = [-50, 0, 50, 100, 150];
      renderWithRouter({ riskHistory: history });

      // Should render without errors
      expect(screen.getByTestId('risk-sparkline')).toBeInTheDocument();
    });

    it('updates sparkline when riskHistory changes', () => {
      const { rerender } = render(
        <MemoryRouter>
          <StatsRow
            activeCameras={5}
            eventsToday={12}
            currentRiskScore={45}
            systemStatus="healthy"
            riskHistory={[10, 20, 30]}
          />
        </MemoryRouter>
      );

      expect(screen.getByTestId('risk-sparkline')).toBeInTheDocument();

      // Change to single value (should hide sparkline)
      rerender(
        <MemoryRouter>
          <StatsRow
            activeCameras={5}
            eventsToday={12}
            currentRiskScore={45}
            systemStatus="healthy"
            riskHistory={[50]}
          />
        </MemoryRouter>
      );

      expect(screen.queryByTestId('risk-sparkline')).not.toBeInTheDocument();
    });

    it('generates correct path with ascending values', () => {
      const history = [0, 25, 50, 75, 100];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');

      // Line path should contain M (move) and L (line) commands
      const linePathD = paths[1].getAttribute('d') || '';
      expect(linePathD).toMatch(/^M /);
      expect(linePathD).toContain(' L ');
    });

    it('generates correct path with descending values', () => {
      const history = [100, 75, 50, 25, 0];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');

      // Line path should contain M and L commands
      const linePathD = paths[1].getAttribute('d') || '';
      expect(linePathD).toMatch(/^M /);
      expect(linePathD).toContain(' L ');
    });

    it('filled area path closes correctly', () => {
      const history = [10, 30, 50, 70, 90];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');

      // First path (filled area) should end with Z
      const filledPathD = paths[0].getAttribute('d') || '';
      expect(filledPathD).toContain(' Z');
    });

    it('line path does not close', () => {
      const history = [10, 30, 50, 70, 90];
      renderWithRouter({ riskHistory: history });

      const sparkline = screen.getByTestId('risk-sparkline');
      const paths = sparkline.querySelectorAll('path');

      // Second path (line) should NOT end with Z
      const linePathD = paths[1].getAttribute('d') || '';
      expect(linePathD).not.toMatch(/Z$/);
    });
  });
});
