/**
 * Tests for ShortcutsHelpModal component
 *
 * This component displays available keyboard shortcuts when ? is pressed.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ShortcutsHelpModal from './ShortcutsHelpModal';

describe('ShortcutsHelpModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders nothing when closed', () => {
      render(<ShortcutsHelpModal open={false} onClose={() => {}} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders dialog when open', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders title', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      expect(screen.getByRole('heading', { name: /keyboard shortcuts/i })).toBeInTheDocument();
    });
  });

  describe('shortcut groups', () => {
    it('displays global shortcuts section', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      expect(screen.getByRole('heading', { name: /global/i })).toBeInTheDocument();
    });

    it('displays navigation shortcuts section', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      expect(screen.getByRole('heading', { name: /^navigation$/i })).toBeInTheDocument();
    });

    it('displays list navigation shortcuts section', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      // Look for list-related shortcuts
      expect(screen.getByRole('heading', { name: /list navigation/i })).toBeInTheDocument();
    });
  });

  describe('shortcuts content', () => {
    it('displays command palette shortcut', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      // Should show Cmd/Ctrl + K
      expect(screen.getByText(/command palette/i)).toBeInTheDocument();
    });

    it('displays help shortcut', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      // ? appears multiple times (in shortcuts list and footer hint)
      const questionMarks = screen.getAllByText('?');
      expect(questionMarks.length).toBeGreaterThan(0);
    });

    it('displays navigation chord shortcuts', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      // Check for navigation shortcut descriptions
      expect(screen.getByText(/go to dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/go to timeline/i)).toBeInTheDocument();

      // Check for the keys (g appears multiple times, so use getAllByText)
      const gKeys = screen.getAllByText('g');
      expect(gKeys.length).toBeGreaterThan(0);
      expect(screen.getByText('d')).toBeInTheDocument();
      expect(screen.getByText('t')).toBeInTheDocument();
    });

    it('displays j/k navigation shortcuts', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      expect(screen.getByText('j')).toBeInTheDocument();
      expect(screen.getByText('k')).toBeInTheDocument();
    });
  });

  describe('closing', () => {
    it('calls onClose when close button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<ShortcutsHelpModal open={true} onClose={onClose} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when backdrop is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<ShortcutsHelpModal open={true} onClose={onClose} />);

      const backdrop = screen.getByTestId('modal-backdrop');
      await user.click(backdrop);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Escape key is pressed', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<ShortcutsHelpModal open={true} onClose={onClose} />);

      await user.keyboard('{Escape}');

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('accessibility', () => {
    it('has accessible dialog role', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('has aria-modal attribute', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('has proper aria-label', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-label', expect.stringMatching(/shortcuts|keyboard/i));
    });
  });

  describe('focus trap', () => {
    it('traps focus within the modal when open', async () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      // Focus should be within the dialog (may be set asynchronously via requestAnimationFrame)
      const dialog = screen.getByRole('dialog');
      await waitFor(() => {
        expect(dialog.contains(document.activeElement)).toBe(true);
      });
    });

    it('close button is focusable', () => {
      render(<ShortcutsHelpModal open={true} onClose={() => {}} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      closeButton.focus();
      expect(document.activeElement).toBe(closeButton);
    });
  });
});
