/**
 * Tests for CommandPalette component
 *
 * This component provides a cmd+k style command palette for quick navigation
 * and actions using the cmdk library.
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, beforeAll, afterAll } from 'vitest';

import CommandPalette from './CommandPalette';
import { renderWithNavigation } from '../../test-utils';

// Mock scrollIntoView for cmdk library
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterAll(() => {
  vi.restoreAllMocks();
});

// Wrapper component with shared navigation fixture
function renderWithRouter(ui: React.ReactElement, mode: 'easy' | 'advanced' = 'easy') {
  return renderWithNavigation(ui, { useMemoryRouter: false, mode });
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders nothing when closed', () => {
      renderWithRouter(<CommandPalette open={false} onOpenChange={() => {}} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders dialog when open', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders search input when open', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      expect(screen.getByPlaceholderText(/search|type/i)).toBeInTheDocument();
    });

    it('renders navigation items', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      // Check for some navigation items
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Timeline')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });
  });

  describe('search functionality', () => {
    it('filters items based on search input', async () => {
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const input = screen.getByPlaceholderText(/search|type/i);
      await user.type(input, 'dash');

      // Dashboard should be visible, others might be filtered out
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    it('finds items by exact name match - settings', async () => {
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const input = screen.getByPlaceholderText(/search|type/i);
      await user.clear(input);
      await user.type(input, 'settings');

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });
    });

    it('finds items by keyword - cameras', async () => {
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const input = screen.getByPlaceholderText(/search|type/i);
      await user.clear(input);
      await user.type(input, 'cameras');

      await waitFor(() => {
        // Dashboard has "cameras" as a keyword now
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });
    });

    it('performs case-insensitive search', async () => {
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const input = screen.getByPlaceholderText(/search|type/i);
      await user.clear(input);
      await user.type(input, 'SETTINGS');

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });
    });

    it('shows empty state when no results match', async () => {
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const input = screen.getByPlaceholderText(/search|type/i);
      await user.type(input, 'xyznonexistent');

      await waitFor(() => {
        expect(screen.getByText(/no results/i)).toBeInTheDocument();
      });
    });
  });

  describe('navigation', () => {
    it('calls onOpenChange(false) when item is selected', async () => {
      const onOpenChange = vi.fn();
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={onOpenChange} />);

      const dashboardItem = screen.getByText('Dashboard');
      await user.click(dashboardItem);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('keyboard interaction', () => {
    it('closes on Escape key', async () => {
      const onOpenChange = vi.fn();
      const user = userEvent.setup();
      renderWithRouter(<CommandPalette open={true} onOpenChange={onOpenChange} />);

      await user.keyboard('{Escape}');

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('groups', () => {
    it('displays navigation group', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      expect(screen.getByText(/navigation/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible dialog role', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('focuses search input when opened', async () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      await waitFor(() => {
        const input = screen.getByPlaceholderText(/search|type/i);
        expect(document.activeElement).toBe(input);
      });
    });
  });

  describe('shortcuts display', () => {
    it('shows keyboard shortcuts for items', () => {
      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />);

      // Check for shortcut indicators (e.g., "g d" for dashboard)
      expect(screen.getByText('g d')).toBeInTheDocument();
    });
  });

  describe('Easy vs Advanced mode items (F4.9)', () => {
    it('shows Easy hubs/tabs and Switch to Advanced in Easy mode, and includes Advanced hubs/tabs and Switch to Easy in Advanced mode', () => {
      const { unmount } = renderWithRouter(
        <CommandPalette open={true} onOpenChange={() => {}} />,
        'easy'
      );
      expect(screen.getByText('Switch to Advanced')).toBeInTheDocument();
      expect(screen.queryByText('AI Audit')).not.toBeInTheDocument();
      expect(screen.queryByText('Entities')).not.toBeInTheDocument();
      unmount();

      renderWithRouter(<CommandPalette open={true} onOpenChange={() => {}} />, 'advanced');
      expect(screen.getByText('Switch to Easy')).toBeInTheDocument();
      expect(screen.getByText('AI Audit')).toBeInTheDocument();
      expect(screen.getByText('Entities')).toBeInTheDocument();
      expect(screen.getByText('Operations')).toBeInTheDocument();
    });
  });
});
