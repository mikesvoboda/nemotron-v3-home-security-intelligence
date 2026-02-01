import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import LinkPersonModal from './LinkPersonModal';

// Mock the hooks (they don't exist yet)
const mockUseMembersQuery = vi.fn();
const mockUseLinkDetection = vi.fn();

vi.mock('../../hooks/useHouseholdApi', () => ({
  useMembersQuery: () => mockUseMembersQuery(),
  useLinkDetection: () => mockUseLinkDetection(),
}));

const mockMembers = [
  { id: 1, name: 'Mike', role: 'resident', trusted_level: 'full' },
  { id: 2, name: 'Jane', role: 'family', trusted_level: 'full' },
  { id: 3, name: 'Gardener', role: 'service_worker', trusted_level: 'partial' },
  { id: 4, name: 'Visitor', role: 'frequent_visitor', trusted_level: 'partial' },
];

const mockDetection = {
  id: 123,
  object_type: 'person',
  confidence: 0.95,
  detected_at: '2025-01-31T10:00:00Z',
  thumbnail_url: '/api/detections/123/thumbnail',
};

describe('LinkPersonModal', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Default mock implementations
    mockUseMembersQuery.mockReturnValue({
      data: mockMembers,
      isLoading: false,
      isError: false,
    });

    mockUseLinkDetection.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = (props = {}) => {
    const defaultProps = {
      isOpen: true,
      onClose: vi.fn(),
      detection: mockDetection,
      onSuccess: vi.fn(),
    };

    return render(
      <QueryClientProvider client={queryClient}>
        <LinkPersonModal {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Rendering Tests ==========

  describe('Rendering', () => {
    it('renders modal when isOpen is true', () => {
      renderModal({ isOpen: true });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/link person to household member/i)).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows detection thumbnail', () => {
      renderModal();
      const thumbnail = screen.getByRole('img', { name: /detection thumbnail/i });
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('src', mockDetection.thumbnail_url);
    });

    it('shows member dropdown with household members', () => {
      renderModal();
      const dropdown = screen.getByLabelText(/select household member/i);
      expect(dropdown).toBeInTheDocument();
    });

    it('shows confirm button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /link/i })).toBeInTheDocument();
    });

    it('shows cancel button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('disables confirm button when no member selected', () => {
      renderModal();
      const confirmButton = screen.getByRole('button', { name: /link/i });
      expect(confirmButton).toBeDisabled();
    });

    it('shows detection confidence', () => {
      renderModal();
      expect(screen.getByText(/95%/)).toBeInTheDocument();
    });

    it('shows detection timestamp', () => {
      renderModal();
      expect(screen.getByText(/2025-01-31/)).toBeInTheDocument();
    });

    it('shows notes textarea', () => {
      renderModal();
      expect(screen.getByLabelText(/notes/i)).toBeInTheDocument();
    });
  });

  // ========== Member Filtering Tests ==========

  describe('Member Filtering', () => {
    it('only shows residents and family members in dropdown', async () => {
      renderModal();
      const dropdown = screen.getByLabelText(/select household member/i);

      await userEvent.click(dropdown);

      expect(screen.getByText('Mike')).toBeInTheDocument();
      expect(screen.getByText('Jane')).toBeInTheDocument();
      expect(screen.queryByText('Gardener')).not.toBeInTheDocument();
      expect(screen.queryByText('Visitor')).not.toBeInTheDocument();
    });

    it('filters out service_worker role', async () => {
      renderModal();
      const dropdown = screen.getByLabelText(/select household member/i);

      await userEvent.click(dropdown);

      const serviceWorker = mockMembers.find(m => m.role === 'service_worker');
      expect(screen.queryByText(serviceWorker!.name)).not.toBeInTheDocument();
    });

    it('filters out frequent_visitor role', async () => {
      renderModal();
      const dropdown = screen.getByLabelText(/select household member/i);

      await userEvent.click(dropdown);

      const visitor = mockMembers.find(m => m.role === 'frequent_visitor');
      expect(screen.queryByText(visitor!.name)).not.toBeInTheDocument();
    });

    it('shows empty state when no eligible members', () => {
      mockUseMembersQuery.mockReturnValue({
        data: [{ id: 5, name: 'Worker', role: 'service_worker', trusted_level: 'partial' }],
        isLoading: false,
        isError: false,
      });

      renderModal();
      expect(screen.getByText(/no eligible household members/i)).toBeInTheDocument();
    });
  });

  // ========== Interaction Tests ==========

  describe('Interactions', () => {
    it('enables confirm button when member is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const confirmButton = screen.getByRole('button', { name: /link/i });
      expect(confirmButton).not.toBeDisabled();
    });

    it('calls onClose when cancel button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderModal({ onClose });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls linkDetectionToMember API when confirm is clicked', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseLinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const confirmButton = screen.getByRole('button', { name: /link/i });
      await user.click(confirmButton);

      expect(mutate).toHaveBeenCalledWith(
        {
          detectionId: mockDetection.id,
          memberId: 1,
          notes: '',
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
        })
      );
    });

    it('includes notes in API call when provided', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseLinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const notesInput = screen.getByLabelText(/notes/i);
      await user.type(notesInput, 'Test note');

      const confirmButton = screen.getByRole('button', { name: /link/i });
      await user.click(confirmButton);

      expect(mutate).toHaveBeenCalledWith(
        {
          detectionId: mockDetection.id,
          memberId: 1,
          notes: 'Test note',
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
        })
      );
    });

    it('shows loading state during linking', () => {
      mockUseLinkDetection.mockReturnValue({
        mutate: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();
      expect(screen.getByRole('button', { name: /linking/i })).toBeDisabled();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('disables all inputs during linking', () => {
      mockUseLinkDetection.mockReturnValue({
        mutate: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();
      expect(screen.getByLabelText(/select household member/i)).toBeDisabled();
      expect(screen.getByLabelText(/notes/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('closes modal on successful link', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const onSuccess = vi.fn();
      const mutate = vi.fn((_, { onSuccess: successCallback }) => {
        successCallback({ memberId: 1, memberName: 'Mike' });
      });

      mockUseLinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ onClose, onSuccess });

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const confirmButton = screen.getByRole('button', { name: /link/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(onClose).toHaveBeenCalledTimes(1);
      });
    });

    it('calls onSuccess callback with member details', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      const mutate = vi.fn((_, { onSuccess: successCallback }) => {
        successCallback({ memberId: 1, memberName: 'Mike' });
      });

      mockUseLinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ onSuccess });

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const confirmButton = screen.getByRole('button', { name: /link/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith({ memberId: 1, memberName: 'Mike' });
      });
    });
  });

  // ========== Error Handling Tests ==========

  describe('Error Handling', () => {
    it('shows error message on API failure', () => {
      mockUseLinkDetection.mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isError: true,
        error: { message: 'Failed to link detection' },
      });

      renderModal();
      expect(screen.getByText(/failed to link detection/i)).toBeInTheDocument();
    });

    it('shows generic error when error message is missing', () => {
      mockUseLinkDetection.mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isError: true,
        error: {},
      });

      renderModal();
      expect(screen.getByText(/failed to link person/i)).toBeInTheDocument();
    });

    it('shows loading error for members query', () => {
      mockUseMembersQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load members' },
      });

      renderModal();
      expect(screen.getByText(/failed to load members/i)).toBeInTheDocument();
    });

    it('shows loading state for members query', () => {
      mockUseMembersQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      });

      renderModal();
      expect(screen.getByText(/loading members/i)).toBeInTheDocument();
    });
  });

  // ========== Validation Tests ==========

  describe('Validation', () => {
    it('accepts notes up to 500 characters', async () => {
      const user = userEvent.setup();
      renderModal();

      const notesInput = screen.getByLabelText(/notes/i);
      const longNotes = 'a'.repeat(500);
      await user.type(notesInput, longNotes);

      expect(notesInput).toHaveValue(longNotes);
      expect(screen.queryByText(/notes too long/i)).not.toBeInTheDocument();
    });

    it('shows validation error for notes over 500 characters', async () => {
      const user = userEvent.setup();
      renderModal();

      const notesInput = screen.getByLabelText(/notes/i);
      const tooLongNotes = 'a'.repeat(501);
      await user.type(notesInput, tooLongNotes);

      expect(screen.getByText(/notes must be 500 characters or less/i)).toBeInTheDocument();
    });

    it('disables confirm button when notes are too long', async () => {
      const user = userEvent.setup();
      renderModal();

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      const notesInput = screen.getByLabelText(/notes/i);
      const tooLongNotes = 'a'.repeat(501);
      await user.type(notesInput, tooLongNotes);

      const confirmButton = screen.getByRole('button', { name: /link/i });
      expect(confirmButton).toBeDisabled();
    });

    it('shows character count for notes', async () => {
      const user = userEvent.setup();
      renderModal();

      const notesInput = screen.getByLabelText(/notes/i);
      await user.type(notesInput, 'Test');

      expect(screen.getByText(/4 \/ 500/)).toBeInTheDocument();
    });
  });

  // ========== Edge Cases ==========

  describe('Edge Cases', () => {
    it('handles undefined detection gracefully', () => {
      renderModal({ detection: undefined });
      expect(screen.getByText(/invalid detection/i)).toBeInTheDocument();
    });

    it('handles detection without thumbnail', () => {
      const detectionNoThumbnail = { ...mockDetection, thumbnail_url: null };
      renderModal({ detection: detectionNoThumbnail });

      const thumbnail = screen.getByRole('img', { name: /detection thumbnail/i });
      expect(thumbnail).toHaveAttribute('src', '/placeholder-person.png');
    });

    it('allows member selection to be changed', async () => {
      const user = userEvent.setup();
      renderModal();

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      await user.click(dropdown);
      await user.click(screen.getByText('Jane'));

      expect(screen.getByDisplayValue('Jane')).toBeInTheDocument();
    });

    it('clears form when modal is closed and reopened', async () => {
      const user = userEvent.setup();
      const { rerender } = renderModal({ isOpen: true });

      const dropdown = screen.getByLabelText(/select household member/i);
      await user.click(dropdown);
      await user.click(screen.getByText('Mike'));

      rerender(
        <QueryClientProvider client={queryClient}>
          <LinkPersonModal
            isOpen={false}
            onClose={vi.fn()}
            detection={mockDetection}
            onSuccess={vi.fn()}
          />
        </QueryClientProvider>
      );

      rerender(
        <QueryClientProvider client={queryClient}>
          <LinkPersonModal
            isOpen={true}
            onClose={vi.fn()}
            detection={mockDetection}
            onSuccess={vi.fn()}
          />
        </QueryClientProvider>
      );

      expect(screen.queryByDisplayValue('Mike')).not.toBeInTheDocument();
    });
  });
});
