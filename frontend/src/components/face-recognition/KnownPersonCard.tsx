/**
 * KnownPersonCard - Display card for a known person in the face recognition grid
 *
 * Features:
 * - Displays person avatar (placeholder icon)
 * - Shows person name with truncation for long names
 * - Embedding count badge with visual feedback
 * - Household member badge when applicable
 * - Click handler for selection
 * - Optional context menu for edit/delete actions
 * - Hover state with NVIDIA green highlight
 * - Full keyboard accessibility
 *
 * @module components/face-recognition/KnownPersonCard
 * @see NEM-4688 Phase 1 - Known Persons Management
 */

import { Menu, Transition } from '@headlessui/react';
import { Check, Home, MoreVertical, Pencil, Trash2, User, AlertTriangle } from 'lucide-react';
import { Fragment, memo, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * KnownPerson type representing a person in the face recognition system.
 * Matches the KnownPersonResponse schema from the API.
 */
export interface KnownPerson {
  id: number;
  name: string;
  is_household_member: boolean;
  embedding_count: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Props for the KnownPersonCard component.
 */
export interface KnownPersonCardProps {
  /** The known person data to display */
  person: KnownPerson;
  /** Callback when the card is clicked/selected */
  onSelect: (person: KnownPerson) => void;
  /** Optional callback for edit action */
  onEdit?: (person: KnownPerson) => void;
  /** Optional callback for delete action */
  onDelete?: (person: KnownPerson) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * KnownPersonCard displays a known person in a card format with avatar,
 * name, embedding count, and optional household badge.
 */
const KnownPersonCard = memo(function KnownPersonCard({
  person,
  onSelect,
  onEdit,
  onDelete,
  className = '',
}: KnownPersonCardProps) {
  const hasContextMenu = !!onEdit || !!onDelete;

  // Handle card click
  const handleClick = useCallback(() => {
    onSelect(person);
  }, [onSelect, person]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onSelect(person);
      }
    },
    [onSelect, person]
  );

  // Handle edit action
  const handleEdit = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onEdit?.(person);
    },
    [onEdit, person]
  );

  // Handle delete action
  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onDelete?.(person);
    },
    [onDelete, person]
  );

  // Stop menu button click from propagating to card
  const handleMenuButtonClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  // Determine embedding badge styling
  const hasEmbeddings = person.embedding_count > 0;
  const embeddingBadgeClass = hasEmbeddings
    ? 'text-green-400'
    : 'text-yellow-400';

  return (
    <div
      data-testid="known-person-card"
      className={`relative rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 cursor-pointer hover:border-[#76B900] transition-colors ${className}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`View known person ${person.name}`}
    >
      {/* Context Menu */}
      {hasContextMenu && (
        <div className="absolute right-2 top-2">
          <Menu as="div" className="relative">
            <Menu.Button
              data-testid="context-menu-button"
              className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
              onClick={handleMenuButtonClick}
              aria-label={`More options for ${person.name}`}
            >
              <MoreVertical className="h-4 w-4" />
            </Menu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-1 w-36 origin-top-right rounded-md bg-[#252525] border border-gray-700 shadow-lg focus:outline-none">
                <div className="py-1">
                  {onEdit && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={handleEdit}
                          className={`${
                            active ? 'bg-gray-700' : ''
                          } flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-300`}
                        >
                          <Pencil className="h-4 w-4" />
                          Edit
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {onDelete && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={handleDelete}
                          className={`${
                            active ? 'bg-gray-700' : ''
                          } flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400`}
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      )}
                    </Menu.Item>
                  )}
                </div>
              </Menu.Items>
            </Transition>
          </Menu>
        </div>
      )}

      {/* Avatar */}
      <div className="flex justify-center mb-3">
        <div
          data-testid="person-avatar"
          className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center"
        >
          <User className="lucide-user h-8 w-8 text-gray-400" />
        </div>
      </div>

      {/* Person Name */}
      <h3
        data-testid="person-name"
        className="text-center text-white font-medium truncate mb-2"
        title={person.name}
      >
        {person.name}
      </h3>

      {/* Badges */}
      <div className="flex flex-col items-center gap-1.5">
        {/* Embedding Count Badge */}
        <div
          data-testid="embedding-count-badge"
          className={`flex items-center gap-1 text-xs ${embeddingBadgeClass}`}
        >
          {hasEmbeddings ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" />
          )}
          <span>
            {person.embedding_count} {person.embedding_count === 1 ? 'face' : 'faces'}
          </span>
        </div>

        {/* Household Badge */}
        {person.is_household_member && (
          <div
            data-testid="household-badge"
            className="flex items-center gap-1 text-xs text-blue-400"
          >
            <Home className="h-3.5 w-3.5" />
            <span>Household</span>
          </div>
        )}
      </div>
    </div>
  );
});

export default KnownPersonCard;
