/**
 * Tests for AddPersonModal component
 *
 * TDD Phase: RED - These tests define the expected behavior for the AddPersonModal.
 * Task: NEM-4688 Phase 1 - Create Add/Edit Person Modal
 *
 * This test suite covers:
 * - Modal rendering and visibility
 * - Form fields and validation
 * - Add mode behavior
 * - Edit mode behavior
 * - Form submission and mutations
 * - Toast notifications
 * - Accessibility requirements
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AddPersonModal from './AddPersonModal';
import { renderWithProviders } from '../../test/utils';

import type { KnownPerson } from '../../types/faceRecognition';

// ============================================================================
// Mocks
// ============================================================================

// Mock useToast hook
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock useKnownPersonsApi hooks
const mockCreateKnownPerson = vi.fn();
const mockUpdateKnownPerson = vi.fn();
const mockCreateKnownPersonMutation = {
  mutateAsync: mockCreateKnownPerson,
  isPending: false,
  isError: false,
  error: null,
};
const mockUpdateKnownPersonMutation = {
  mutateAsync: mockUpdateKnownPerson,
  isPending: false,
  isError: false,
  error: null,
};

vi.mock('../../hooks/useKnownPersonsApi', () => ({
  useCreateKnownPerson: () => mockCreateKnownPersonMutation,
  useUpdateKnownPerson: () => mockUpdateKnownPersonMutation,
}));

// ============================================================================
// Test Data
// ============================================================================

const mockPerson: KnownPerson = {
  id: 1,
  name: 'John Doe',
  is_household_member: true,
  notes: 'Test notes',
  created_at: '2025-01-31T12:00:00Z',
  updated_at: '2025-01-31T12:00:00Z',
  embedding_count: 2,
  household_member_id: null,
};

// ============================================================================
// Tests
// ============================================================================

describe('AddPersonModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateKnownPersonMutation.isPending = false;
    mockUpdateKnownPersonMutation.isPending = false;
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the modal when isOpen is true', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render the modal when isOpen is false', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('displays "Add Person" title in add mode', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByRole('heading', { name: /Add Person/i })).toBeInTheDocument();
    });

    it('displays "Edit Person" title in edit mode', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} editPerson={mockPerson} />);
      expect(screen.getByRole('heading', { name: /Edit Person/i })).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Form Fields Tests
  // ==========================================================================

  describe('form fields', () => {
    it('renders name input field', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByLabelText(/Name/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Enter name/i)).toBeInTheDocument();
    });

    it('renders is household member checkbox', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByLabelText(/Household Member/i)).toBeInTheDocument();
      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('renders notes textarea', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByLabelText(/Notes/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Optional notes/i)).toBeInTheDocument();
    });

    it('renders Save and Cancel buttons', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: /Save/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('populates fields with editPerson data', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} editPerson={mockPerson} />);

      expect(screen.getByLabelText(/Name/i)).toHaveValue('John Doe');
      expect(screen.getByRole('checkbox')).toBeChecked();
      expect(screen.getByLabelText(/Notes/i)).toHaveValue('Test notes');
    });

    it('has empty fields in add mode', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      expect(screen.getByLabelText(/Name/i)).toHaveValue('');
      expect(screen.getByRole('checkbox')).not.toBeChecked();
      expect(screen.getByLabelText(/Notes/i)).toHaveValue('');
    });
  });

  // ==========================================================================
  // Form Validation Tests
  // ==========================================================================

  describe('form validation', () => {
    it('shows error message when name is empty on submit', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(screen.getByText(/Name is required/i)).toBeInTheDocument();
      });
    });

    it('does not call mutation when validation fails', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockCreateKnownPerson).not.toHaveBeenCalled();
      });
    });

    it('clears error when user starts typing in name field', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      // Trigger validation error
      await user.click(screen.getByRole('button', { name: /Save/i }));
      await waitFor(() => {
        expect(screen.getByText(/Name is required/i)).toBeInTheDocument();
      });

      // Start typing
      await user.type(screen.getByLabelText(/Name/i), 'J');

      await waitFor(() => {
        expect(screen.queryByText(/Name is required/i)).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Add Mode Tests
  // ==========================================================================

  describe('add mode', () => {
    it('calls createKnownPerson mutation on successful submit', async () => {
      const user = userEvent.setup();
      mockCreateKnownPerson.mockResolvedValueOnce({ id: 1, name: 'Jane Doe' });

      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.type(screen.getByLabelText(/Name/i), 'Jane Doe');
      await user.click(screen.getByRole('checkbox'));
      await user.type(screen.getByLabelText(/Notes/i), 'Some notes');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockCreateKnownPerson).toHaveBeenCalledWith({
          name: 'Jane Doe',
          is_household_member: true,
          notes: 'Some notes',
        });
      });
    });

    it('shows success toast and closes modal on successful creation', async () => {
      const user = userEvent.setup();
      mockCreateKnownPerson.mockResolvedValueOnce({ id: 1, name: 'Jane Doe' });

      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.type(screen.getByLabelText(/Name/i), 'Jane Doe');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith('Person created successfully');
        expect(defaultProps.onClose).toHaveBeenCalled();
      });
    });

    it('shows error toast on creation failure', async () => {
      const user = userEvent.setup();
      mockCreateKnownPerson.mockRejectedValueOnce(new Error('Failed to create person'));

      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.type(screen.getByLabelText(/Name/i), 'Jane Doe');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to create person');
        expect(defaultProps.onClose).not.toHaveBeenCalled();
      });
    });
  });

  // ==========================================================================
  // Edit Mode Tests
  // ==========================================================================

  describe('edit mode', () => {
    it('calls updateKnownPerson mutation on successful submit', async () => {
      const user = userEvent.setup();
      mockUpdateKnownPerson.mockResolvedValueOnce({ ...mockPerson, name: 'John Smith' });

      renderWithProviders(<AddPersonModal {...defaultProps} editPerson={mockPerson} />);

      await user.clear(screen.getByLabelText(/Name/i));
      await user.type(screen.getByLabelText(/Name/i), 'John Smith');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockUpdateKnownPerson).toHaveBeenCalledWith({
          id: mockPerson.id,
          data: {
            name: 'John Smith',
            is_household_member: true,
            notes: 'Test notes',
          },
        });
      });
    });

    it('shows success toast and closes modal on successful update', async () => {
      const user = userEvent.setup();
      mockUpdateKnownPerson.mockResolvedValueOnce({ ...mockPerson, name: 'John Smith' });

      renderWithProviders(<AddPersonModal {...defaultProps} editPerson={mockPerson} />);

      await user.clear(screen.getByLabelText(/Name/i));
      await user.type(screen.getByLabelText(/Name/i), 'John Smith');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith('Person updated successfully');
        expect(defaultProps.onClose).toHaveBeenCalled();
      });
    });

    it('shows error toast on update failure', async () => {
      const user = userEvent.setup();
      mockUpdateKnownPerson.mockRejectedValueOnce(new Error('Failed to update person'));

      renderWithProviders(<AddPersonModal {...defaultProps} editPerson={mockPerson} />);

      await user.clear(screen.getByLabelText(/Name/i));
      await user.type(screen.getByLabelText(/Name/i), 'John Smith');
      await user.click(screen.getByRole('button', { name: /Save/i }));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to update person');
        expect(defaultProps.onClose).not.toHaveBeenCalled();
      });
    });
  });

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('loading state', () => {
    it('disables Save button when saving', () => {
      mockCreateKnownPersonMutation.isPending = true;
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /Saving/i })).toBeDisabled();
    });

    it('disables Cancel button when saving', () => {
      mockCreateKnownPersonMutation.isPending = true;
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    });

    it('shows "Saving..." text when saving', () => {
      mockCreateKnownPersonMutation.isPending = true;
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      expect(screen.getByText(/Saving/i)).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Cancel and Close Tests
  // ==========================================================================

  describe('cancel and close', () => {
    it('calls onClose when Cancel button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(defaultProps.onClose).toHaveBeenCalled();
    });

    it('calls onClose when modal backdrop is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AddPersonModal {...defaultProps} />);

      // Click outside the modal content (on the backdrop)
      const dialog = screen.getByRole('dialog');
      const backdrop = dialog.parentElement;
      if (backdrop) {
        await user.click(backdrop);
      }

      // Headless UI Dialog calls onClose when clicking outside
      expect(defaultProps.onClose).toHaveBeenCalled();
    });

    it('resets form when modal is reopened', async () => {
      const user = userEvent.setup();
      const { rerender } = renderWithProviders(<AddPersonModal {...defaultProps} />);

      // Enter some data
      await user.type(screen.getByLabelText(/Name/i), 'Test Name');
      await user.click(screen.getByRole('checkbox'));

      // Close the modal
      rerender(<AddPersonModal {...defaultProps} isOpen={false} />);

      // Reopen the modal
      rerender(<AddPersonModal {...defaultProps} isOpen={true} />);

      // Form should be reset
      expect(screen.getByLabelText(/Name/i)).toHaveValue('');
      expect(screen.getByRole('checkbox')).not.toBeChecked();
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has proper dialog role', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has associated label for name input', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const nameInput = screen.getByLabelText(/Name/i);
      expect(nameInput).toHaveAttribute('id');
    });

    it('has associated label for checkbox', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const checkbox = screen.getByLabelText(/Household Member/i);
      expect(checkbox).toHaveAttribute('id');
    });

    it('has associated label for notes textarea', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const notesInput = screen.getByLabelText(/Notes/i);
      expect(notesInput).toHaveAttribute('id');
    });

    it('focuses the name input when modal opens', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const nameInput = screen.getByLabelText(/Name/i);
      expect(nameInput).toHaveFocus();
    });

    it('has proper form structure', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      // The form element has an implicit role of 'form'
      const dialog = screen.getByRole('dialog');
      const form = dialog.querySelector('form');
      expect(form).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Styling Tests
  // ==========================================================================

  describe('styling', () => {
    it('has dark theme styling on inputs', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const nameInput = screen.getByLabelText(/Name/i);
      expect(nameInput.className).toContain('bg-[#121212]');
      expect(nameInput.className).toContain('border-gray-700');
    });

    it('has NVIDIA green accent on Save button', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const saveButton = screen.getByRole('button', { name: /Save/i });
      expect(saveButton.className).toContain('bg-[#76B900]');
    });

    it('has proper modal background styling', () => {
      renderWithProviders(<AddPersonModal {...defaultProps} />);
      const dialogPanel = screen.getByRole('dialog').querySelector('[class*="bg-[#1A1A1A]"]');
      expect(dialogPanel).toBeInTheDocument();
    });
  });
});
