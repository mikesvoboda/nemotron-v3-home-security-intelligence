/**
 * Tests for IdentifyPersonModal component.
 *
 * @module components/face-recognition/IdentifyPersonModal.test
 * @see NEM-4688 Phase 2 - Identify Person Modal
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import IdentifyPersonModal from './IdentifyPersonModal';

// Mock the hooks
const mockUseKnownPersonsQuery = vi.fn();
const mockUseIdentifyFace = vi.fn();

vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useKnownPersonsQuery: () => mockUseKnownPersonsQuery(),
  useIdentifyFace: () => mockUseIdentifyFace(),
}));

// Mock the toast hook
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  loading: vi.fn(),
  dismiss: vi.fn(),
  promise: vi.fn(),
};

vi.mock('../../hooks/useToast', () => ({
  useToast: () => mockToast,
  default: () => mockToast,
}));

// Test data
const mockKnownPersons = [
  {
    id: 1,
    name: 'John Smith',
    is_household_member: true,
    embedding_count: 3,
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-20T10:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Doe',
    is_household_member: true,
    embedding_count: 2,
    created_at: '2025-01-16T10:00:00Z',
    updated_at: '2025-01-21T10:00:00Z',
  },
  {
    id: 3,
    name: 'Bob Wilson',
    is_household_member: false,
    embedding_count: 1,
    created_at: '2025-01-17T10:00:00Z',
    updated_at: '2025-01-22T10:00:00Z',
  },
  {
    id: 4,
    name: 'Alice Johnson',
    is_household_member: true,
    embedding_count: 4,
    created_at: '2025-01-18T10:00:00Z',
    updated_at: '2025-01-23T10:00:00Z',
  },
];

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  eventId: 123,
  facePreviewUrl: '/api/face-events/123/thumbnail',
  qualityScore: 0.82,
  cameraName: 'Front Door',
  timestamp: '2025-01-31T10:28:00Z',
};

describe('IdentifyPersonModal', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Default mock implementations
    mockUseKnownPersonsQuery.mockReturnValue({
      data: mockKnownPersons,
      isLoading: false,
      isError: false,
      error: null,
    });

    mockUseIdentifyFace.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    });

    // Reset toast mocks
    mockToast.success.mockClear();
    mockToast.error.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <IdentifyPersonModal {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Rendering Tests ==========

  describe('Rendering', () => {
    it('renders modal when isOpen is true', () => {
      renderModal();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Identify Person')).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows face preview image', () => {
      renderModal();
      const preview = screen.getByRole('img', { name: /face preview/i });
      expect(preview).toBeInTheDocument();
      expect(preview).toHaveAttribute('src', defaultProps.facePreviewUrl);
    });

    it('shows placeholder when no face preview URL provided', () => {
      renderModal({ facePreviewUrl: undefined });
      const preview = screen.getByRole('img', { name: /face preview/i });
      expect(preview).toHaveAttribute('src', '/placeholder-face.png');
    });

    it('shows camera name', () => {
      renderModal();
      expect(screen.getByText(/front door/i)).toBeInTheDocument();
    });

    it('shows formatted timestamp', () => {
      renderModal();
      // Should display in a readable format
      expect(screen.getByText(/jan 31, 2025/i)).toBeInTheDocument();
    });

    it('shows search input for filtering persons', () => {
      renderModal();
      expect(screen.getByPlaceholderText(/search persons/i)).toBeInTheDocument();
    });

    it('shows grid of known persons', () => {
      renderModal();
      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
    });

    it('shows radio button for each person', () => {
      renderModal();
      const radios = screen.getAllByRole('radio');
      expect(radios).toHaveLength(mockKnownPersons.length);
    });

    it('shows "Also enroll this face" checkbox when quality >= 0.7', () => {
      renderModal({ qualityScore: 0.82 });
      expect(screen.getByRole('checkbox', { name: /also enroll this face/i })).toBeInTheDocument();
    });

    it('does not show enrollment checkbox when quality < 0.7', () => {
      renderModal({ qualityScore: 0.65 });
      expect(screen.queryByRole('checkbox', { name: /also enroll this face/i })).not.toBeInTheDocument();
    });

    it('shows quality score in enrollment checkbox label', () => {
      renderModal({ qualityScore: 0.82 });
      expect(screen.getByText(/quality: 0\.82/i)).toBeInTheDocument();
    });

    it('shows Cancel button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('shows Identify button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /identify/i })).toBeInTheDocument();
    });

    it('disables Identify button when no person selected', () => {
      renderModal();
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      expect(identifyButton).toBeDisabled();
    });
  });

  // ========== Person Selection Tests ==========

  describe('Person Selection', () => {
    it('enables Identify button when a person is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      const identifyButton = screen.getByRole('button', { name: /identify/i });
      expect(identifyButton).not.toBeDisabled();
    });

    it('allows selecting a different person', async () => {
      const user = userEvent.setup();
      renderModal();

      // Select John first
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);
      expect(johnRadio).toBeChecked();

      // Then select Jane
      const janeRadio = screen.getByRole('radio', { name: /jane doe/i });
      await user.click(janeRadio);

      expect(janeRadio).toBeChecked();
      expect(johnRadio).not.toBeChecked();
    });

    it('filters persons when searching', async () => {
      const user = userEvent.setup();
      renderModal();

      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'john');

      // Only John should be visible
      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument(); // Also contains "john"
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
      expect(screen.queryByText('Bob Wilson')).not.toBeInTheDocument();
    });

    it('shows message when no persons match search', async () => {
      const user = userEvent.setup();
      renderModal();

      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'xyz');

      expect(screen.getByText(/no persons found/i)).toBeInTheDocument();
    });

    it('clears search when X button clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'john');

      const clearButton = screen.getByRole('button', { name: /clear search/i });
      await user.click(clearButton);

      expect(searchInput).toHaveValue('');
      // All persons should be visible again
      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
    });
  });

  // ========== Enrollment Checkbox Tests ==========

  describe('Enrollment Checkbox', () => {
    it('checkbox is checked by default when quality >= 0.8', () => {
      renderModal({ qualityScore: 0.85 });
      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      expect(checkbox).toBeChecked();
    });

    it('checkbox is unchecked by default when quality between 0.7 and 0.8', () => {
      renderModal({ qualityScore: 0.75 });
      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      expect(checkbox).not.toBeChecked();
    });

    it('allows toggling enrollment checkbox', async () => {
      const user = userEvent.setup();
      renderModal({ qualityScore: 0.82 });

      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      expect(checkbox).toBeChecked();

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();

      await user.click(checkbox);
      expect(checkbox).toBeChecked();
    });
  });

  // ========== Form Submission Tests ==========

  describe('Form Submission', () => {
    it('calls useIdentifyFace mutation with correct parameters', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ qualityScore: 0.82 });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Check enrollment checkbox (should be checked by default for quality >= 0.8)
      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      expect(checkbox).toBeChecked();

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mutate).toHaveBeenCalledWith(
        {
          eventId: 123,
          knownPersonId: 1,
          createEmbedding: true,
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('does not send createEmbedding when checkbox unchecked', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ qualityScore: 0.82 });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Uncheck enrollment checkbox
      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      await user.click(checkbox);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mutate).toHaveBeenCalledWith(
        {
          eventId: 123,
          knownPersonId: 1,
          createEmbedding: false,
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('does not send createEmbedding when quality < 0.7', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ qualityScore: 0.65 });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify (no checkbox visible)
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mutate).toHaveBeenCalledWith(
        {
          eventId: 123,
          knownPersonId: 1,
          createEmbedding: false,
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('shows loading state during submission', () => {
      mockUseIdentifyFace.mockReturnValue({
        mutate: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();

      expect(screen.getByRole('button', { name: /identifying/i })).toBeDisabled();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('disables all inputs during submission', () => {
      mockUseIdentifyFace.mockReturnValue({
        mutate: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal({ qualityScore: 0.82 });

      const searchInput = screen.getByPlaceholderText(/search persons/i);
      expect(searchInput).toBeDisabled();

      // Custom radio buttons use tabindex=-1 and opacity class for disabled state
      const radios = screen.getAllByRole('radio');
      radios.forEach(radio => {
        expect(radio).toHaveAttribute('tabindex', '-1');
        expect(radio).toHaveClass('opacity-50');
      });

      const checkbox = screen.getByRole('checkbox', { name: /also enroll this face/i });
      expect(checkbox).toBeDisabled();

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton).toBeDisabled();
    });
  });

  // ========== Success Handling Tests ==========

  describe('Success Handling', () => {
    it('shows success toast on successful identification', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onSuccess }) => {
        onSuccess({ success: true, created_embedding: true });
      });
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      const onClose = vi.fn();
      renderModal({ onClose });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mockToast.success).toHaveBeenCalledWith(
        expect.stringContaining('John Smith'),
        expect.any(Object)
      );
    });

    it('closes modal on successful identification', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onSuccess }) => {
        onSuccess({ success: true, created_embedding: false });
      });
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      const onClose = vi.fn();
      renderModal({ onClose });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('includes enrollment info in success message when embedding created', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onSuccess }) => {
        onSuccess({ success: true, created_embedding: true });
      });
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal({ qualityScore: 0.82 });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mockToast.success).toHaveBeenCalledWith(
        expect.stringMatching(/enrolled/i),
        expect.any(Object)
      );
    });
  });

  // ========== Error Handling Tests ==========

  describe('Error Handling', () => {
    it('shows error toast on API failure', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onError }) => {
        onError(new Error('Failed to identify face'));
      });
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(mockToast.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed to identify face'),
        expect.any(Object)
      );
    });

    it('does not close modal on error', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onError }) => {
        onError(new Error('Failed to identify face'));
      });
      mockUseIdentifyFace.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      const onClose = vi.fn();
      renderModal({ onClose });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Click identify
      const identifyButton = screen.getByRole('button', { name: /identify/i });
      await user.click(identifyButton);

      expect(onClose).not.toHaveBeenCalled();
    });

    it('shows error message when known persons fail to load', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load known persons' },
      });

      renderModal();
      expect(screen.getByText(/failed to load known persons/i)).toBeInTheDocument();
    });

    it('shows loading state while fetching known persons', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      });

      renderModal();
      expect(screen.getByText(/loading persons/i)).toBeInTheDocument();
    });

    it('shows empty state when no known persons exist', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      });

      renderModal();
      expect(screen.getByText(/no known persons/i)).toBeInTheDocument();
    });
  });

  // ========== Modal Actions Tests ==========

  describe('Modal Actions', () => {
    it('calls onClose when Cancel button clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderModal({ onClose });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when close button (X) clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderModal({ onClose });

      const closeButton = screen.getByRole('button', { name: /close/i });
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('resets form state when modal is reopened', async () => {
      const user = userEvent.setup();
      const { rerender } = renderModal({ isOpen: true });

      // Select a person
      const johnRadio = screen.getByRole('radio', { name: /john smith/i });
      await user.click(johnRadio);

      // Type in search
      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'john');

      // Close modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <IdentifyPersonModal {...defaultProps} isOpen={false} />
        </QueryClientProvider>
      );

      // Reopen modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <IdentifyPersonModal {...defaultProps} isOpen={true} />
        </QueryClientProvider>
      );

      // Form should be reset
      expect(screen.getByPlaceholderText(/search persons/i)).toHaveValue('');
      const radios = screen.getAllByRole('radio');
      radios.forEach(radio => {
        expect(radio).not.toBeChecked();
      });
    });
  });

  // ========== Accessibility Tests ==========

  describe('Accessibility', () => {
    it('has accessible modal title', () => {
      renderModal();
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');
      expect(screen.getByText('Identify Person')).toBeInTheDocument();
    });

    it('has proper radio group labeling', () => {
      renderModal();
      expect(screen.getByRole('radiogroup', { name: /select matching person/i })).toBeInTheDocument();
    });

    it('each person has radio button with name as label', () => {
      renderModal();
      expect(screen.getByRole('radio', { name: /john smith/i })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /jane doe/i })).toBeInTheDocument();
    });

    it('search input has accessible label', () => {
      renderModal();
      expect(screen.getByLabelText(/search persons/i)).toBeInTheDocument();
    });
  });
});
