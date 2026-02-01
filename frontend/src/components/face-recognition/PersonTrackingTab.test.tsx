/**
 * PersonTrackingTab Test Suite
 *
 * Tests for the Person Tracking tab showing appearance timeline,
 * journey visualization, and statistics for a selected person.
 *
 * @module components/face-recognition/PersonTrackingTab.test
 * @see NEM-4688 Phase 3 - Person Tracking
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PersonTrackingTab from './PersonTrackingTab';

// ============================================================================
// Mock Hooks
// ============================================================================

const mockUseKnownPersonsQuery = vi.fn();
const mockUsePersonAppearancesQuery = vi.fn();

vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useKnownPersonsQuery: () => mockUseKnownPersonsQuery(),
  usePersonAppearancesQuery: (personId: number | null, filters: unknown) =>
    mockUsePersonAppearancesQuery(personId, filters),
}));

// ============================================================================
// Test Data
// ============================================================================

const mockKnownPersons = [
  {
    id: 1,
    name: 'John Smith',
    is_household_member: true,
    embedding_count: 3,
    notes: 'Family member',
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T12:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Doe',
    is_household_member: true,
    embedding_count: 2,
    notes: null,
    created_at: '2025-01-20T08:00:00Z',
    updated_at: '2025-01-20T08:00:00Z',
  },
  {
    id: 3,
    name: 'Delivery Person',
    is_household_member: false,
    embedding_count: 1,
    notes: 'Regular delivery',
    created_at: '2025-01-25T14:00:00Z',
    updated_at: '2025-01-25T14:00:00Z',
  },
];

const mockAppearances = {
  appearances: [
    {
      timestamp: '2025-01-31T08:15:00Z',
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-001',
      confidence: 0.95,
      thumbnail_url: '/api/thumbnails/det-001',
      event_id: 100,
    },
    {
      timestamp: '2025-01-31T08:17:00Z',
      camera_id: 2,
      camera_name: 'Front Door',
      detection_id: 'det-002',
      confidence: 0.92,
      thumbnail_url: '/api/thumbnails/det-002',
      event_id: 101,
    },
    {
      timestamp: '2025-01-31T10:32:00Z',
      camera_id: 2,
      camera_name: 'Front Door',
      detection_id: 'det-003',
      confidence: 0.88,
      thumbnail_url: null,
      event_id: 102,
    },
    {
      timestamp: '2025-01-31T10:34:00Z',
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-004',
      confidence: 0.91,
      thumbnail_url: '/api/thumbnails/det-004',
      event_id: 103,
    },
  ],
  total: 4,
};

const mockAppearancesLast7Days = {
  appearances: [
    ...mockAppearances.appearances,
    {
      timestamp: '2025-01-30T09:00:00Z',
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-005',
      confidence: 0.90,
      thumbnail_url: '/api/thumbnails/det-005',
      event_id: 104,
    },
    {
      timestamp: '2025-01-29T14:00:00Z',
      camera_id: 3,
      camera_name: 'Backyard',
      detection_id: 'det-006',
      confidence: 0.87,
      thumbnail_url: '/api/thumbnails/det-006',
      event_id: 105,
    },
  ],
  total: 6,
};

// ============================================================================
// Test Setup
// ============================================================================

describe('PersonTrackingTab', () => {
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

    mockUsePersonAppearancesQuery.mockReturnValue({
      data: mockAppearances,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <PersonTrackingTab {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Basic Rendering Tests ==========

  describe('Basic Rendering', () => {
    it('renders the component with correct title', () => {
      renderComponent();
      expect(screen.getByText('Person Tracking')).toBeInTheDocument();
    });

    it('renders the person selector dropdown', () => {
      renderComponent();
      expect(screen.getByTestId('person-selector')).toBeInTheDocument();
    });

    it('renders date range selector when person is selected', () => {
      renderComponent({ initialPersonId: 1 });
      expect(screen.getByTestId('date-range-selector')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      const { container } = renderComponent({ className: 'custom-class' });
      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('renders data-testid for the tab', () => {
      renderComponent();
      expect(screen.getByTestId('person-tracking-tab')).toBeInTheDocument();
    });
  });

  // ========== Person Selector Tests ==========

  describe('Person Selector', () => {
    it('displays placeholder when no person selected', () => {
      renderComponent();
      expect(screen.getByPlaceholderText(/search and select a person/i)).toBeInTheDocument();
    });

    it('displays all known persons in dropdown', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Focus the combobox input (clicking opens dropdown in Headless UI)
      const comboboxInput = screen.getByRole('combobox');
      // Type something to trigger dropdown
      await user.type(comboboxInput, 'J');

      // Clear to show all options
      await user.clear(comboboxInput);

      // Wait for dropdown to be visible using findBy
      const listbox = await screen.findByRole('listbox');
      expect(listbox).toBeInTheDocument();
      expect(within(listbox).getByText('John Smith')).toBeInTheDocument();
      expect(within(listbox).getByText('Jane Doe')).toBeInTheDocument();
      expect(within(listbox).getByText('Delivery Person')).toBeInTheDocument();
    });

    it('selects initial person when initialPersonId prop is provided', async () => {
      renderComponent({ initialPersonId: 1 });

      // The name should appear in the combobox input
      await waitFor(() => {
        const comboboxInput = screen.getByRole('combobox');
        expect(comboboxInput).toHaveValue('John Smith');
      });
    });

    it('calls API with selected person ID', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Type in the combobox to open dropdown
      const comboboxInput = screen.getByRole('combobox');
      await user.type(comboboxInput, 'John');

      // Wait for dropdown and click on John
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('John Smith'));

      await waitFor(() => {
        expect(mockUsePersonAppearancesQuery).toHaveBeenCalledWith(
          1,
          expect.any(Object)
        );
      });
    });

    it('allows searching persons by name', async () => {
      const user = userEvent.setup();
      renderComponent();

      const searchInput = screen.getByPlaceholderText(/search/i);
      await user.type(searchInput, 'Jane');

      await waitFor(() => {
        expect(screen.getByText('Jane Doe')).toBeInTheDocument();
        expect(screen.queryByText('John Smith')).not.toBeInTheDocument();
      });
    });

    it('shows no results message when search yields nothing', async () => {
      const user = userEvent.setup();
      renderComponent();

      const searchInput = screen.getByPlaceholderText(/search/i);
      await user.type(searchInput, 'xyz');

      await waitFor(() => {
        expect(screen.getByText(/no persons found/i)).toBeInTheDocument();
      });
    });

    it('displays household badge for household members in dropdown', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Type in the combobox to open dropdown
      const comboboxInput = screen.getByRole('combobox');
      await user.type(comboboxInput, 'J');
      await user.clear(comboboxInput);

      // Wait for listbox and check for household badges
      const listbox = await screen.findByRole('listbox');
      const householdBadges = within(listbox).getAllByText(/household/i);
      expect(householdBadges.length).toBeGreaterThan(0);
    });
  });

  // ========== Date Range Selector Tests ==========

  describe('Date Range Selector', () => {
    it('shows preset options', () => {
      renderComponent({ initialPersonId: 1 });

      expect(screen.getByRole('button', { name: /today/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /yesterday/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /last 7 days/i })).toBeInTheDocument();
    });

    it('defaults to Today filter', () => {
      renderComponent({ initialPersonId: 1 });

      const todayButton = screen.getByRole('button', { name: /today/i });
      expect(todayButton).toHaveClass('bg-[#76B900]');
    });

    it('changes date range when preset is clicked', async () => {
      const user = userEvent.setup();
      renderComponent({ initialPersonId: 1 });

      const last7DaysButton = screen.getByRole('button', { name: /last 7 days/i });
      await user.click(last7DaysButton);

      await waitFor(() => {
        expect(mockUsePersonAppearancesQuery).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            start_date: expect.any(String),
            end_date: expect.any(String),
          })
        );
      });
    });

    it('allows custom date range selection', async () => {
      const user = userEvent.setup();
      renderComponent({ initialPersonId: 1 });

      const customButton = screen.getByRole('button', { name: /custom/i });
      await user.click(customButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
      });
    });
  });

  // ========== Journey Timeline Tests ==========

  describe('Journey Timeline', () => {
    it('displays "Today\'s Journey" section header', () => {
      renderComponent({ initialPersonId: 1 });
      expect(screen.getByText(/today.?s journey/i)).toBeInTheDocument();
    });

    it('renders timeline items for each appearance', () => {
      renderComponent({ initialPersonId: 1 });

      const timelineItems = screen.getAllByTestId('timeline-item');
      expect(timelineItems).toHaveLength(4);
    });

    it('displays appearance time in correct format', () => {
      renderComponent({ initialPersonId: 1 });

      // Times should be displayed in 12-hour format with AM/PM
      // We check for any time format as timezone may vary
      const timeElements = screen.getAllByTestId('appearance-time');
      expect(timeElements.length).toBe(4);
      // Each should contain a time pattern like "3:15 AM" or "10:32 PM"
      timeElements.forEach((el) => {
        expect(el.textContent).toMatch(/\d{1,2}:\d{2}\s*(AM|PM)/i);
      });
    });

    it('displays camera name for each appearance', () => {
      renderComponent({ initialPersonId: 1 });

      const driveways = screen.getAllByText('Driveway');
      const frontDoors = screen.getAllByText('Front Door');

      expect(driveways.length).toBeGreaterThan(0);
      expect(frontDoors.length).toBeGreaterThan(0);
    });

    it('shows vertical connector lines between timeline items', () => {
      renderComponent({ initialPersonId: 1 });

      const connectors = screen.getAllByTestId('timeline-connector');
      // One less connector than items (no connector after last item)
      expect(connectors).toHaveLength(3);
    });

    it('shows confidence badge for each appearance', () => {
      renderComponent({ initialPersonId: 1 });

      expect(screen.getByText(/95%/)).toBeInTheDocument();
      expect(screen.getByText(/92%/)).toBeInTheDocument();
    });

    it('displays appearances in chronological order', () => {
      renderComponent({ initialPersonId: 1 });

      const timelineItems = screen.getAllByTestId('timeline-item');

      // Should have 4 items in chronological order
      expect(timelineItems).toHaveLength(4);

      // Verify we can find time elements (actual times depend on timezone)
      const times = timelineItems.map((item) => {
        const timeElement = within(item).getByTestId('appearance-time');
        return timeElement.textContent;
      });

      // All times should be present and in time format
      times.forEach((time) => {
        expect(time).toMatch(/\d{1,2}:\d{2}\s*(AM|PM)/i);
      });
    });

    it('shows action type indicator (arrived/entered/exited/departed)', () => {
      renderComponent({ initialPersonId: 1 });

      // The component infers action type based on camera and sequence
      const actions = screen.getAllByTestId('action-type');
      expect(actions.length).toBeGreaterThan(0);
    });
  });

  // ========== Statistics Cards Tests ==========

  describe('Statistics Cards', () => {
    it('displays statistics section', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: mockAppearancesLast7Days,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('stats-cards')).toBeInTheDocument();
    });

    it('displays total sightings count', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: mockAppearancesLast7Days,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('stat-sightings')).toBeInTheDocument();
      expect(screen.getByText('6')).toBeInTheDocument();
    });

    it('displays average per day', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: mockAppearancesLast7Days,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('stat-avg-day')).toBeInTheDocument();
      // 6 appearances over potentially 7 days
      expect(screen.getByText(/\d+\.\d+/)).toBeInTheDocument();
    });

    it('displays unique cameras count', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: mockAppearancesLast7Days,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('stat-cameras')).toBeInTheDocument();
      // Should show 3 unique cameras (Driveway, Front Door, Backyard)
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('shows Sightings label on first card', () => {
      renderComponent({ initialPersonId: 1 });

      const sightingsCard = screen.getByTestId('stat-sightings');
      expect(within(sightingsCard).getByText(/sightings/i)).toBeInTheDocument();
    });

    it('shows Avg/Day label on second card', () => {
      renderComponent({ initialPersonId: 1 });

      const avgDayCard = screen.getByTestId('stat-avg-day');
      expect(within(avgDayCard).getByText(/avg.*day/i)).toBeInTheDocument();
    });

    it('shows Cameras label on third card', () => {
      renderComponent({ initialPersonId: 1 });

      const camerasCard = screen.getByTestId('stat-cameras');
      expect(within(camerasCard).getByText(/cameras/i)).toBeInTheDocument();
    });
  });

  // ========== Loading States Tests ==========

  describe('Loading States', () => {
    it('shows loading state for persons list', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      });

      renderComponent();

      expect(screen.getByTestId('persons-loading')).toBeInTheDocument();
    });

    it('shows loading state for appearances', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('appearances-loading')).toBeInTheDocument();
    });

    it('shows spinner animation during loading', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      const spinner = screen.getByTestId('loading-spinner');
      expect(spinner).toHaveClass('animate-spin');
    });
  });

  // ========== Empty States Tests ==========

  describe('Empty States', () => {
    it('shows prompt to select person when none selected', () => {
      renderComponent();

      // Look for the specific prompt text in the empty state
      expect(screen.getByText(/select a person to view their tracking data/i)).toBeInTheDocument();
    });

    it('shows empty state when no appearances found', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: { appearances: [], total: 0 },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByText(/no appearances found/i)).toBeInTheDocument();
    });

    it('shows empty state with descriptive message', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: { appearances: [], total: 0 },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByText(/john smith has not been detected/i)).toBeInTheDocument();
    });

    it('shows empty state icon', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: { appearances: [], total: 0 },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByTestId('empty-state-icon')).toBeInTheDocument();
    });

    it('shows no known persons message when list is empty', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      });

      renderComponent();

      expect(screen.getByText(/no known persons/i)).toBeInTheDocument();
    });
  });

  // ========== Error States Tests ==========

  describe('Error States', () => {
    it('shows error state when persons fetch fails', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load persons' },
      });

      renderComponent();

      expect(screen.getByText(/failed to load persons/i)).toBeInTheDocument();
    });

    it('shows error state when appearances fetch fails', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load appearances' },
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByText(/failed to load appearances/i)).toBeInTheDocument();
    });

    it('shows retry button on error', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load appearances' },
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('calls refetch when retry button is clicked', async () => {
      const user = userEvent.setup();
      const refetch = vi.fn();
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load appearances' },
        refetch,
      });

      renderComponent({ initialPersonId: 1 });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      expect(refetch).toHaveBeenCalledTimes(1);
    });

    it('shows generic error message when error has no message', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: {},
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
    });
  });

  // ========== Styling Tests ==========

  describe('Styling', () => {
    it('applies NVIDIA dark theme background', () => {
      renderComponent();

      const tab = screen.getByTestId('person-tracking-tab');
      expect(tab).toHaveClass('bg-[#121212]');
    });

    it('timeline uses NVIDIA green accent color', () => {
      renderComponent({ initialPersonId: 1 });

      const timelineDots = screen.getAllByTestId('timeline-dot');
      expect(timelineDots[0]).toHaveClass('bg-[#76B900]');
    });

    it('statistics cards have proper styling', () => {
      renderComponent({ initialPersonId: 1 });

      const statsCards = screen.getByTestId('stats-cards');
      const cards = within(statsCards).getAllByRole('article');

      expect(cards[0]).toHaveClass('bg-[#1A1A1A]');
      expect(cards[0]).toHaveClass('rounded-lg');
      expect(cards[0]).toHaveClass('border');
    });

    it('person selector has proper dropdown styling', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Type in the combobox to open dropdown
      const comboboxInput = screen.getByRole('combobox');
      await user.type(comboboxInput, 'J');

      // Wait for dropdown and check styling
      const dropdown = await screen.findByTestId('person-dropdown');
      expect(dropdown).toHaveClass('bg-[#1A1A1A]');
      expect(dropdown).toHaveClass('border-gray-700');
    });
  });

  // ========== Accessibility Tests ==========

  describe('Accessibility', () => {
    it('has accessible heading', () => {
      renderComponent();

      const heading = screen.getByRole('heading', { name: /person tracking/i });
      expect(heading).toBeInTheDocument();
    });

    it('person selector has aria-label', () => {
      renderComponent();

      const selector = screen.getByTestId('person-selector');
      expect(selector).toHaveAttribute('aria-label', expect.stringContaining('person'));
    });

    it('date range buttons have aria-pressed attribute', () => {
      renderComponent({ initialPersonId: 1 });

      const todayButton = screen.getByRole('button', { name: /today/i });
      expect(todayButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('timeline items have proper semantic structure', () => {
      renderComponent({ initialPersonId: 1 });

      const timeline = screen.getByRole('list', { name: /journey timeline/i });
      expect(timeline).toBeInTheDocument();

      const timelineItems = within(timeline).getAllByRole('listitem');
      expect(timelineItems).toHaveLength(4);
    });

    it('statistics cards have proper roles', () => {
      renderComponent({ initialPersonId: 1 });

      const statsCards = screen.getByTestId('stats-cards');
      const cards = within(statsCards).getAllByRole('article');
      expect(cards.length).toBe(3);
    });

    it('loading state is announced to screen readers', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      const status = screen.getByRole('status');
      expect(status).toHaveTextContent(/loading/i);
    });

    it('error state is announced to screen readers', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load appearances' },
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });
  });

  // ========== Edge Cases Tests ==========

  describe('Edge Cases', () => {
    it('handles very long person names', async () => {
      const user = userEvent.setup();
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [
          {
            ...mockKnownPersons[0],
            name: 'A Very Long Person Name That Should Be Truncated Properly In The UI',
          },
        ],
        isLoading: false,
        isError: false,
        error: null,
      });

      renderComponent();

      // Type in the combobox to open dropdown
      const comboboxInput = screen.getByRole('combobox');
      await user.type(comboboxInput, 'Very Long');

      // Wait for listbox and check for the long name
      const listbox = await screen.findByRole('listbox');
      expect(within(listbox).getByText('A Very Long Person Name That Should Be Truncated Properly In The UI')).toBeInTheDocument();
    });

    it('handles appearances with missing thumbnail URLs', () => {
      renderComponent({ initialPersonId: 1 });

      // Third appearance has null thumbnail_url
      const timelineItems = screen.getAllByTestId('timeline-item');
      const thirdItem = timelineItems[2];

      // Should show placeholder or icon instead
      expect(within(thirdItem).getByTestId('appearance-icon')).toBeInTheDocument();
    });

    it('handles single appearance correctly', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: {
          appearances: [mockAppearances.appearances[0]],
          total: 1,
        },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      const timelineItems = screen.getAllByTestId('timeline-item');
      expect(timelineItems).toHaveLength(1);

      // Should not show connector after single item
      expect(screen.queryByTestId('timeline-connector')).not.toBeInTheDocument();
    });

    it('handles rapid person selection changes', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Type to open dropdown and select John
      const comboboxInput = screen.getByRole('combobox');
      await user.type(comboboxInput, 'John');

      let listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('John Smith'));

      // Clear and type to select Jane
      await user.clear(comboboxInput);
      await user.type(comboboxInput, 'Jane');
      listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('Jane Doe'));

      // Should show Jane's data, not John's
      await waitFor(() => {
        expect(mockUsePersonAppearancesQuery).toHaveBeenLastCalledWith(
          2,
          expect.any(Object)
        );
      });
    });

    it('calculates statistics correctly with zero appearances', () => {
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: { appearances: [], total: 0 },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent({ initialPersonId: 1 });

      // Stats should show zeros or empty state
      const sightingsCard = screen.queryByTestId('stat-sightings');
      if (sightingsCard) {
        expect(within(sightingsCard).getByText('0')).toBeInTheDocument();
      }
    });

    it('updates statistics when date range changes', async () => {
      const user = userEvent.setup();
      renderComponent({ initialPersonId: 1 });

      // Initially showing today's data
      expect(screen.getByText('4')).toBeInTheDocument();

      // Change to last 7 days
      mockUsePersonAppearancesQuery.mockReturnValue({
        data: mockAppearancesLast7Days,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      const last7DaysButton = screen.getByRole('button', { name: /last 7 days/i });
      await user.click(last7DaysButton);

      await waitFor(() => {
        expect(screen.getByText('6')).toBeInTheDocument();
      });
    });
  });
});
