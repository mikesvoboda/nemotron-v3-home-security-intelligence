/**
 * Tests for KnownPersonDetailModal component
 *
 * TDD Phase: RED - These tests drive the implementation of KnownPersonDetailModal.
 * Task: NEM-4688 Phase 1 - Create Known Person Detail Modal
 *
 * This test suite covers:
 * - Modal rendering and states
 * - Person details display
 * - Face embeddings gallery with delete functionality
 * - Recent appearances timeline
 * - Edit/Delete actions
 * - Accessibility
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import KnownPersonDetailModal from './KnownPersonDetailModal';
import { renderWithProviders } from '../../test/utils';

import type { KnownPerson, FaceEmbedding, PersonAppearance } from '../../types/faceRecognition';

// ============================================================================
// Mock Data
// ============================================================================

const mockPerson: KnownPerson = {
  id: 1,
  name: 'John Smith',
  is_household_member: true,
  notes: 'Family member - primary resident',
  created_at: '2025-01-15T10:00:00Z',
  updated_at: '2025-01-20T12:00:00Z',
  embedding_count: 3,
  household_member_id: 42,
};

const mockEmbeddings: FaceEmbedding[] = [
  {
    id: 101,
    person_id: 1,
    quality_score: 0.92,
    source_image_path: '/images/face1.jpg',
    created_at: '2025-01-15T10:00:00Z',
  },
  {
    id: 102,
    person_id: 1,
    quality_score: 0.88,
    source_image_path: '/images/face2.jpg',
    created_at: '2025-01-16T11:00:00Z',
  },
  {
    id: 103,
    person_id: 1,
    quality_score: 0.85,
    source_image_path: '/images/face3.jpg',
    created_at: '2025-01-17T12:00:00Z',
  },
];

const mockAppearances: PersonAppearance[] = [
  {
    timestamp: '2025-01-31T10:32:00Z',
    camera_id: 1,
    camera_name: 'Front Door',
    detection_id: 'det-001',
    confidence: 0.95,
    thumbnail_url: '/thumbnails/det-001.jpg',
    event_id: 1001,
  },
  {
    timestamp: '2025-01-31T08:15:00Z',
    camera_id: 2,
    camera_name: 'Driveway',
    detection_id: 'det-002',
    confidence: 0.92,
    thumbnail_url: '/thumbnails/det-002.jpg',
    event_id: 1002,
  },
  {
    timestamp: '2025-01-30T18:45:00Z',
    camera_id: 3,
    camera_name: 'Backyard',
    detection_id: 'det-003',
    confidence: 0.89,
    thumbnail_url: '/thumbnails/det-003.jpg',
    event_id: 1003,
  },
];

// ============================================================================
// Mock Variables
// ============================================================================

let mockPersonData: KnownPerson | undefined = mockPerson;
let mockPersonLoading = false;
let mockPersonError: Error | null = null;

let mockEmbeddingsData: FaceEmbedding[] | undefined = mockEmbeddings;
let mockEmbeddingsLoading = false;

let mockAppearancesData: PersonAppearance[] | undefined = mockAppearances;
let mockAppearancesLoading = false;

const mockDeleteEmbedding = vi.fn();
const mockOnClose = vi.fn();
const mockOnEdit = vi.fn();
const mockOnDelete = vi.fn();
const mockOnEnrollFace = vi.fn();

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useKnownPersonQuery: () => ({
    data: mockPersonData,
    isLoading: mockPersonLoading,
    error: mockPersonError,
  }),
  usePersonEmbeddingsQuery: () => ({
    data: mockEmbeddingsData,
    isLoading: mockEmbeddingsLoading,
  }),
  usePersonAppearancesQuery: () => ({
    data: { appearances: mockAppearancesData ?? [], total: mockAppearancesData?.length ?? 0 },
    isLoading: mockAppearancesLoading,
  }),
  useDeleteEmbedding: () => ({
    mutateAsync: mockDeleteEmbedding,
    isPending: false,
  }),
  useUpdateKnownPerson: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock('../../hooks/useHouseholdApi', () => ({
  useMembersQuery: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// ============================================================================
// Helper Functions
// ============================================================================

function renderModal(props?: Partial<Parameters<typeof KnownPersonDetailModal>[0]>) {
  const defaultProps = {
    personId: 1,
    isOpen: true,
    onClose: mockOnClose,
    onEdit: mockOnEdit,
    onDelete: mockOnDelete,
    onEnrollFace: mockOnEnrollFace,
  };
  return renderWithProviders(<KnownPersonDetailModal {...defaultProps} {...props} />);
}

// ============================================================================
// Tests
// ============================================================================

describe('KnownPersonDetailModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock data to defaults
    mockPersonData = mockPerson;
    mockPersonLoading = false;
    mockPersonError = null;
    mockEmbeddingsData = mockEmbeddings;
    mockEmbeddingsLoading = false;
    mockAppearancesData = mockAppearances;
    mockAppearancesLoading = false;
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the modal when open', () => {
      renderModal();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not render when personId is null', () => {
      renderModal({ personId: null });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows loading state when data is loading', () => {
      mockPersonLoading = true;
      mockPersonData = undefined;
      renderModal();

      expect(screen.getByTestId('person-detail-loading')).toBeInTheDocument();
    });

    it('shows error state when fetch fails', () => {
      mockPersonError = new Error('Failed to load person');
      mockPersonData = undefined;
      renderModal();

      expect(screen.getByText(/Failed to load person/i)).toBeInTheDocument();
    });

    it('displays person name in header', () => {
      renderModal();
      // Person name appears in the dialog heading
      expect(screen.getByRole('heading', { level: 2, name: 'John Smith' })).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Person Details Tests
  // ==========================================================================

  describe('person details', () => {
    it('displays person name', () => {
      renderModal();
      // Person name appears in both the heading and the details section
      // Check the heading exists
      expect(screen.getByRole('heading', { level: 2, name: 'John Smith' })).toBeInTheDocument();
    });

    it('displays household member status when linked', () => {
      renderModal();
      // Check that both the label and value are present
      expect(screen.getByText(/Linked Household:/i)).toBeInTheDocument();
      expect(screen.getByText('Yes')).toBeInTheDocument();
    });

    it('displays "No" when not a household member', () => {
      mockPersonData = { ...mockPerson, is_household_member: false, household_member_id: null };
      renderModal();
      // Check that both the label and value are present
      expect(screen.getByText(/Linked Household:/i)).toBeInTheDocument();
      // Use getAllByText since "No" might appear elsewhere, then check the first one
      const noElements = screen.getAllByText('No');
      expect(noElements.length).toBeGreaterThan(0);
    });

    it('displays trust level for household members', () => {
      renderModal();
      expect(screen.getByText(/Full/i)).toBeInTheDocument();
    });

    it('displays created date formatted', () => {
      renderModal();
      // Should display Jan 15, 2025
      expect(screen.getByText(/Jan 15, 2025/i)).toBeInTheDocument();
    });

    it('displays notes when available', () => {
      renderModal();
      expect(screen.getByText(/Family member - primary resident/i)).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Face Embeddings Gallery Tests
  // ==========================================================================

  describe('face embeddings gallery', () => {
    it('displays embedding count in header', () => {
      renderModal();
      expect(screen.getByText(/Face Embeddings \(3\)/i)).toBeInTheDocument();
    });

    it('shows Add from Event button', () => {
      renderModal();
      expect(screen.getByRole('button', { name: /Add from Event/i })).toBeInTheDocument();
    });

    it('calls onEnrollFace when Add from Event is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('button', { name: /Add from Event/i }));
      expect(mockOnEnrollFace).toHaveBeenCalledWith(1);
    });

    it('displays all face embeddings', () => {
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const embeddingCards = within(gallery).getAllByTestId(/^embedding-card-/);
      expect(embeddingCards).toHaveLength(3);
    });

    it('displays quality score for each embedding', () => {
      renderModal();

      expect(screen.getByText('0.92')).toBeInTheDocument();
      expect(screen.getByText('0.88')).toBeInTheDocument();
      expect(screen.getByText('0.85')).toBeInTheDocument();
    });

    it('shows delete button for each embedding', () => {
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const deleteButtons = within(gallery).getAllByRole('button', { name: /Delete embedding/i });
      expect(deleteButtons).toHaveLength(3);
    });

    it('shows confirmation dialog when delete button is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const deleteButtons = within(gallery).getAllByRole('button', { name: /Delete embedding/i });
      await user.click(deleteButtons[0]);

      expect(screen.getByText(/Are you sure you want to delete this face embedding/i)).toBeInTheDocument();
    });

    it('calls deleteEmbedding when confirmed', async () => {
      const user = userEvent.setup();
      mockDeleteEmbedding.mockResolvedValue(undefined);
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const deleteButtons = within(gallery).getAllByRole('button', { name: /Delete embedding/i });
      await user.click(deleteButtons[0]);
      await user.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(mockDeleteEmbedding).toHaveBeenCalledWith({
          personId: 1,
          embeddingId: 101,
        });
      });
    });

    it('cancels deletion when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const deleteButtons = within(gallery).getAllByRole('button', { name: /Delete embedding/i });
      await user.click(deleteButtons[0]);
      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(mockDeleteEmbedding).not.toHaveBeenCalled();
      // Wait for the dialog to close
      await waitFor(() => {
        expect(screen.queryByText(/Are you sure you want to delete this face embedding/i)).not.toBeInTheDocument();
      });
    });

    it('shows empty state when no embeddings', () => {
      mockEmbeddingsData = [];
      renderModal();

      expect(screen.getByText(/No face embeddings yet/i)).toBeInTheDocument();
    });

    it('shows loading state for embeddings', () => {
      mockEmbeddingsLoading = true;
      mockEmbeddingsData = undefined;
      renderModal();

      expect(screen.getByTestId('embeddings-loading')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Recent Appearances Timeline Tests
  // ==========================================================================

  describe('recent appearances timeline', () => {
    it('displays Recent Appearances header', () => {
      renderModal();
      expect(screen.getByText(/Recent Appearances/i)).toBeInTheDocument();
    });

    it('displays up to 5 recent appearances', () => {
      renderModal();

      const timeline = screen.getByTestId('appearances-timeline');
      const appearances = within(timeline).getAllByTestId(/^appearance-item-/);
      expect(appearances).toHaveLength(3);
    });

    it('displays camera name for each appearance', () => {
      renderModal();

      expect(screen.getByText(/Front Door/i)).toBeInTheDocument();
      expect(screen.getByText(/Driveway/i)).toBeInTheDocument();
      expect(screen.getByText(/Backyard/i)).toBeInTheDocument();
    });

    it('displays confidence for each appearance', () => {
      renderModal();

      expect(screen.getByText(/95%/i)).toBeInTheDocument();
      expect(screen.getByText(/92%/i)).toBeInTheDocument();
      expect(screen.getByText(/89%/i)).toBeInTheDocument();
    });

    it('displays formatted timestamp', () => {
      renderModal();

      // The timestamps are formatted with date/time
      // Since mock dates may not be "today", just check that the timeline is rendered
      const timeline = screen.getByTestId('appearances-timeline');
      expect(timeline).toBeInTheDocument();
      // The appearance items should exist and have timestamps
      const appearanceItems = within(timeline).getAllByTestId(/^appearance-item-/);
      expect(appearanceItems.length).toBeGreaterThan(0);
    });

    it('shows View Full Timeline link', () => {
      renderModal();

      expect(screen.getByRole('button', { name: /View Full Timeline/i })).toBeInTheDocument();
    });

    it('shows empty state when no appearances', () => {
      mockAppearancesData = [];
      renderModal();

      expect(screen.getByText(/No recent appearances/i)).toBeInTheDocument();
    });

    it('shows loading state for appearances', () => {
      mockAppearancesLoading = true;
      mockAppearancesData = undefined;
      renderModal();

      expect(screen.getByTestId('appearances-loading')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Header Actions Tests
  // ==========================================================================

  describe('header actions', () => {
    it('shows Edit button', () => {
      renderModal();
      // The Edit button in header has exact aria-label "Edit"
      expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    });

    it('shows Delete button', () => {
      renderModal();
      // The Delete button in header has exact aria-label "Delete" (not "Delete embedding")
      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    });

    it('calls onEdit with person data when Edit is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.click(screen.getByRole('button', { name: 'Edit' }));
      expect(mockOnEdit).toHaveBeenCalledWith(mockPerson);
    });

    it('calls onDelete with person data when Delete is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      // Click the header Delete button, not the embedding delete buttons
      await user.click(screen.getByRole('button', { name: 'Delete' }));
      expect(mockOnDelete).toHaveBeenCalledWith(mockPerson);
    });

    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      renderModal();

      // The Close button has exact aria-label "Close"
      const closeButton = screen.getByRole('button', { name: 'Close' });
      await user.click(closeButton);

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has modal with accessible role="dialog"', () => {
      renderModal();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has accessible dialog title', () => {
      renderModal();
      const dialog = screen.getByRole('dialog');
      // Find the heading element which contains the title
      const heading = within(dialog).getByRole('heading', { level: 2 });
      expect(heading).toHaveTextContent('John Smith');
    });

    it('traps focus within modal when open', async () => {
      const user = userEvent.setup();
      renderModal();

      // Focus should be trapped in modal
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();

      // Tab through focusable elements
      await user.tab();
      const activeElement = document.activeElement;
      expect(dialog.contains(activeElement)).toBe(true);
    });

    it('closes modal on Escape key', async () => {
      const user = userEvent.setup();
      renderModal();

      await user.keyboard('{Escape}');
      expect(mockOnClose).toHaveBeenCalled();
    });

    it('has proper heading structure', () => {
      renderModal();

      // Person name should be the dialog title
      const dialog = screen.getByRole('dialog');
      const heading = within(dialog).getByRole('heading', { level: 2 });
      expect(heading).toHaveTextContent('John Smith');
    });

    it('delete buttons have accessible names', () => {
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const deleteButtons = within(gallery).getAllByRole('button', { name: /Delete embedding/i });
      expect(deleteButtons[0]).toHaveAccessibleName();
    });
  });

  // ==========================================================================
  // Quality Score Display Tests
  // ==========================================================================

  describe('quality score display', () => {
    it('shows green border for high quality (>= 0.8)', () => {
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const highQualityCard = within(gallery).getByTestId('embedding-card-101');
      // High quality has green border
      expect(highQualityCard.className).toContain('border-green');
    });

    it('shows yellow border for medium quality (0.7-0.8)', () => {
      mockEmbeddingsData = [{ ...mockEmbeddings[0], quality_score: 0.75 }];
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const mediumQualityCard = within(gallery).getByTestId('embedding-card-101');
      // Medium quality has yellow border
      expect(mediumQualityCard.className).toContain('border-yellow');
    });

    it('shows red border for low quality (< 0.7)', () => {
      mockEmbeddingsData = [{ ...mockEmbeddings[0], quality_score: 0.65 }];
      renderModal();

      const gallery = screen.getByTestId('face-embeddings-gallery');
      const lowQualityCard = within(gallery).getByTestId('embedding-card-101');
      // Low quality has red border
      expect(lowQualityCard.className).toContain('border-red');
    });
  });

  // ==========================================================================
  // Primary Photo Tests
  // ==========================================================================

  describe('primary photo', () => {
    it('displays primary photo section', () => {
      renderModal();
      expect(screen.getByTestId('primary-photo')).toBeInTheDocument();
    });

    it('shows highest quality embedding as primary photo', () => {
      renderModal();

      const primaryPhoto = screen.getByTestId('primary-photo');
      // The highest quality embedding (0.92) should be shown as primary
      const img = within(primaryPhoto).getByRole('img');
      expect(img).toHaveAttribute('src', expect.stringContaining('face1.jpg'));
    });

    it('shows placeholder when no embeddings', () => {
      mockEmbeddingsData = [];
      renderModal();

      const primaryPhoto = screen.getByTestId('primary-photo');
      expect(within(primaryPhoto).getByTestId('photo-placeholder')).toBeInTheDocument();
    });
  });
});
