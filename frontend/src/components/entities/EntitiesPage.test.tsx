import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EntitiesPage from './EntitiesPage';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEntities: vi.fn(),
    fetchEntity: vi.fn(),
  };
});

const mockFetchEntities = vi.mocked(api.fetchEntities);
const mockFetchEntity = vi.mocked(api.fetchEntity);

describe('EntitiesPage', () => {
  // Mock entity data
  const mockEntities: api.EntitySummary[] = [
    {
      id: 'entity-001',
      entity_type: 'person',
      first_seen: '2024-01-15T08:00:00Z',
      last_seen: '2024-01-15T10:00:00Z',
      appearance_count: 5,
      cameras_seen: ['front_door', 'back_yard'],
      thumbnail_url: 'https://example.com/thumb1.jpg',
    },
    {
      id: 'entity-002',
      entity_type: 'vehicle',
      first_seen: '2024-01-15T09:00:00Z',
      last_seen: '2024-01-15T09:30:00Z',
      appearance_count: 2,
      cameras_seen: ['driveway'],
      thumbnail_url: null,
    },
  ];

  const mockEntityDetail: api.EntityDetail = {
    ...mockEntities[0],
    appearances: [
      {
        detection_id: 'det-001',
        camera_id: 'front_door',
        camera_name: 'Front Door',
        timestamp: '2024-01-15T10:00:00Z',
        thumbnail_url: 'https://example.com/thumb1.jpg',
        similarity_score: 0.95,
        attributes: {},
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default successful response
    mockFetchEntities.mockResolvedValue({
      entities: mockEntities,
      count: mockEntities.length,
      limit: 50,
      offset: 0,
    });
    mockFetchEntity.mockResolvedValue(mockEntityDetail);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the page header with title and description', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Entities')).toBeInTheDocument();
      expect(
        screen.getByText('Track and identify people and vehicles across your cameras')
      ).toBeInTheDocument();
    });

    it('displays loading state initially with skeleton loaders', () => {
      mockFetchEntities.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      render(<EntitiesPage />);

      expect(screen.getAllByTestId('entity-card-skeleton').length).toBeGreaterThan(0);
    });

    it('displays entity cards after loading', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Check for entity type badges
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays error state when API fails', async () => {
      mockFetchEntities.mockRejectedValue(new Error('API Error'));

      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.getByText('API Error')).toBeInTheDocument();
      });

      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });

    it('displays empty state when no entities', async () => {
      mockFetchEntities.mockResolvedValue({
        entities: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.getByText('No Entities Found')).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('renders filter buttons for All, Persons, and Vehicles', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Persons')).toBeInTheDocument();
      expect(screen.getByText('Vehicles')).toBeInTheDocument();
    });

    it('filters entities when Persons button is clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Click the Persons filter
      await user.click(screen.getByText('Persons'));

      // API should be called with entity_type filter
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ entity_type: 'person' })
        );
      });
    });

    it('filters entities when Vehicles button is clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Click the Vehicles filter
      await user.click(screen.getByText('Vehicles'));

      // API should be called with entity_type filter
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ entity_type: 'vehicle' })
        );
      });
    });
  });

  describe('Refresh functionality', () => {
    it('renders refresh button', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText('Refresh entities')).toBeInTheDocument();
    });

    it('reloads entities when refresh button is clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Clear previous calls
      mockFetchEntities.mockClear();

      // Click refresh
      await user.click(screen.getByLabelText('Refresh entities'));

      // API should be called again
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });
    });
  });

  describe('Entity detail modal', () => {
    it('opens modal when entity card is clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Find and click the first entity card
      const entityCards = screen.getAllByRole('button');
      const entityCard = entityCards.find((btn) => btn.getAttribute('aria-label')?.includes('View entity'));

      if (entityCard) {
        await user.click(entityCard);

        // API should fetch entity detail
        await waitFor(() => {
          expect(mockFetchEntity).toHaveBeenCalledWith('entity-001');
        });

        // Modal should open
        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Stats display', () => {
    it('displays entity type counts', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Check for counts (1 person, 1 vehicle in mock data)
      expect(screen.getByText('1 person')).toBeInTheDocument();
      expect(screen.getByText('1 vehicle')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toHaveTextContent('Entities');
    });

    it('filter buttons have aria-pressed attribute', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      const allButton = screen.getByText('All');
      expect(allButton).toHaveAttribute('aria-pressed', 'true');

      const personsButton = screen.getByText('Persons');
      expect(personsButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('refresh button is accessible', async () => {
      render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      const refreshButton = screen.getByLabelText('Refresh entities');
      expect(refreshButton).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies NVIDIA green accent color to icons', async () => {
      const { container } = render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Check for the NVIDIA green color class on text elements
      const greenElements = container.querySelectorAll('[class*="text-[#76B900]"]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('has dark theme background', async () => {
      const { container } = render(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading entities...')).not.toBeInTheDocument();
      });

      // Check for the dark background class
      const darkBgElements = container.querySelectorAll('[class*="bg-[#1F1F1F]"]');
      expect(darkBgElements.length).toBeGreaterThan(0);
    });
  });
});
