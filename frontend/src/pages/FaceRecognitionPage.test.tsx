/**
 * Tests for FaceRecognitionPage component
 *
 * TDD Phase: GREEN - These tests validate the Face Recognition page behavior.
 * Task: NEM-4688 Phase 1 - Create Face Recognition Page with Tabs
 * Task: NEM-4688 Phase 3 - Face Events Tab wiring
 * Task: NEM-4688 Phase 4 - Real-Time Unknown Stranger Alerts & Person Tracking
 *
 * This test suite covers:
 * - Page rendering with proper structure
 * - Tab navigation (Known Persons, Face Events, Person Tracking, Debug Tools)
 * - Tab switching behavior
 * - Accessibility requirements
 * - Unknown stranger alert integration (Phase 4)
 * - Real component wiring for all tabs
 * - Modal integration (KnownPersonDetailModal, AddPersonModal)
 */

import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import FaceRecognitionPage from './FaceRecognitionPage';
import * as useUnknownStrangerAlertsModule from '../hooks/useUnknownStrangerAlerts';
import { renderWithProviders } from '../test/utils';

// ============================================================================
// Mocks
// ============================================================================

// Mock useToast hook (may be needed for future phases)
vi.mock('../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock useUnknownStrangerAlerts hook
vi.mock('../hooks/useUnknownStrangerAlerts', () => ({
  useUnknownStrangerAlerts: vi.fn(),
}));

// Mock KnownPersonsTab component to isolate page-level tests from API calls
vi.mock('../components/face-recognition/KnownPersonsTab', () => ({
  default: ({ onPersonClick, onAddPerson }: { onPersonClick: (person: unknown) => void; onAddPerson: () => void }) => (
    <div data-testid="known-persons-tab-real">
      Known Persons Tab Component
      <button data-testid="mock-person-click" onClick={() => onPersonClick({ id: 1, name: 'Test Person', is_household_member: false, created_at: '2025-01-01T00:00:00Z' })}>Click Person</button>
      <button data-testid="mock-add-person" onClick={() => onAddPerson()}>Add Person</button>
    </div>
  ),
}));

// Mock FaceEventsTab component to isolate page-level tests from API calls
vi.mock('../components/face-recognition/FaceEventsTab', () => ({
  default: ({ onIdentify: _onIdentify, onAddNewPerson: _onAddNewPerson, onViewDetection: _onViewDetection }: { onIdentify: (id: number) => void; onAddNewPerson: (id: number) => void; onViewDetection: (id: string) => void }) => (
    <div data-testid="face-events-tab-real">Face Events Tab Component</div>
  ),
}));

// Mock PersonTrackingTab component to isolate page-level tests from API calls
vi.mock('../components/face-recognition/PersonTrackingTab', () => ({
  default: () => (
    <div data-testid="person-tracking-tab-real">Person Tracking Tab Component</div>
  ),
}));

// Mock KnownPersonDetailModal to isolate page-level tests
vi.mock('../components/face-recognition/KnownPersonDetailModal', () => ({
  default: ({ isOpen, personId, onClose }: { isOpen: boolean; personId: number | null; onClose: () => void }) => (
    isOpen ? <div data-testid="known-person-detail-modal" data-person-id={personId}><button data-testid="mock-close-detail" onClick={onClose}>Close</button></div> : null
  ),
}));

// Mock AddPersonModal to isolate page-level tests
vi.mock('../components/face-recognition/AddPersonModal', () => ({
  default: ({ isOpen, onClose, editPerson }: { isOpen: boolean; onClose: () => void; editPerson?: unknown }) => (
    isOpen ? <div data-testid="add-person-modal" data-edit-mode={editPerson ? 'true' : 'false'}><button data-testid="mock-close-add" onClick={onClose}>Close</button></div> : null
  ),
}));

// ============================================================================
// Tests
// ============================================================================

// Default mock return value
const mockMarkAsRead = vi.fn();
const defaultMockReturn: ReturnType<typeof useUnknownStrangerAlertsModule.useUnknownStrangerAlerts> = {
  isConnected: true,
  lastUnknownFace: null,
  unreadCount: 0,
  markAsRead: mockMarkAsRead,
  hasExhaustedRetries: false,
  reconnectCount: 0,
};

describe('FaceRecognitionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock to default return value
    (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue(
      defaultMockReturn
    );
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the page without crashing', () => {
      renderWithProviders(<FaceRecognitionPage />);
      expect(screen.getByTestId('face-recognition-page')).toBeInTheDocument();
    });

    it('displays page title "Face Recognition"', () => {
      renderWithProviders(<FaceRecognitionPage />);
      expect(screen.getByRole('heading', { name: /Face Recognition/i })).toBeInTheDocument();
    });

    it('displays page description', () => {
      renderWithProviders(<FaceRecognitionPage />);
      expect(
        screen.getByText(/Manage known persons and track face detections/i)
      ).toBeInTheDocument();
    });

    it('has proper heading hierarchy with H1', () => {
      renderWithProviders(<FaceRecognitionPage />);
      const mainHeading = screen.getByRole('heading', { name: /Face Recognition/i });
      expect(mainHeading).toBeInTheDocument();
      expect(mainHeading.tagName).toBe('H1');
    });
  });

  // ==========================================================================
  // Tab Navigation Tests
  // ==========================================================================

  describe('tab navigation', () => {
    it('displays all four tabs', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.getByRole('tab', { name: /Known Persons/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Face Events/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Person Tracking/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Debug Tools/i })).toBeInTheDocument();
    });

    it('has Known Persons tab selected by default', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const knownPersonsTab = screen.getByRole('tab', { name: /Known Persons/i });
      expect(knownPersonsTab).toHaveAttribute('aria-selected', 'true');
    });

    it('displays tab list with proper role', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.getByRole('tablist')).toBeInTheDocument();
    });

    it('displays Known Persons tab content by default', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.getByTestId('known-persons-tab-content')).toBeInTheDocument();
    });

    it('switches to Face Events tab when clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      const faceEventsTab = screen.getByRole('tab', { name: /Face Events/i });
      await user.click(faceEventsTab);

      await waitFor(() => {
        expect(faceEventsTab).toHaveAttribute('aria-selected', 'true');
        expect(screen.getByTestId('face-events-tab-content')).toBeInTheDocument();
      });
    });

    it('switches to Person Tracking tab when clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      const personTrackingTab = screen.getByRole('tab', { name: /Person Tracking/i });
      await user.click(personTrackingTab);

      await waitFor(() => {
        expect(personTrackingTab).toHaveAttribute('aria-selected', 'true');
        expect(screen.getByTestId('person-tracking-tab-content')).toBeInTheDocument();
      });
    });

    it('can navigate back to Known Persons tab', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Switch to Face Events first
      await user.click(screen.getByRole('tab', { name: /Face Events/i }));

      // Switch back to Known Persons
      const knownPersonsTab = screen.getByRole('tab', { name: /Known Persons/i });
      await user.click(knownPersonsTab);

      await waitFor(() => {
        expect(knownPersonsTab).toHaveAttribute('aria-selected', 'true');
        expect(screen.getByTestId('known-persons-tab-content')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Tab Content Tests
  // ==========================================================================

  describe('tab content', () => {
    it('Known Persons tab renders the real KnownPersonsTab component', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.getByTestId('known-persons-tab-content')).toBeInTheDocument();
      // Verify the real KnownPersonsTab component is rendered (mocked in this test)
      expect(screen.getByTestId('known-persons-tab-real')).toBeInTheDocument();
    });

    it('Face Events tab renders the real FaceEventsTab component', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      await user.click(screen.getByRole('tab', { name: /Face Events/i }));

      await waitFor(() => {
        expect(screen.getByTestId('face-events-tab-content')).toBeInTheDocument();
        expect(screen.getByTestId('face-events-tab-real')).toBeInTheDocument();
      });
    });

    it('Person Tracking tab renders the real PersonTrackingTab component', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      await user.click(screen.getByRole('tab', { name: /Person Tracking/i }));

      await waitFor(() => {
        expect(screen.getByTestId('person-tracking-tab-content')).toBeInTheDocument();
        expect(screen.getByTestId('person-tracking-tab-real')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Modal Integration Tests
  // ==========================================================================

  describe('modal integration', () => {
    it('opens KnownPersonDetailModal when a person is clicked in KnownPersonsTab', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Click on a person in the mocked KnownPersonsTab
      const personClickButton = screen.getByTestId('mock-person-click');
      await user.click(personClickButton);

      await waitFor(() => {
        expect(screen.getByTestId('known-person-detail-modal')).toBeInTheDocument();
        expect(screen.getByTestId('known-person-detail-modal')).toHaveAttribute('data-person-id', '1');
      });
    });

    it('opens AddPersonModal when add person is clicked in KnownPersonsTab', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Click add person in the mocked KnownPersonsTab
      const addPersonButton = screen.getByTestId('mock-add-person');
      await user.click(addPersonButton);

      await waitFor(() => {
        expect(screen.getByTestId('add-person-modal')).toBeInTheDocument();
        expect(screen.getByTestId('add-person-modal')).toHaveAttribute('data-edit-mode', 'false');
      });
    });

    it('closes KnownPersonDetailModal when close is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Open the detail modal
      await user.click(screen.getByTestId('mock-person-click'));

      await waitFor(() => {
        expect(screen.getByTestId('known-person-detail-modal')).toBeInTheDocument();
      });

      // Close the modal
      await user.click(screen.getByTestId('mock-close-detail'));

      await waitFor(() => {
        expect(screen.queryByTestId('known-person-detail-modal')).not.toBeInTheDocument();
      });
    });

    it('closes AddPersonModal when close is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Open the add person modal
      await user.click(screen.getByTestId('mock-add-person'));

      await waitFor(() => {
        expect(screen.getByTestId('add-person-modal')).toBeInTheDocument();
      });

      // Close the modal
      await user.click(screen.getByTestId('mock-close-add'));

      await waitFor(() => {
        expect(screen.queryByTestId('add-person-modal')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has proper ARIA roles for tabs', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const tablist = screen.getByRole('tablist');
      expect(tablist).toBeInTheDocument();

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(4);

      // Selected tab should have aria-selected=true
      expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
      expect(tabs[1]).toHaveAttribute('aria-selected', 'false');
      expect(tabs[2]).toHaveAttribute('aria-selected', 'false');
      expect(tabs[3]).toHaveAttribute('aria-selected', 'false');
    });

    it('has proper tabpanel roles', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.getByRole('tabpanel')).toBeInTheDocument();
    });

    it('supports keyboard navigation between tabs', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Focus the first tab
      const firstTab = screen.getByRole('tab', { name: /Known Persons/i });
      firstTab.focus();

      // Press right arrow to move to next tab
      await user.keyboard('{ArrowRight}');

      await waitFor(() => {
        const faceEventsTab = screen.getByRole('tab', { name: /Face Events/i });
        expect(faceEventsTab).toHaveFocus();
      });
    });

    it('has focus-visible styles on tabs', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const tabs = screen.getAllByRole('tab');
      // Tabs should have focus ring classes (checking class presence)
      tabs.forEach((tab) => {
        expect(tab.className).toContain('focus:');
      });
    });
  });

  // ==========================================================================
  // Styling Tests
  // ==========================================================================

  describe('styling', () => {
    it('has dark theme background', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const page = screen.getByTestId('face-recognition-page');
      expect(page.className).toContain('bg-[#121212]');
    });

    it('has tabs with proper styling classes', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const tablist = screen.getByRole('tablist');
      expect(tablist.className).toContain('bg-[#1A1A1A]');
    });

    it('selected tab has NVIDIA green accent', () => {
      renderWithProviders(<FaceRecognitionPage />);

      const selectedTab = screen.getByRole('tab', { name: /Known Persons/i });
      expect(selectedTab.className).toContain('#76B900');
    });
  });

  // ==========================================================================
  // Unknown Stranger Alerts Tests (NEM-4688 Phase 4)
  // ==========================================================================

  describe('unknown stranger alerts', () => {
    it('calls useUnknownStrangerAlerts hook with showToasts enabled', () => {
      renderWithProviders(<FaceRecognitionPage />);

      expect(useUnknownStrangerAlertsModule.useUnknownStrangerAlerts).toHaveBeenCalledWith(
        expect.objectContaining({
          showToasts: true,
        })
      );
    });

    it('does not show unread badge when unreadCount is 0', () => {
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 0,
      });

      renderWithProviders(<FaceRecognitionPage />);

      expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument();
    });

    it('shows unread badge on Face Events tab when there are unread alerts', () => {
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 5,
      });

      renderWithProviders(<FaceRecognitionPage />);

      const badge = screen.getByTestId('unread-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('5');
    });

    it('shows 99+ when unread count exceeds 99', () => {
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 150,
      });

      renderWithProviders(<FaceRecognitionPage />);

      const badge = screen.getByTestId('unread-badge');
      expect(badge).toHaveTextContent('99+');
    });

    it('unread badge has proper accessibility label', () => {
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 3,
      });

      renderWithProviders(<FaceRecognitionPage />);

      const badge = screen.getByTestId('unread-badge');
      expect(badge).toHaveAttribute('aria-label', '3 unread alerts');
    });

    it('calls markAsRead when switching to Face Events tab with unread alerts', async () => {
      const mockMarkAsReadFn = vi.fn();
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 5,
        markAsRead: mockMarkAsReadFn,
      });

      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Click on Face Events tab
      const faceEventsTab = screen.getByRole('tab', { name: /Face Events/i });
      await user.click(faceEventsTab);

      await waitFor(() => {
        expect(mockMarkAsReadFn).toHaveBeenCalled();
      });
    });

    it('does not call markAsRead when switching to Face Events tab with no unread alerts', async () => {
      const mockMarkAsReadFn = vi.fn();
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 0,
        markAsRead: mockMarkAsReadFn,
      });

      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Click on Face Events tab
      const faceEventsTab = screen.getByRole('tab', { name: /Face Events/i });
      await user.click(faceEventsTab);

      await waitFor(() => {
        expect(faceEventsTab).toHaveAttribute('aria-selected', 'true');
      });

      expect(mockMarkAsReadFn).not.toHaveBeenCalled();
    });

    it('does not call markAsRead when switching to Known Persons tab', async () => {
      const mockMarkAsReadFn = vi.fn();
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 5,
        markAsRead: mockMarkAsReadFn,
      });

      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Switch to Face Events first (which calls markAsRead)
      await user.click(screen.getByRole('tab', { name: /Face Events/i }));
      mockMarkAsReadFn.mockClear();

      // Switch to Known Persons
      await user.click(screen.getByRole('tab', { name: /Known Persons/i }));

      expect(mockMarkAsReadFn).not.toHaveBeenCalled();
    });

    it('does not call markAsRead when switching to Person Tracking tab', async () => {
      const mockMarkAsReadFn = vi.fn();
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 5,
        markAsRead: mockMarkAsReadFn,
      });

      const user = userEvent.setup();
      renderWithProviders(<FaceRecognitionPage />);

      // Switch to Person Tracking
      await user.click(screen.getByRole('tab', { name: /Person Tracking/i }));

      expect(mockMarkAsReadFn).not.toHaveBeenCalled();
    });

    it('onView callback switches to Face Events tab', async () => {
      let capturedOnView: ((face: unknown) => void) | undefined;

      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockImplementation(
        (options: { onView?: (face: unknown) => void }) => {
          capturedOnView = options.onView;
          return defaultMockReturn;
        }
      );

      renderWithProviders(<FaceRecognitionPage />);

      // Verify Known Persons tab is selected initially
      const knownPersonsTab = screen.getByRole('tab', { name: /Known Persons/i });
      expect(knownPersonsTab).toHaveAttribute('aria-selected', 'true');

      // Simulate calling onView (as if user clicked View on toast)
      act(() => {
        capturedOnView?.({ event_id: 123, is_unknown: true });
      });

      // Face Events tab should now be selected
      await waitFor(() => {
        const faceEventsTab = screen.getByRole('tab', { name: /Face Events/i });
        expect(faceEventsTab).toHaveAttribute('aria-selected', 'true');
      });
    });

    it('unread badge has correct styling for visibility', () => {
      (useUnknownStrangerAlertsModule.useUnknownStrangerAlerts as Mock).mockReturnValue({
        ...defaultMockReturn,
        unreadCount: 5,
      });

      renderWithProviders(<FaceRecognitionPage />);

      const badge = screen.getByTestId('unread-badge');
      expect(badge.className).toContain('bg-red-600');
      expect(badge.className).toContain('text-white');
    });
  });
});
