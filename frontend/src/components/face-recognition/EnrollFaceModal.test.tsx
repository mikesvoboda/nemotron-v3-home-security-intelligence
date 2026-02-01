/**
 * EnrollFaceModal Test Suite
 *
 * Tests for the EnrollFaceModal component that allows users to enroll a face
 * from a detection event to a known person (existing or new).
 *
 * @module components/face-recognition/EnrollFaceModal.test
 * @see NEM-4688 Phase 2 - Face Enrollment Modal
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import EnrollFaceModal from './EnrollFaceModal';

// Mock the hooks
const mockUseKnownPersonsQuery = vi.fn();
const mockUseEnrollFace = vi.fn();
const mockUseCreateKnownPerson = vi.fn();
const mockUseToast = vi.fn();

vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useKnownPersonsQuery: () => mockUseKnownPersonsQuery(),
  useEnrollFace: () => mockUseEnrollFace(),
  useCreateKnownPerson: () => mockUseCreateKnownPerson(),
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => mockUseToast(),
  default: () => mockUseToast(),
}));

// Mock the types - include quality assessment functions needed by FaceQualityAssessment
vi.mock('../../types/faceRecognition', () => ({
  computeQualityFactorsFromScore: (score: number) => ({
    blur: {
      score: score,
      label: 'Sharpness',
      status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
      recommendation: score < 0.8 ? 'Hold camera steady' : undefined,
    },
    lighting: {
      score: score,
      label: 'Lighting',
      status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
      recommendation: score < 0.8 ? 'Improve lighting' : undefined,
    },
    angle: {
      score: score,
      label: 'Face Angle',
      status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
      recommendation: score < 0.8 ? 'Face the camera' : undefined,
    },
    occlusion: {
      score: score,
      label: 'Visibility',
      status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
      recommendation: score < 0.8 ? 'Remove obstructions' : undefined,
    },
  }),
  getQualityStatus: (score: number) => {
    if (score >= 0.8) return 'good';
    if (score >= 0.7) return 'fair';
    return 'poor';
  },
  isQualityEnrollable: (score: number) => score >= 0.7,
  getOverallRecommendation: (score: number) => {
    if (score >= 0.8) return undefined;
    if (score < 0.7) return 'Image quality is too low for enrollment.';
    return 'Recognition accuracy may be reduced.';
  },
}));

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

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  detectionId: 'detection-123',
  facePreviewUrl: '/api/detections/123/face-crop',
  qualityScore: 0.85,
  cameraName: 'Front Door',
  timestamp: '2025-01-31T10:32:00Z',
};

describe('EnrollFaceModal', () => {
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

    mockUseEnrollFace.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ success: true, embedding_id: 1, quality_score: 0.85 }),
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
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <EnrollFaceModal {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Basic Rendering ==========

  describe('basic rendering', () => {
    it('renders modal when isOpen is true', () => {
      renderModal({ isOpen: true });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      // There's both title "Enroll Face" and button "Enroll Face"
      expect(screen.getAllByText(/enroll face/i).length).toBeGreaterThan(0);
    });

    it('does not render modal when isOpen is false', () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('displays the face preview image', () => {
      renderModal();
      const image = screen.getByRole('img', { name: /face preview/i });
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', defaultProps.facePreviewUrl);
    });

    it('displays placeholder when no facePreviewUrl is provided', () => {
      renderModal({ facePreviewUrl: undefined });
      const image = screen.getByRole('img', { name: /face preview/i });
      expect(image).toHaveAttribute('src', '/placeholder-face.png');
    });

    it('displays quality score', () => {
      renderModal();
      expect(screen.getByText(/quality score/i)).toBeInTheDocument();
      // FaceQualityAssessment shows percentage format (85%)
      const overallSection = screen.getByTestId('quality-overall-score');
      expect(within(overallSection).getByText('85%')).toBeInTheDocument();
    });

    it('displays camera name', () => {
      renderModal();
      expect(screen.getByText(/camera/i)).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('displays timestamp formatted nicely', () => {
      renderModal();
      expect(screen.getByText(/time/i)).toBeInTheDocument();
      // Should show formatted date/time
      expect(screen.getByText(/jan 31, 2025/i)).toBeInTheDocument();
    });

    it('displays close button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /close modal/i })).toBeInTheDocument();
    });

    it('displays cancel button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('displays enroll button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /enroll face/i })).toBeInTheDocument();
    });
  });

  // ========== Quality Score Indicators ==========

  describe('quality score indicators', () => {
    it('shows green indicator and "Good" label for quality >= 0.8', () => {
      renderModal({ qualityScore: 0.85 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-green-500');
      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    it('shows yellow indicator and "Fair" label for quality 0.7-0.8', () => {
      renderModal({ qualityScore: 0.75 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');
      expect(screen.getByText('Fair')).toBeInTheDocument();
    });

    it('shows red indicator and "Poor" label for quality < 0.7', () => {
      renderModal({ qualityScore: 0.65 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-red-500');
      expect(screen.getByText('Poor')).toBeInTheDocument();
    });

    it('displays warning message for quality 0.7-0.8', () => {
      renderModal({ qualityScore: 0.75 });
      // FaceQualityAssessment shows "Moderate Quality" warning for fair scores
      expect(screen.getByTestId('quality-fair-warning')).toBeInTheDocument();
      expect(screen.getByText(/moderate quality/i)).toBeInTheDocument();
    });

    it('displays blocking message and disables enroll for quality < 0.7', () => {
      renderModal({ qualityScore: 0.65 });
      // FaceQualityAssessment shows "Quality Too Low" for poor scores
      expect(screen.getByText(/quality too low/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /enroll face/i })).toBeDisabled();
    });

    it('does not display warning for quality >= 0.8', () => {
      renderModal({ qualityScore: 0.85 });
      // FaceQualityAssessment shows "Excellent quality" message for good scores
      expect(screen.queryByTestId('quality-fair-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('quality-blocked-warning')).not.toBeInTheDocument();
    });

    it('displays visual progress bar for quality score', () => {
      renderModal({ qualityScore: 0.85 });
      const progressBar = screen.getByTestId('quality-progress-bar');
      expect(progressBar).toBeInTheDocument();
      // Width should be 85%
      expect(progressBar).toHaveStyle({ width: '85%' });
    });
  });

  // ========== Mode Selection ==========

  describe('mode selection', () => {
    it('renders two radio options: add to existing and create new', () => {
      renderModal();
      expect(screen.getByRole('radio', { name: /add to existing person/i })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /create new person/i })).toBeInTheDocument();
    });

    it('defaults to "add to existing" mode', () => {
      renderModal();
      const existingRadio = screen.getByRole('radio', { name: /add to existing person/i });
      expect(existingRadio).toBeChecked();
    });

    it('shows person selector when "add to existing" is selected', () => {
      renderModal();
      expect(screen.getByLabelText(/select person/i)).toBeInTheDocument();
    });

    it('hides person selector when "create new" is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      const createNewRadio = screen.getByRole('radio', { name: /create new person/i });
      await user.click(createNewRadio);

      expect(screen.queryByLabelText(/select person/i)).not.toBeInTheDocument();
    });

    it('shows name input when "create new" is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      const createNewRadio = screen.getByRole('radio', { name: /create new person/i });
      await user.click(createNewRadio);

      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    it('shows household checkbox when "create new" is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      const createNewRadio = screen.getByRole('radio', { name: /create new person/i });
      await user.click(createNewRadio);

      expect(screen.getByRole('checkbox', { name: /household member/i })).toBeInTheDocument();
    });
  });

  // ========== Person Selector ==========

  describe('person selector', () => {
    it('displays searchable dropdown with known persons', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
    });

    it('filters persons as user types in search', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // Find and type in the search input
      const searchInput = screen.getByPlaceholderText(/search persons/i);
      await user.type(searchInput, 'John');

      // After typing, John Smith should be visible but not Jane Doe
      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('John Smith');
    });

    it('shows embedding count for each person', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // John Smith has 3 embeddings
      expect(screen.getByText(/3 faces/i)).toBeInTheDocument();
    });

    it('shows household badge for household members', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // Should show household indicators for John and Bob
      const options = screen.getAllByRole('option');
      const johnOption = options.find((opt) => opt.textContent?.includes('John Smith'));
      expect(johnOption).toHaveTextContent(/household/i);
    });

    it('shows warning for person at max embeddings (10)', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      // Bob Wilson has 10 embeddings (max)
      const bobOption = screen.getByRole('option', { name: /bob wilson/i });
      expect(within(bobOption).getByText(/max reached/i)).toBeInTheDocument();
    });

    it('disables person option when at max embeddings', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      const bobOption = screen.getByRole('option', { name: /bob wilson/i });
      expect(bobOption).toHaveAttribute('aria-disabled', 'true');
    });

    it('enables enroll button when person is selected', async () => {
      const user = userEvent.setup();
      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      const enrollButton = screen.getByRole('button', { name: /enroll face/i });
      expect(enrollButton).not.toBeDisabled();
    });

    it('shows loading state for persons query', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      });

      renderModal();
      expect(screen.getByText(/loading persons/i)).toBeInTheDocument();
    });

    it('shows error state for persons query', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load persons' },
      });

      renderModal();
      expect(screen.getByText(/failed to load persons/i)).toBeInTheDocument();
    });

    it('shows empty state when no persons exist', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
      });

      renderModal();
      expect(screen.getByText(/no known persons/i)).toBeInTheDocument();
    });
  });

  // ========== Create New Person Form ==========

  describe('create new person form', () => {
    it('validates name is required', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      const enrollButton = screen.getByRole('button', { name: /enroll face/i });
      expect(enrollButton).toBeDisabled();
    });

    it('enables enroll button when name is entered', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'Test Person');

      const enrollButton = screen.getByRole('button', { name: /enroll face/i });
      expect(enrollButton).not.toBeDisabled();
    });

    it('household checkbox is unchecked by default', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));

      const checkbox = screen.getByRole('checkbox', { name: /household member/i });
      expect(checkbox).not.toBeChecked();
    });

    it('can toggle household checkbox', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      const checkbox = screen.getByRole('checkbox', { name: /household member/i });

      await user.click(checkbox);
      expect(checkbox).toBeChecked();

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  // ========== Enrollment Flow - Existing Person ==========

  describe('enrollment flow - existing person', () => {
    it('calls enrollFace mutation with correct params', async () => {
      const user = userEvent.setup();
      const mutateAsync = vi.fn().mockResolvedValue({ success: true, embedding_id: 'emb-1' });
      mockUseEnrollFace.mockReturnValue({
        mutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      expect(mutateAsync).toHaveBeenCalledWith({
        personId: 1,
        detectionId: 'detection-123',
      });
    });

    it('shows loading state during enrollment', () => {
      mockUseEnrollFace.mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();

      // With isPending=true from the start, the loading state should show
      expect(screen.getByRole('button', { name: /enrolling/i })).toBeDisabled();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('shows success toast and closes modal on success', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const successToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: successToast,
        error: vi.fn(),
        warning: vi.fn(),
        info: vi.fn(),
      });

      renderModal({ onClose });

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      await waitFor(() => {
        expect(successToast).toHaveBeenCalledWith(
          expect.stringContaining('enrolled'),
          expect.any(Object)
        );
      });

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });

    it('shows error toast on enrollment failure', async () => {
      const user = userEvent.setup();
      const errorToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: vi.fn(),
        error: errorToast,
        warning: vi.fn(),
        info: vi.fn(),
      });

      mockUseEnrollFace.mockReturnValue({
        mutateAsync: vi.fn().mockRejectedValue(new Error('Enrollment failed')),
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      await waitFor(() => {
        expect(errorToast).toHaveBeenCalledWith(
          expect.stringContaining('failed'),
          expect.any(Object)
        );
      });
    });
  });

  // ========== Enrollment Flow - New Person ==========

  describe('enrollment flow - new person', () => {
    it('creates person first, then enrolls face', async () => {
      const user = userEvent.setup();
      const createMutateAsync = vi.fn().mockResolvedValue({ id: 5, name: 'New Person' });
      const enrollMutateAsync = vi.fn().mockResolvedValue({ success: true, embedding_id: 'emb-2' });

      mockUseCreateKnownPerson.mockReturnValue({
        mutateAsync: createMutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      mockUseEnrollFace.mockReturnValue({
        mutateAsync: enrollMutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'New Person');

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      await waitFor(() => {
        expect(createMutateAsync).toHaveBeenCalledWith({
          name: 'New Person',
          is_household_member: false,
        });
      });

      await waitFor(() => {
        expect(enrollMutateAsync).toHaveBeenCalledWith({
          personId: 5,
          detectionId: 'detection-123',
        });
      });
    });

    it('passes household member flag when checked', async () => {
      const user = userEvent.setup();
      const createMutateAsync = vi.fn().mockResolvedValue({ id: 5, name: 'New Person' });

      mockUseCreateKnownPerson.mockReturnValue({
        mutateAsync: createMutateAsync,
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'New Person');
      await user.click(screen.getByRole('checkbox', { name: /household member/i }));

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      await waitFor(() => {
        expect(createMutateAsync).toHaveBeenCalledWith({
          name: 'New Person',
          is_household_member: true,
        });
      });
    });

    it('shows error if person creation fails', async () => {
      const user = userEvent.setup();
      const errorToast = vi.fn();
      mockUseToast.mockReturnValue({
        success: vi.fn(),
        error: errorToast,
        warning: vi.fn(),
        info: vi.fn(),
      });

      mockUseCreateKnownPerson.mockReturnValue({
        mutateAsync: vi.fn().mockRejectedValue(new Error('Create failed')),
        isPending: false,
        isError: false,
        error: null,
      });

      renderModal();

      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'New Person');

      await user.click(screen.getByRole('button', { name: /enroll face/i }));

      await waitFor(() => {
        expect(errorToast).toHaveBeenCalledWith(
          expect.stringContaining('failed'),
          expect.any(Object)
        );
      });
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

    it('disables all inputs during enrollment', () => {
      mockUseEnrollFace.mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
      });

      renderModal();

      expect(screen.getByRole('radio', { name: /add to existing person/i })).toBeDisabled();
      expect(screen.getByRole('radio', { name: /create new person/i })).toBeDisabled();
      expect(screen.getByLabelText(/select person/i)).toBeDisabled();
    });

    it('resets form when modal closes and reopens', async () => {
      const user = userEvent.setup();
      const { rerender } = renderModal({ isOpen: true });

      // Select create new and enter name
      await user.click(screen.getByRole('radio', { name: /create new person/i }));
      await user.type(screen.getByLabelText(/name/i), 'Test Name');

      // Close modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <EnrollFaceModal {...defaultProps} isOpen={false} />
        </QueryClientProvider>
      );

      // Reopen modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <EnrollFaceModal {...defaultProps} isOpen={true} />
        </QueryClientProvider>
      );

      // Should be back to default state
      expect(screen.getByRole('radio', { name: /add to existing person/i })).toBeChecked();
    });
  });

  // ========== Accessibility ==========

  describe('accessibility', () => {
    it('has appropriate aria-label on modal', () => {
      renderModal();
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');
    });

    it('focuses on close button when modal opens', async () => {
      renderModal();
      await waitFor(() => {
        expect(document.activeElement?.closest('[role="dialog"]')).toBeInTheDocument();
      });
    });

    it('traps focus within modal', async () => {
      const user = userEvent.setup();
      renderModal();

      // Tab through all focusable elements
      await user.tab();
      await user.tab();
      await user.tab();
      await user.tab();
      await user.tab();
      await user.tab();

      // Focus should stay within modal
      expect(document.activeElement?.closest('[role="dialog"]')).toBeInTheDocument();
    });

    it('quality indicator has aria-label', () => {
      renderModal();
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveAttribute('aria-label');
    });
  });

  // ========== Edge Cases ==========

  describe('edge cases', () => {
    it('handles missing timestamp gracefully', () => {
      renderModal({ timestamp: undefined });
      expect(screen.getByText(/unknown time/i)).toBeInTheDocument();
    });

    it('handles quality score of 0', () => {
      renderModal({ qualityScore: 0 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-red-500');
      expect(screen.getByRole('button', { name: /enroll face/i })).toBeDisabled();
    });

    it('handles quality score of exactly 0.7', async () => {
      const user = userEvent.setup();
      renderModal({ qualityScore: 0.7 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');

      // Select a person first - button should be enabled since 0.7 is at threshold
      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);
      await user.click(screen.getByText('John Smith'));

      expect(screen.getByRole('button', { name: /enroll face/i })).not.toBeDisabled();
    });

    it('handles quality score of exactly 0.8', () => {
      renderModal({ qualityScore: 0.8 });
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-green-500');
    });

    it('handles quality score above 1.0 (capped display)', () => {
      renderModal({ qualityScore: 1.2 });
      const progressBar = screen.getByTestId('quality-progress-bar');
      expect(progressBar).toHaveStyle({ width: '100%' });
    });

    it('handles very long person names with truncation', async () => {
      const user = userEvent.setup();
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [
          {
            ...mockKnownPersons[0],
            name: 'This Is A Very Long Person Name That Should Be Truncated',
          },
        ],
        isLoading: false,
        isError: false,
      });

      renderModal();

      const selector = screen.getByLabelText(/select person/i);
      await user.click(selector);

      const option = screen.getByRole('option');
      expect(option).toHaveClass('truncate');
    });
  });
});
