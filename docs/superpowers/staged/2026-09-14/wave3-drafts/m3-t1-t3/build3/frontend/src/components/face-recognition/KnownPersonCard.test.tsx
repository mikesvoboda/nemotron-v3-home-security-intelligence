/**
 * KnownPersonCard Test Suite
 *
 * Tests for the KnownPersonCard component that displays a known person
 * in the face recognition grid with avatar, name, embedding count, and
 * household member status.
 *
 * @module components/face-recognition/KnownPersonCard.test
 * @see NEM-4688 Phase 1 - Known Persons Management
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import KnownPersonCard from './KnownPersonCard';

import type { KnownPerson } from './KnownPersonCard';

describe('KnownPersonCard', () => {
  // Mock known person data
  const mockPerson: KnownPerson = {
    id: 1,
    name: 'John Smith',
    is_household_member: true,
    embedding_count: 3,
    notes: 'Family member',
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T12:00:00Z',
  };

  const mockPersonWithoutHousehold: KnownPerson = {
    id: 2,
    name: 'Delivery Person',
    is_household_member: false,
    embedding_count: 1,
    notes: null,
    created_at: '2025-01-20T08:00:00Z',
    updated_at: '2025-01-20T08:00:00Z',
  };

  const mockPersonNoEmbeddings: KnownPerson = {
    id: 3,
    name: 'New Person',
    is_household_member: false,
    embedding_count: 0,
    notes: null,
    created_at: '2025-01-25T14:00:00Z',
    updated_at: '2025-01-25T14:00:00Z',
  };

  describe('basic rendering', () => {
    it('renders the component with required props', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByTestId('known-person-card')).toBeInTheDocument();
    });

    it('displays the person name', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    it('displays an avatar placeholder when no thumbnail is available', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByTestId('person-avatar')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      const onSelect = vi.fn();
      const { container } = render(
        <KnownPersonCard person={mockPerson} onSelect={onSelect} className="custom-class" />
      );

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('custom-class');
    });
  });

  describe('embedding count badge', () => {
    it('displays the embedding count with checkmark', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByTestId('embedding-count-badge')).toBeInTheDocument();
      expect(screen.getByText('3 faces')).toBeInTheDocument();
    });

    it('displays singular "face" for count of 1', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPersonWithoutHousehold} onSelect={onSelect} />);

      expect(screen.getByText('1 face')).toBeInTheDocument();
    });

    it('displays "0 faces" for count of 0', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPersonNoEmbeddings} onSelect={onSelect} />);

      expect(screen.getByText('0 faces')).toBeInTheDocument();
    });

    it('shows success styling when embedding count is greater than 0', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const badge = screen.getByTestId('embedding-count-badge');
      expect(badge).toHaveClass('text-green-400');
    });

    it('shows warning styling when embedding count is 0', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPersonNoEmbeddings} onSelect={onSelect} />);

      const badge = screen.getByTestId('embedding-count-badge');
      expect(badge).toHaveClass('text-yellow-400');
    });
  });

  describe('household member badge', () => {
    it('displays household badge when is_household_member is true', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByTestId('household-badge')).toBeInTheDocument();
      expect(screen.getByText('Household')).toBeInTheDocument();
    });

    it('does not display household badge when is_household_member is false', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPersonWithoutHousehold} onSelect={onSelect} />);

      expect(screen.queryByTestId('household-badge')).not.toBeInTheDocument();
    });
  });

  describe('click interactions', () => {
    it('calls onSelect when card is clicked', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = screen.getByTestId('known-person-card');
      await user.click(card);

      expect(onSelect).toHaveBeenCalledWith(mockPerson);
      expect(onSelect).toHaveBeenCalledTimes(1);
    });

    it('applies cursor-pointer style', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('cursor-pointer');
    });

    it('has role="button" for accessibility', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('supports keyboard navigation with Enter', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard('{Enter}');

      expect(onSelect).toHaveBeenCalledWith(mockPerson);
    });

    it('supports keyboard navigation with Space', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard(' ');

      expect(onSelect).toHaveBeenCalledWith(mockPerson);
    });
  });

  describe('hover state', () => {
    it('applies hover border style class', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('hover:border-[#76B900]');
    });

    it('has transition class for smooth hover effect', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('transition-colors');
    });
  });

  describe('context menu (edit/delete)', () => {
    it('renders menu button when onEdit or onDelete is provided', () => {
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onEdit={onEdit} />);

      expect(screen.getByTestId('context-menu-button')).toBeInTheDocument();
    });

    it('does not render menu button when neither onEdit nor onDelete is provided', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      expect(screen.queryByTestId('context-menu-button')).not.toBeInTheDocument();
    });

    it('shows menu options when menu button is clicked', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      const onDelete = vi.fn();
      render(
        <KnownPersonCard
          person={mockPerson}
          onSelect={onSelect}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      );

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('calls onEdit when Edit option is clicked', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onEdit={onEdit} />);

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      const editButton = screen.getByText('Edit');
      await user.click(editButton);

      expect(onEdit).toHaveBeenCalledWith(mockPerson);
      expect(onSelect).not.toHaveBeenCalled();
    });

    it('calls onDelete when Delete option is clicked', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onDelete = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onDelete={onDelete} />);

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      const deleteButton = screen.getByText('Delete');
      await user.click(deleteButton);

      expect(onDelete).toHaveBeenCalledWith(mockPerson);
      expect(onSelect).not.toHaveBeenCalled();
    });

    it('menu button click does not trigger card onSelect', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onEdit={onEdit} />);

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      expect(onSelect).not.toHaveBeenCalled();
    });

    it('shows only Edit when onDelete is not provided', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onEdit={onEdit} />);

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.queryByText('Delete')).not.toBeInTheDocument();
    });

    it('shows only Delete when onEdit is not provided', async () => {
      const user = userEvent.setup();
      const onSelect = vi.fn();
      const onDelete = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onDelete={onDelete} />);

      const menuButton = screen.getByTestId('context-menu-button');
      await user.click(menuButton);

      expect(screen.queryByText('Edit')).not.toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('bg-[#1A1A1A]');
    });

    it('applies rounded corners', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('rounded-lg');
    });

    it('applies border styling', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border', 'border-gray-700');
    });

    it('applies padding', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('p-4');
    });
  });

  describe('avatar', () => {
    it('displays a circular avatar container', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const avatar = screen.getByTestId('person-avatar');
      expect(avatar).toHaveClass('rounded-full');
    });

    it('displays User icon in avatar', () => {
      const onSelect = vi.fn();
      const { container } = render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      // lucide-react adds lucide-user class to User icons
      const userIcon = container.querySelector('svg.lucide-user');
      expect(userIcon).toBeInTheDocument();
    });

    it('avatar has gray background', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const avatar = screen.getByTestId('person-avatar');
      expect(avatar).toHaveClass('bg-gray-700');
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria-label', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = screen.getByRole('button');
      expect(card).toHaveAttribute('aria-label', expect.stringContaining('John Smith'));
    });

    it('has tabIndex=0 for keyboard navigation', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} />);

      const card = screen.getByRole('button');
      expect(card).toHaveAttribute('tabIndex', '0');
    });

    it('menu button has aria-label', () => {
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<KnownPersonCard person={mockPerson} onSelect={onSelect} onEdit={onEdit} />);

      const menuButton = screen.getByTestId('context-menu-button');
      expect(menuButton).toHaveAttribute('aria-label', expect.stringContaining('options'));
    });
  });

  describe('edge cases', () => {
    it('handles very long person names with truncation', () => {
      const onSelect = vi.fn();
      const longNamePerson: KnownPerson = {
        ...mockPerson,
        name: 'This Is A Very Long Person Name That Should Be Truncated Properly',
      };
      render(<KnownPersonCard person={longNamePerson} onSelect={onSelect} />);

      const nameElement = screen.getByTestId('person-name');
      expect(nameElement).toHaveClass('truncate');
    });

    it('handles person with null notes', () => {
      const onSelect = vi.fn();
      render(<KnownPersonCard person={mockPersonWithoutHousehold} onSelect={onSelect} />);

      expect(screen.getByTestId('known-person-card')).toBeInTheDocument();
    });

    it('handles high embedding count', () => {
      const onSelect = vi.fn();
      const highCountPerson: KnownPerson = {
        ...mockPerson,
        embedding_count: 100,
      };
      render(<KnownPersonCard person={highCountPerson} onSelect={onSelect} />);

      expect(screen.getByText('100 faces')).toBeInTheDocument();
    });
  });
});
