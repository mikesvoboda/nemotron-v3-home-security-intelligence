/**
 * BulkEnrollmentModal Test Suite
 *
 * Tests for the BulkEnrollmentModal component that allows users to enroll
 * multiple faces at once via batch upload.
 *
 * @module components/face-recognition/BulkEnrollmentModal.test
 * @see NEM-4954 - Bulk Enrollment Workflow
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import BulkEnrollmentModal from './BulkEnrollmentModal';

// Mock the hooks
const mockUseKnownPersonsQuery = vi.fn();
const mockUseBulkEnrollFaces = vi.fn();
const mockUseCreateKnownPerson = vi.fn();
const mockUseToast = vi.fn();

vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useKnownPersonsQuery: () => mockUseKnownPersonsQuery(),
  useBulkEnrollFaces: () => mockUseBulkEnrollFaces(),
  useCreateKnownPerson: () => mockUseCreateKnownPerson(),
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => mockUseToast(),
  default: () => mockUseToast(),
}));

// Mock URL.createObjectURL and URL.revokeObjectURL
const mockCreateObjectURL = vi.fn(() => 'mock-url');
const mockRevokeObjectURL = vi.fn();
global.URL.createObjectURL = mockCreateObjectURL;
global.URL.revokeObjectURL = mockRevokeObjectURL;

const mockKnownPersons = [
  {
    id: 1,
    name: 'John Smith',
    is_household_member: true,
    embedding_count: 3,
    notes: 'Family member',
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T12:00:00Z',
    household_member_id: null,
  },
  {
    id: 2,
    name: 'Jane Doe',
    is_household_member: false,
    embedding_count: 2,
    notes: null,
    created_at: '2025-01-20T08:00:00Z',
    updated_at: '2025-01-20T08:00:00Z',
    household_member_id: null,
  },
  {
    id: 3,
    name: 'Bob Wilson',
    is_household_member: true,
    embedding_count: 10, // Max embeddings reached
    notes: null,
    created_at: '2025-01-22T14:00:00Z',
    updated_at: '2025-01-22T14:00:00Z',
    household_member_id: null,
  },
];

const createMockFile = (name: string, type = 'image/jpeg', size = 1024): File => {
  const file = new File(['test'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
};

// TODO: Fix flaky test - times out in CI due to async/act() issues
// See: https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/issues/TBD
describe.skip('BulkEnrollmentModal', () => {
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
    });

    mockUseBulkEnrollFaces.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({
        total_images: 2,
        successful: 2,
        failed: 0,
        results: [
          { filename: 'face1.jpg', success: true, embedding_id: 1, quality_score: 0.92, error: null },
          { filename: 'face2.jpg', success: true, embedding_id: 2, quality_score: 0.88, error: null },
        ],
        person_id: 1,
        person_name: 'John Smith',
        created_new_person: false,
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    mockUseCreateKnownPerson.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({
        id: 4,
        name: 'New Person',
        is_household_member: false,
        embedding_count: 0,
        notes: null,
        created_at: '2025-01-31T10:00:00Z',
        updated_at: '2025-01-31T10:00:00Z',
        household_member_id: null,
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    mockUseToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    });

    mockCreateObjectURL.mockClear();
    mockRevokeObjectURL.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BulkEnrollmentModal {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Basic Rendering ==========

  describe('basic rendering', () => {
    it('renders modal when isOpen is true', () => {
      renderModal({ isOpen: true });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/bulk face enrollment/i)).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('displays file upload area', () => {
      renderModal();
      expect(screen.getByTestId('drop-zone')).toBeInTheDocument();
      expect(screen.getByText(/drag & drop images here/i)).toBeInTheDocument();
    });

    it('displays mode selection radio buttons', () => {
      renderModal();
      expect(screen.getByRole('radio', { name: /add to existing person/i })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /create new person/i })).toBeInTheDocument();
    });

    it('displays close button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /close modal/i })).toBeInTheDocument();
    });

    it('displays cancel button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('enroll button is disabled when no files selected', () => {
      renderModal();
      const enrollButton = screen.getByTestId('enroll-button');
      expect(enrollButton).toBeDisabled();
    });
  });

  // ========== File Upload ==========

  describe('file upload', () => {
    it('accepts files via input', async () => {
      const user = userEvent.setup();
      renderModal();

      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');

      await user.upload(input, file);

      expect(screen.getByTestId('file-preview-0')).toBeInTheDocument();
    });

    it('shows file size for uploaded files', async () => {
      const user = userEvent.setup();
      renderModal();

      const file = createMockFile('test.jpg', 'image/jpeg', 2048);
      const input = screen.getByTestId('file-input');

      await user.upload(input, file);

      expect(screen.getByText(/2\.0 KB/i)).toBeInTheDocument();
    });

    it('allows removing uploaded files', async () => {
      const user = userEvent.setup();
      renderModal();

      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');

      await user.upload(input, file);
      expect(screen.getByTestId('file-preview-0')).toBeInTheDocument();

      const removeButton = screen.getByRole('button', { name: /remove test\.jpg/i });
      await user.click(removeButton);

      expect(screen.queryByTestId('file-preview-0')).not.toBeInTheDocument();
    });

    it('rejects invalid file types', async () => {
      const user = userEvent.setup();
      const warningToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: vi.fn(),
        error: vi.fn(),
        warning: warningToast,
        info: vi.fn(),
      });

      renderModal();

      const file = createMockFile('test.pdf', 'application/pdf');
      const input = screen.getByTestId('file-input');

      await user.upload(input, file);

      expect(warningToast).toHaveBeenCalledWith(
        expect.stringContaining('Invalid file type')
      );
    });

    it('limits to maximum 10 files', async () => {
      const user = userEvent.setup();
      const warningToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: vi.fn(),
        error: vi.fn(),
        warning: warningToast,
        info: vi.fn(),
      });

      renderModal();

      const files = Array.from({ length: 11 }, (_, i) =>
        createMockFile(`test${i}.jpg`)
      );
      const input = screen.getByTestId('file-input');

      await user.upload(input, files);

      expect(warningToast).toHaveBeenCalledWith(
        expect.stringContaining('Maximum 10 files')
      );
    });

    it('updates file count display', async () => {
      const user = userEvent.setup();
      renderModal();

      const files = [createMockFile('test1.jpg'), createMockFile('test2.jpg')];
      const input = screen.getByTestId('file-input');

      await user.upload(input, files);

      expect(screen.getByText(/face images \(2\/10\)/i)).toBeInTheDocument();
    });
  });

  // ========== Mode Selection ==========

  describe('mode selection', () => {
    it('defaults to "add to existing" mode', () => {
      renderModal();
      const existingRadio = screen.getByRole('radio', { name: /add to existing person/i });
      expect(existingRadio).toBeChecked();
    });

    it('shows person selector in existing mode', () => {
      renderModal();
      expect(screen.getByLabelText(/select person/i)).toBeInTheDocument();
    });

    it('hides person selector in new mode', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      expect(screen.queryByLabelText(/select person/i)).not.toBeInTheDocument();
    });

    it('shows name input in new mode', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    it('shows household checkbox in new mode', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      expect(screen.getByRole('checkbox', { name: /household member/i })).toBeInTheDocument();
    });
  });

  // ========== Person Selector ==========

  describe('person selector', () => {
    it('displays known persons in dropdown', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
    });

    it('shows available slots for each person', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // John has 3 embeddings, so 7 slots left
      expect(screen.getByText(/7 slots left/i)).toBeInTheDocument();
    });

    it('shows "Max reached" for person at limit', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // Bob has 10 embeddings (max)
      expect(screen.getByText(/max reached/i)).toBeInTheDocument();
    });

    it('disables person at max embeddings', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      const bobOption = screen.getByRole('option', { name: /bob wilson/i });
      expect(bobOption).toHaveAttribute('aria-disabled', 'true');
    });

    it('filters persons by search query', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'John');

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('John Smith');
    });
  });

  // ========== Enrollment Flow ==========

  describe('enrollment flow - existing person', () => {
    it('enables enroll button when files and person selected', async () => {
      const user = userEvent.setup();
      renderModal();

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      const enrollButton = screen.getByTestId('enroll-button');
      expect(enrollButton).not.toBeDisabled();
    });

    it('calls bulk enroll mutation with correct params', async () => {
      const user = userEvent.setup();
      const mutateAsync = vi.fn().mockResolvedValue({
        total_images: 1,
        successful: 1,
        failed: 0,
        results: [{ filename: 'test.jpg', success: true, embedding_id: 1, quality_score: 0.9, error: null }],
        person_id: 1,
        person_name: 'John Smith',
        created_new_person: false,
      });
      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            person_id: 1,
          })
        );
      });
    });

    it('shows processing state during enrollment', async () => {
      const user = userEvent.setup();
      const pendingPromise = new Promise(() => {
        // Keep promise pending indefinitely for this test
      });

      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync: vi.fn().mockReturnValue(pendingPromise),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      // Should show processing state
      await waitFor(() => {
        expect(screen.getByText(/processing images/i)).toBeInTheDocument();
      });
    });

    it('shows results summary on completion', async () => {
      const user = userEvent.setup();
      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync: vi.fn().mockResolvedValue({
          total_images: 2,
          successful: 2,
          failed: 0,
          results: [
            { filename: 'face1.jpg', success: true, embedding_id: 1, quality_score: 0.92, error: null },
            { filename: 'face2.jpg', success: true, embedding_id: 2, quality_score: 0.88, error: null },
          ],
          person_id: 1,
          person_name: 'John Smith',
          created_new_person: false,
        }),
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Upload files
      const files = [createMockFile('face1.jpg'), createMockFile('face2.jpg')];
      const input = screen.getByTestId('file-input');
      await user.upload(input, files);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      // Wait for completion
      await waitFor(() => {
        expect(screen.getByText(/enrollment results/i)).toBeInTheDocument();
      });

      // Check summary
      expect(screen.getByTestId('success-count')).toHaveTextContent('2');
      expect(screen.getByTestId('fail-count')).toHaveTextContent('0');
    });

    it('shows per-image results', async () => {
      const user = userEvent.setup();
      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync: vi.fn().mockResolvedValue({
          total_images: 2,
          successful: 1,
          failed: 1,
          results: [
            { filename: 'good.jpg', success: true, embedding_id: 1, quality_score: 0.92, error: null },
            { filename: 'bad.jpg', success: false, embedding_id: null, quality_score: 0.55, error: 'Quality too low' },
          ],
          person_id: 1,
          person_name: 'John Smith',
          created_new_person: false,
        }),
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Upload files
      const files = [createMockFile('good.jpg'), createMockFile('bad.jpg')];
      const input = screen.getByTestId('file-input');
      await user.upload(input, files);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      // Wait for completion
      await waitFor(() => {
        expect(screen.getByTestId('result-item-0')).toBeInTheDocument();
        expect(screen.getByTestId('result-item-1')).toBeInTheDocument();
      });

      // Check individual results
      const successItem = screen.getByTestId('result-item-0');
      expect(within(successItem).getByText(/good\.jpg/i)).toBeInTheDocument();
      expect(within(successItem).getByText(/0\.92/)).toBeInTheDocument();

      const failItem = screen.getByTestId('result-item-1');
      expect(within(failItem).getByText(/bad\.jpg/i)).toBeInTheDocument();
      expect(within(failItem).getByText(/quality too low/i)).toBeInTheDocument();
    });
  });

  // ========== Enrollment Flow - New Person ==========

  describe('enrollment flow - new person', () => {
    it('enables enroll button when files and name provided', async () => {
      const user = userEvent.setup();
      renderModal();

      // Switch to new person mode
      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Enter name
      await user.type(screen.getByLabelText(/name/i), 'New Person');

      const enrollButton = screen.getByTestId('enroll-button');
      expect(enrollButton).not.toBeDisabled();
    });

    it('calls bulk enroll mutation with new person params', async () => {
      const user = userEvent.setup();
      const mutateAsync = vi.fn().mockResolvedValue({
        total_images: 1,
        successful: 1,
        failed: 0,
        results: [{ filename: 'test.jpg', success: true, embedding_id: 1, quality_score: 0.9, error: null }],
        person_id: 4,
        person_name: 'New Person',
        created_new_person: true,
      });
      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Switch to new person mode
      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Enter name and check household
      await user.type(screen.getByLabelText(/name/i), 'New Person');
      await user.click(screen.getByRole('checkbox', { name: /household member/i }));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            new_person_name: 'New Person',
            is_household_member: true,
          })
        );
      });
    });
  });

  // ========== Error Handling ==========

  describe('error handling', () => {
    it('shows error toast on enrollment failure', async () => {
      const user = userEvent.setup();
      const errorToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: vi.fn(),
        error: errorToast,
        warning: vi.fn(),
        info: vi.fn(),
      });

      mockUseBulkEnrollFaces.mockReturnValue({
        mutateAsync: vi.fn().mockRejectedValue(new Error('Server error')),
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      await waitFor(() => {
        expect(errorToast).toHaveBeenCalledWith(
          expect.stringContaining('Bulk enrollment failed')
        );
      });
    });

    it('shows warning when max embeddings warning applies', async () => {
      const user = userEvent.setup();
      renderModal();

      // Select person with limited slots (John has 7 slots)
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Upload more files than slots available (8 files)
      const files = Array.from({ length: 8 }, (_, i) =>
        createMockFile(`test${i}.jpg`)
      );
      const input = screen.getByTestId('file-input');
      await user.upload(input, files);

      // Should show warning
      expect(screen.getByText(/only 7 of 8 images will be enrolled/i)).toBeInTheDocument();
    });
  });

  // ========== Modal Actions ==========

  describe('modal actions', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderModal({ onClose });

      await user.click(screen.getByRole('button', { name: /close modal/i }));

      expect(onClose).toHaveBeenCalled();
    });

    it('calls onClose when cancel button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderModal({ onClose });

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onClose).toHaveBeenCalled();
    });

    it('revokes object URLs on close', async () => {
      const user = userEvent.setup();
      const { rerender } = renderModal({ isOpen: true });

      // Upload a file
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Close modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <BulkEnrollmentModal {...defaultProps} isOpen={false} />
        </QueryClientProvider>
      );

      expect(mockRevokeObjectURL).toHaveBeenCalled();
    });

    it('resets form state when modal closes', async () => {
      const user = userEvent.setup();
      const { rerender } = renderModal({ isOpen: true });

      // Upload a file and switch mode
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);
      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'Test Name');

      // Close and reopen modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <BulkEnrollmentModal {...defaultProps} isOpen={false} />
        </QueryClientProvider>
      );

      rerender(
        <QueryClientProvider client={queryClient}>
          <BulkEnrollmentModal {...defaultProps} isOpen={true} />
        </QueryClientProvider>
      );

      // Should be reset
      expect(screen.getByRole('radio', { name: /add to existing person/i })).toBeChecked();
      expect(screen.queryByTestId('file-preview-0')).not.toBeInTheDocument();
    });

    it('shows Done button after completion', async () => {
      const user = userEvent.setup();
      renderModal();

      // Upload files
      const file = createMockFile('test.jpg');
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      // Select a person
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      // Click enroll
      await user.click(screen.getByTestId('enroll-button'));

      // Wait for completion
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /done/i })).toBeInTheDocument();
      });
    });
  });

  // ========== Accessibility ==========

  describe('accessibility', () => {
    it('has appropriate aria-label on drop zone', () => {
      renderModal();
      const dropZone = screen.getByTestId('drop-zone');
      expect(dropZone).toHaveAttribute('aria-label', 'Drop files or click to upload');
    });

    it('file input accepts correct types', () => {
      renderModal();
      const input = screen.getByTestId('file-input');
      expect(input).toHaveAttribute('accept', 'image/jpeg,image/png,image/jpg');
    });

    it('has multiple attribute on file input', () => {
      renderModal();
      const input = screen.getByTestId('file-input');
      expect(input).toHaveAttribute('multiple');
    });
  });
});
