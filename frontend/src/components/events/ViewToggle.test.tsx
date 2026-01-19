import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ViewToggle from './ViewToggle';

describe('ViewToggle', () => {
  // Mock localStorage
  const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: vi.fn((key: string) => store[key] || null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      clear: () => {
        store = {};
      },
    };
  })();

  beforeEach(() => {
    localStorageMock.clear();
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders grid and list toggle buttons', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      expect(screen.getByRole('button', { name: /grid view/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /list view/i })).toBeInTheDocument();
    });

    it('renders with grid icon', () => {
      const handleChange = vi.fn();
      const { container } = render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const gridIcon = container.querySelector('svg.lucide-grid-2x2');
      expect(gridIcon).toBeInTheDocument();
    });

    it('renders with list icon', () => {
      const handleChange = vi.fn();
      const { container } = render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const listIcon = container.querySelector('svg.lucide-list');
      expect(listIcon).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const handleChange = vi.fn();
      const { container } = render(
        <ViewToggle viewMode="grid" onChange={handleChange} className="custom-class" />
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('custom-class');
    });
  });

  describe('active state', () => {
    it('shows grid button as active when viewMode is grid', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      const listButton = screen.getByRole('button', { name: /list view/i });

      expect(gridButton).toHaveClass('bg-[#76B900]');
      expect(gridButton).toHaveClass('text-black');
      expect(listButton).not.toHaveClass('bg-[#76B900]');
    });

    it('shows list button as active when viewMode is list', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="list" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      const listButton = screen.getByRole('button', { name: /list view/i });

      expect(listButton).toHaveClass('bg-[#76B900]');
      expect(listButton).toHaveClass('text-black');
      expect(gridButton).not.toHaveClass('bg-[#76B900]');
    });

    it('has aria-pressed true for active button', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      const listButton = screen.getByRole('button', { name: /list view/i });

      expect(gridButton).toHaveAttribute('aria-pressed', 'true');
      expect(listButton).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('interaction', () => {
    it('calls onChange with "list" when list button is clicked', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const listButton = screen.getByRole('button', { name: /list view/i });
      await user.click(listButton);

      expect(handleChange).toHaveBeenCalledWith('list');
      expect(handleChange).toHaveBeenCalledTimes(1);
    });

    it('calls onChange with "grid" when grid button is clicked', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="list" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      await user.click(gridButton);

      expect(handleChange).toHaveBeenCalledWith('grid');
      expect(handleChange).toHaveBeenCalledTimes(1);
    });

    it('does not call onChange when clicking already active button', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      await user.click(gridButton);

      expect(handleChange).not.toHaveBeenCalled();
    });
  });

  describe('keyboard navigation', () => {
    it('buttons are focusable via keyboard', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const gridButton = screen.getByRole('button', { name: /grid view/i });
      const listButton = screen.getByRole('button', { name: /list view/i });

      gridButton.focus();
      expect(document.activeElement).toBe(gridButton);

      listButton.focus();
      expect(document.activeElement).toBe(listButton);
    });

    it('activates button on Enter key', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const listButton = screen.getByRole('button', { name: /list view/i });
      listButton.focus();
      await user.keyboard('{Enter}');

      expect(handleChange).toHaveBeenCalledWith('list');
    });

    it('activates button on Space key', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const listButton = screen.getByRole('button', { name: /list view/i });
      listButton.focus();
      await user.keyboard(' ');

      expect(handleChange).toHaveBeenCalledWith('list');
    });
  });

  describe('accessibility', () => {
    it('has appropriate role group', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const group = screen.getByRole('group', { name: /view toggle/i });
      expect(group).toBeInTheDocument();
    });

    it('buttons have descriptive aria-labels', () => {
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      expect(screen.getByLabelText(/switch to grid view/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/switch to list view/i)).toBeInTheDocument();
    });
  });

  describe('localStorage persistence', () => {
    it('saves view preference to localStorage on change', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} persistKey="test-view-mode" />);

      const listButton = screen.getByRole('button', { name: /list view/i });
      await user.click(listButton);

      expect(localStorageMock.setItem).toHaveBeenCalledWith('test-view-mode', '"list"');
    });

    it('does not save to localStorage when persistKey is not provided', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<ViewToggle viewMode="grid" onChange={handleChange} />);

      const listButton = screen.getByRole('button', { name: /list view/i });
      await user.click(listButton);

      expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });
  });
});
