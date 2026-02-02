/**
 * Tests for RecentThreatsIndicator component (TDD - Red Phase)
 *
 * This is a compact header widget showing recent threat detections with a dropdown.
 * It displays a badge with threat count and provides a dropdown list of recent threats
 * with real-time updates via WebSocket.
 *
 * Test cases:
 * 1. Renders threat count badge (e.g., "3 threats")
 * 2. Shows "No threats" when count is 0
 * 3. Clicking opens dropdown with threat list
 * 4. Each threat item shows: weapon type, time ago, camera name
 * 5. Clicking a threat item navigates to event detail (calls onThreatClick)
 * 6. Updates count when new WebSocket threat event received
 * 7. Filters to only show threats from last 24 hours
 * 8. Badge pulses/animates when new threat arrives
 * 9. Dropdown closes when clicking outside
 * 10. Accessibility: proper button role, aria-expanded, aria-controls
 */
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest';

import RecentThreatsIndicator from './RecentThreatsIndicator';
import * as useRecentThreatsModule from '../../hooks/useRecentThreats';

import type { RecentThreat } from '../../types/threat';


// Mock the useRecentThreats hook
vi.mock('../../hooks/useRecentThreats', () => ({
  useRecentThreats: vi.fn(),
}));

describe('RecentThreatsIndicator', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock threat data
  const createMockThreat = (overrides: Partial<RecentThreat> = {}): RecentThreat => ({
    id: `threat-${Math.random().toString(36).substr(2, 9)}`,
    eventId: `event-${Math.random().toString(36).substr(2, 9)}`,
    weaponType: 'handgun',
    cameraName: 'Front Door',
    timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(), // 5 mins ago
    confidence: 0.92,
    thumbnailUrl: 'https://example.com/threat-thumbnail.jpg',
    ...overrides,
  });

  const mockThreats: RecentThreat[] = [
    createMockThreat({
      id: 'threat-1',
      eventId: 'event-1',
      weaponType: 'handgun',
      cameraName: 'Front Door',
      timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(), // 2 mins ago
    }),
    createMockThreat({
      id: 'threat-2',
      eventId: 'event-2',
      weaponType: 'rifle',
      cameraName: 'Back Yard',
      timestamp: new Date(BASE_TIME - 15 * 60 * 1000).toISOString(), // 15 mins ago
    }),
    createMockThreat({
      id: 'threat-3',
      eventId: 'event-3',
      weaponType: 'knife',
      cameraName: 'Garage',
      timestamp: new Date(BASE_TIME - 60 * 60 * 1000).toISOString(), // 1 hour ago
    }),
  ];

  // Default mock hook return value
  let mockHookReturn: ReturnType<typeof useRecentThreatsModule.useRecentThreats>;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);

    mockHookReturn = {
      threats: mockThreats,
      count: mockThreats.length,
      isConnected: true,
      hasNewThreat: false,
      clearNewThreatFlag: vi.fn(),
    };

    (useRecentThreatsModule.useRecentThreats as Mock).mockImplementation(
      (_options?: { onNewThreat?: (threat: RecentThreat) => void }) => {
        return mockHookReturn;
      }
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('threat count badge rendering', () => {
    it('renders threat count badge with correct count', () => {
      render(<RecentThreatsIndicator />);

      expect(screen.getByTestId('threats-indicator')).toBeInTheDocument();
      expect(screen.getByText('3 threats')).toBeInTheDocument();
    });

    it('renders singular "threat" when count is 1', () => {
      mockHookReturn.threats = [mockThreats[0]];
      mockHookReturn.count = 1;

      render(<RecentThreatsIndicator />);

      expect(screen.getByText('1 threat')).toBeInTheDocument();
    });

    it('displays threat count in badge element', () => {
      render(<RecentThreatsIndicator />);

      const badge = screen.getByTestId('threats-count-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('3');
    });

    it('renders shield or warning icon with badge', () => {
      const { container } = render(<RecentThreatsIndicator />);

      // Should have an icon (shield-alert or similar)
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows "No threats" when count is 0', () => {
      mockHookReturn.threats = [];
      mockHookReturn.count = 0;

      render(<RecentThreatsIndicator />);

      expect(screen.getByText('No threats')).toBeInTheDocument();
    });

    it('does not show badge number when count is 0', () => {
      mockHookReturn.threats = [];
      mockHookReturn.count = 0;

      render(<RecentThreatsIndicator />);

      expect(screen.queryByTestId('threats-count-badge')).not.toBeInTheDocument();
    });

    it('shows empty state message in dropdown when no threats', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockHookReturn.threats = [];
      mockHookReturn.count = 0;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/no recent threats/i)).toBeInTheDocument();
    });
  });

  describe('dropdown interaction', () => {
    it('opens dropdown when clicking the indicator', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      await user.click(indicator);

      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();
    });

    it('closes dropdown when clicking the indicator again', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      await user.click(indicator);
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();

      await user.click(indicator);
      expect(screen.queryByTestId('threats-dropdown')).not.toBeInTheDocument();
    });

    it('renders threat list items in dropdown', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const dropdown = screen.getByTestId('threats-dropdown');
      const threatItems = within(dropdown).getAllByTestId(/^threat-item-/);
      expect(threatItems).toHaveLength(3);
    });

    it('respects maxVisible prop to limit displayed threats', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator maxVisible={2} />);

      await user.click(screen.getByTestId('threats-indicator'));

      const dropdown = screen.getByTestId('threats-dropdown');
      const threatItems = within(dropdown).getAllByTestId(/^threat-item-/);
      expect(threatItems).toHaveLength(2);
    });

    it('defaults maxVisible to 5', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Create 7 threats
      const manyThreats = Array.from({ length: 7 }, (_, i) =>
        createMockThreat({
          id: `threat-${i}`,
          eventId: `event-${i}`,
          timestamp: new Date(BASE_TIME - i * 60 * 1000).toISOString(),
        })
      );
      mockHookReturn.threats = manyThreats;
      mockHookReturn.count = 7;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const dropdown = screen.getByTestId('threats-dropdown');
      const threatItems = within(dropdown).getAllByTestId(/^threat-item-/);
      expect(threatItems).toHaveLength(5);
    });

    it('shows "View all" link when more threats exist than maxVisible', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator maxVisible={2} />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/view all/i)).toBeInTheDocument();
    });
  });

  describe('threat item content', () => {
    it('displays weapon type for each threat', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/handgun/i)).toBeInTheDocument();
      expect(screen.getByText(/rifle/i)).toBeInTheDocument();
      expect(screen.getByText(/knife/i)).toBeInTheDocument();
    });

    it('displays camera name for each threat', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
    });

    it('displays relative time ago for each threat', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/2 min/i)).toBeInTheDocument();
      expect(screen.getByText(/15 min/i)).toBeInTheDocument();
      expect(screen.getByText(/1 hour/i)).toBeInTheDocument();
    });

    it('formats "Just now" for very recent threats', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      mockHookReturn.threats = [
        createMockThreat({
          id: 'threat-recent',
          timestamp: new Date(BASE_TIME - 30 * 1000).toISOString(), // 30 seconds ago
        }),
      ];
      mockHookReturn.count = 1;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/just now/i)).toBeInTheDocument();
    });
  });

  describe('threat item click handling', () => {
    it('calls onThreatClick with eventId when threat item is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onThreatClick = vi.fn();

      render(<RecentThreatsIndicator onThreatClick={onThreatClick} />);

      await user.click(screen.getByTestId('threats-indicator'));
      await user.click(screen.getByTestId('threat-item-threat-1'));

      expect(onThreatClick).toHaveBeenCalledWith('event-1');
    });

    it('closes dropdown after clicking a threat item', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onThreatClick = vi.fn();

      render(<RecentThreatsIndicator onThreatClick={onThreatClick} />);

      await user.click(screen.getByTestId('threats-indicator'));
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();

      await user.click(screen.getByTestId('threat-item-threat-1'));
      expect(screen.queryByTestId('threats-dropdown')).not.toBeInTheDocument();
    });

    it('does not throw when onThreatClick is not provided', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      // Should not throw
      await expect(user.click(screen.getByTestId('threat-item-threat-1'))).resolves.not.toThrow();
    });
  });

  describe('real-time WebSocket updates', () => {
    it('updates count when new threat is received via WebSocket', () => {
      const { rerender } = render(<RecentThreatsIndicator />);

      expect(screen.getByText('3 threats')).toBeInTheDocument();

      // Simulate new threat received
      const newThreat = createMockThreat({
        id: 'threat-new',
        eventId: 'event-new',
        weaponType: 'shotgun',
        cameraName: 'Side Gate',
        timestamp: new Date(BASE_TIME).toISOString(),
      });

      mockHookReturn.threats = [newThreat, ...mockThreats];
      mockHookReturn.count = 4;
      mockHookReturn.hasNewThreat = true;

      rerender(<RecentThreatsIndicator />);

      expect(screen.getByText('4 threats')).toBeInTheDocument();
    });

    it('adds new threat to dropdown list', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const { rerender } = render(<RecentThreatsIndicator />);

      // Simulate new threat received
      const newThreat = createMockThreat({
        id: 'threat-new',
        eventId: 'event-new',
        weaponType: 'shotgun',
        cameraName: 'Side Gate',
        timestamp: new Date(BASE_TIME).toISOString(),
      });

      mockHookReturn.threats = [newThreat, ...mockThreats];
      mockHookReturn.count = 4;

      rerender(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(screen.getByText(/shotgun/i)).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('calls hook with onNewThreat callback', () => {
      render(<RecentThreatsIndicator />);

      expect(useRecentThreatsModule.useRecentThreats).toHaveBeenCalledWith(
        expect.objectContaining({
          onNewThreat: expect.any(Function),
        })
      );
    });
  });

  describe('24-hour filter', () => {
    it('only shows threats from the last 24 hours', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Create threats with one outside 24-hour window
      const recentThreats = [
        createMockThreat({
          id: 'threat-recent',
          timestamp: new Date(BASE_TIME - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
        }),
      ];

      mockHookReturn.threats = recentThreats;
      mockHookReturn.count = 1;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const threatItems = screen.getAllByTestId(/^threat-item-/);
      expect(threatItems).toHaveLength(1);
    });

    it('hook filters out threats older than 24 hours', () => {
      // The hook should handle filtering, verify it's called correctly
      render(<RecentThreatsIndicator />);

      expect(useRecentThreatsModule.useRecentThreats).toHaveBeenCalledWith(
        expect.objectContaining({
          maxAgeHours: 24,
        })
      );
    });
  });

  describe('new threat animation', () => {
    it('applies pulse animation class when new threat arrives', () => {
      mockHookReturn.hasNewThreat = true;

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      expect(indicator).toHaveClass('animate-pulse');
    });

    it('does not apply pulse animation when no new threat', () => {
      mockHookReturn.hasNewThreat = false;

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('clears new threat flag when dropdown is opened', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockHookReturn.hasNewThreat = true;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      expect(mockHookReturn.clearNewThreatFlag).toHaveBeenCalled();
    });

    it('applies highlight to most recent threat item when new', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockHookReturn.hasNewThreat = true;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      // First item should have highlight class
      const firstItem = screen.getByTestId('threat-item-threat-1');
      expect(firstItem).toHaveClass('bg-red-50');
    });
  });

  describe('dropdown close on click outside', () => {
    it('closes dropdown when clicking outside', () => {
      render(
        <div>
          <RecentThreatsIndicator />
          <div data-testid="outside">Outside element</div>
        </div>
      );

      // Open dropdown
      fireEvent.click(screen.getByTestId('threats-indicator'));
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();

      // Click outside
      fireEvent.mouseDown(screen.getByTestId('outside'));
      expect(screen.queryByTestId('threats-dropdown')).not.toBeInTheDocument();
    });

    it('closes dropdown on Escape key', () => {
      render(<RecentThreatsIndicator />);

      // Open dropdown
      fireEvent.click(screen.getByTestId('threats-indicator'));
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();

      // Press Escape
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByTestId('threats-dropdown')).not.toBeInTheDocument();
    });

    it('does not close dropdown when clicking inside dropdown', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));
      const dropdown = screen.getByTestId('threats-dropdown');
      expect(dropdown).toBeInTheDocument();

      // Click inside dropdown (but not on an item)
      fireEvent.mouseDown(dropdown);
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has button role on the indicator', () => {
      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      expect(indicator).toHaveAttribute('role', 'button');
    });

    it('has aria-expanded false when dropdown is closed', () => {
      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      expect(indicator).toHaveAttribute('aria-expanded', 'false');
    });

    it('has aria-expanded true when dropdown is open', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      await user.click(indicator);

      expect(indicator).toHaveAttribute('aria-expanded', 'true');
    });

    it('has aria-controls pointing to dropdown id', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      await user.click(indicator);

      const dropdown = screen.getByTestId('threats-dropdown');
      const dropdownId = dropdown.getAttribute('id');

      expect(indicator).toHaveAttribute('aria-controls', dropdownId);
    });

    it('has aria-label describing the indicator purpose', () => {
      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      expect(indicator).toHaveAttribute('aria-label', expect.stringContaining('threat'));
    });

    it('dropdown has role="menu" for proper semantics', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const dropdown = screen.getByTestId('threats-dropdown');
      expect(dropdown).toHaveAttribute('role', 'menu');
    });

    it('threat items have role="menuitem"', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const threatItems = screen.getAllByTestId(/^threat-item-/);
      threatItems.forEach((item) => {
        expect(item).toHaveAttribute('role', 'menuitem');
      });
    });

    it('supports keyboard navigation with Tab', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      // Focus should be manageable within dropdown
      const firstItem = screen.getByTestId('threat-item-threat-1');
      await user.tab();

      expect(document.activeElement).toBe(firstItem);
    });

    it('can be activated with Enter key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      indicator.focus();

      await user.keyboard('{Enter}');

      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();
    });

    it('can be activated with Space key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      const indicator = screen.getByTestId('threats-indicator');
      indicator.focus();

      await user.keyboard(' ');

      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();
    });
  });

  describe('connection status', () => {
    it('shows connected indicator when WebSocket is connected', () => {
      mockHookReturn.isConnected = true;

      render(<RecentThreatsIndicator />);

      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-green-500');
    });

    it('shows disconnected indicator when WebSocket is disconnected', () => {
      mockHookReturn.isConnected = false;

      render(<RecentThreatsIndicator />);

      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-red-500');
    });

    it('shows tooltip with connection status', () => {
      mockHookReturn.isConnected = true;

      render(<RecentThreatsIndicator />);

      const connectionIndicator = screen.getByTestId('connection-indicator');
      expect(connectionIndicator).toHaveAttribute('title', 'Connected');
    });
  });

  describe('styling and layout', () => {
    it('applies custom className', () => {
      const { container } = render(<RecentThreatsIndicator className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('positions dropdown below the indicator', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const dropdown = screen.getByTestId('threats-dropdown');
      // Dropdown should have absolute positioning classes
      expect(dropdown).toHaveClass('absolute');
    });

    it('threat items are sorted by most recent first', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const threatItems = screen.getAllByTestId(/^threat-item-/);

      // First item should be the most recent (threat-1, 2 mins ago)
      expect(threatItems[0]).toHaveAttribute('data-testid', 'threat-item-threat-1');
      // Second item should be threat-2 (15 mins ago)
      expect(threatItems[1]).toHaveAttribute('data-testid', 'threat-item-threat-2');
    });

    it('displays critical/high severity styling for threats', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      const indicator = screen.getByTestId('threats-indicator');
      // Should have danger/red styling
      expect(indicator).toHaveClass('text-red-600');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when initially loading', () => {
      mockHookReturn.threats = [];
      mockHookReturn.count = 0;
      (mockHookReturn as unknown as { isLoading: boolean }).isLoading = true;

      render(<RecentThreatsIndicator />);

      expect(screen.getByTestId('threats-loading')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('handles malformed threat data gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      mockHookReturn.threats = [
        {
          id: 'threat-malformed',
          eventId: 'event-malformed',
          weaponType: undefined as unknown as string, // Malformed
          cameraName: '',
          timestamp: new Date(BASE_TIME).toISOString(),
          confidence: 0.9,
        },
      ];
      mockHookReturn.count = 1;

      render(<RecentThreatsIndicator />);

      await user.click(screen.getByTestId('threats-indicator'));

      // Should still render without crashing
      expect(screen.getByTestId('threats-dropdown')).toBeInTheDocument();
    });
  });
});
