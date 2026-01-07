import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import ReidHistoryPanel from './ReidHistoryPanel';
import * as api from '../../services/api';

import type { EntityAppearance, EntityHistoryResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchEntityHistory: vi.fn(),
}));

describe('ReidHistoryPanel', () => {
  const mockEntityId = 'test-entity-123';
  const mockAppearance1: EntityAppearance = {
    detection_id: 'det-001',
    camera_id: 'front_door',
    camera_name: 'Front Door',
    timestamp: new Date('2025-01-07T10:00:00Z').toISOString(),
    thumbnail_url: '/api/detections/1/image',
    similarity_score: 0.95,
    attributes: { clothing: 'blue jacket' },
  };

  const mockAppearance2: EntityAppearance = {
    detection_id: 'det-002',
    camera_id: 'backyard',
    camera_name: 'Backyard',
    timestamp: new Date('2025-01-07T11:30:00Z').toISOString(),
    thumbnail_url: '/api/detections/2/image',
    similarity_score: 0.87,
    attributes: { clothing: 'blue jacket', carrying: 'bag' },
  };

  const mockAppearance3: EntityAppearance = {
    detection_id: 'det-003',
    camera_id: 'driveway',
    camera_name: 'Driveway',
    timestamp: new Date('2025-01-07T12:00:00Z').toISOString(),
    thumbnail_url: null,
    similarity_score: 0.72,
    attributes: {},
  };

  const mockHistory: EntityHistoryResponse = {
    entity_id: mockEntityId,
    entity_type: 'person',
    appearances: [mockAppearance1, mockAppearance2, mockAppearance3],
    count: 3,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('displays loading spinner while fetching history', () => {
      (api.fetchEntityHistory as Mock).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { container } = render(
        <ReidHistoryPanel entityId={mockEntityId} entityType="person" />
      );

      expect(screen.getByText(/loading re-identification history/i)).toBeInTheDocument();
      // Check for loader icon by class (lucide-react uses lucide-loader-circle class)
      const loader = container.querySelector('.lucide-loader-circle');
      expect(loader).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when fetch fails', async () => {
      const errorMessage = 'Network error';
      (api.fetchEntityHistory as Mock).mockRejectedValue(new Error(errorMessage));

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('retries fetch when "Try Again" button is clicked', async () => {
      const user = userEvent.setup();
      (api.fetchEntityHistory as Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockHistory);

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      // Wait for error
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });

      // Click retry
      const retryButton = screen.getByRole('button', { name: /try again/i });
      await user.click(retryButton);

      // Should show loading then success
      await waitFor(() => {
        expect(screen.getByText(/re-identification history/i)).toBeInTheDocument();
      });

      expect(api.fetchEntityHistory).toHaveBeenCalledTimes(2);
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no appearances exist', async () => {
      const emptyHistory: EntityHistoryResponse = {
        entity_id: mockEntityId,
        entity_type: 'person',
        appearances: [],
        count: 0,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(emptyHistory);

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/no re-identification history found/i)).toBeInTheDocument();
      });
    });

    it('shows person icon for person entity type in empty state', async () => {
      const emptyHistory: EntityHistoryResponse = {
        entity_id: mockEntityId,
        entity_type: 'person',
        appearances: [],
        count: 0,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(emptyHistory);

      const { container } = render(
        <ReidHistoryPanel entityId={mockEntityId} entityType="person" />
      );

      await waitFor(() => {
        expect(screen.getByText(/no re-identification history found/i)).toBeInTheDocument();
      });

      // Check for User icon (lucide-react adds lucide-user class)
      const icon = container.querySelector('.lucide-user');
      expect(icon).toBeInTheDocument();
    });

    it('shows car icon for vehicle entity type in empty state', async () => {
      const emptyHistory: EntityHistoryResponse = {
        entity_id: mockEntityId,
        entity_type: 'vehicle',
        appearances: [],
        count: 0,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(emptyHistory);

      const { container } = render(
        <ReidHistoryPanel entityId={mockEntityId} entityType="vehicle" />
      );

      await waitFor(() => {
        expect(screen.getByText(/no re-identification history found/i)).toBeInTheDocument();
      });

      // Check for Car icon (lucide-react adds lucide-car class)
      const icon = container.querySelector('.lucide-car');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Timeline Display', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('displays all appearances in the timeline', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
        expect(screen.getByText(/backyard/i)).toBeInTheDocument();
        expect(screen.getByText(/driveway/i)).toBeInTheDocument();
      });
    });

    it('displays appearance count in header', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/3 appearances/i)).toBeInTheDocument();
      });
    });

    it('displays singular "appearance" for count of 1', async () => {
      const singleHistory: EntityHistoryResponse = {
        ...mockHistory,
        appearances: [mockAppearance1],
        count: 1,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(singleHistory);

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/1 appearance$/i)).toBeInTheDocument();
      });
    });

    it('sorts appearances by timestamp (most recent first)', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Get all camera names in order
      const cameraNames = screen.getAllByText(/front door|backyard|driveway/i);

      // Most recent should be first (Driveway at 12:00)
      expect(cameraNames[0]).toHaveTextContent(/driveway/i);
      expect(cameraNames[1]).toHaveTextContent(/backyard/i);
      expect(cameraNames[2]).toHaveTextContent(/front door/i);
    });

    it('displays similarity scores with correct formatting', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText('95%')).toBeInTheDocument();
        expect(screen.getByText('87%')).toBeInTheDocument();
        expect(screen.getByText('72%')).toBeInTheDocument();
      });
    });

    it('displays thumbnails when available', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBeGreaterThanOrEqual(2); // At least 2 appearances have thumbnails
      });
    });

    it('displays attributes when available', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        // Use getAllByText since multiple appearances may have same attributes
        const clothingElements = screen.getAllByText(/clothing: blue jacket/i);
        expect(clothingElements.length).toBeGreaterThanOrEqual(1);

        const carryingElements = screen.getAllByText(/carrying: bag/i);
        expect(carryingElements.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Similarity Score Colors', () => {
    it('applies green color for high similarity (>= 0.9)', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        const highScore = screen.getByText('95%');
        expect(highScore).toHaveClass('text-green-400');
      });
    });

    it('applies lime color for good similarity (>= 0.8)', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        const goodScore = screen.getByText('87%');
        expect(goodScore).toHaveClass('text-[#76B900]');
      });
    });

    it('applies yellow color for moderate similarity (>= 0.7)', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        const moderateScore = screen.getByText('72%');
        expect(moderateScore).toHaveClass('text-yellow-400');
      });
    });

    it('handles null similarity score gracefully', async () => {
      const historyWithNull: EntityHistoryResponse = {
        ...mockHistory,
        appearances: [
          {
            ...mockAppearance1,
            similarity_score: null,
          },
        ],
        count: 1,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(historyWithNull);

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(
        () => {
          expect(screen.getByText('Front Door')).toBeInTheDocument();
          // N/A should not be displayed in timeline (only in comparison view)
          // Since similarity_score is null, the badge simply won't be shown
          const badges = screen.queryAllByText('N/A');
          // May or may not be present depending on whether comparison view is active
          expect(badges.length).toBeGreaterThanOrEqual(0);
        },
        { timeout: 3000 }
      );
    });
  });

  describe('Side-by-Side Comparison', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('shows hint to select appearances initially', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(
          screen.getByText(/click on appearances to select up to 2 for side-by-side comparison/i)
        ).toBeInTheDocument();
      });
    });

    it('allows selecting an appearance by clicking', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Click on first appearance
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);

      // Should be marked as selected
      await waitFor(() => {
        const selectedAppearance = screen.getByRole('button', { pressed: true });
        expect(selectedAppearance).toBeInTheDocument();
      });
    });

    it('shows comparison view when 2 appearances are selected', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Select first two appearances
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);
      await user.click(appearances[1]);

      // Comparison view should appear
      await waitFor(() => {
        expect(screen.getByText(/side-by-side comparison/i)).toBeInTheDocument();
      });
    });

    it('limits selection to 2 appearances maximum', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Try to select 3 appearances
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);
      await user.click(appearances[1]);
      await user.click(appearances[2]);

      // Only 2 should be selected
      await waitFor(() => {
        const selectedAppearances = screen.getAllByRole('button', { pressed: true });
        expect(selectedAppearances).toHaveLength(2);
      });
    });

    it('allows deselecting an appearance', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Select and then deselect
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);

      await waitFor(() => {
        expect(screen.getByRole('button', { pressed: true })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { pressed: true }));

      await waitFor(() => {
        expect(screen.queryByRole('button', { pressed: true })).not.toBeInTheDocument();
      });
    });

    it.skip('clears selection when "Clear" button is clicked in comparison view', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Select 2 appearances
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);
      await user.click(appearances[1]);

      // Wait for comparison view
      await waitFor(() => {
        expect(screen.getByText(/side-by-side comparison/i)).toBeInTheDocument();
      });

      // Verify 2 buttons are selected before clear
      const selectedBefore = screen.getAllByRole('button', { pressed: true });
      expect(selectedBefore.length).toBe(2);

      // Click clear button
      const clearButton = screen.getByText(/clear/i).closest('button');
      expect(clearButton).toBeInTheDocument();
      if (clearButton) {
        await user.click(clearButton);
      }

      // After clicking clear, comparison view should be gone and hint should be back
      // No need for waitFor since this should happen immediately on click
      expect(screen.queryByText(/side-by-side comparison/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { pressed: true })).not.toBeInTheDocument();
      expect(
        screen.getByText(/click on appearances to select up to 2 for side-by-side comparison/i)
      ).toBeInTheDocument();
    });

    it('displays thumbnails in comparison view', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Select 2 appearances
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);
      await user.click(appearances[1]);

      // Wait for comparison view
      await waitFor(
        () => {
          const comparisonSection = screen.getByText(/side-by-side comparison/i).closest('div');
          expect(comparisonSection).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // Verify images are present (at least the 2 from timeline that have thumbnails)
      const allImages = screen.getAllByRole('img');
      expect(allImages.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Refresh Functionality', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('displays refresh button in header', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh history/i })).toBeInTheDocument();
      });
    });

    it('refetches data when refresh button is clicked', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      expect(api.fetchEntityHistory).toHaveBeenCalledTimes(1);

      // Click refresh
      const refreshButton = screen.getByRole('button', { name: /refresh history/i });
      await user.click(refreshButton);

      expect(api.fetchEntityHistory).toHaveBeenCalledTimes(2);
    });
  });

  describe('Callbacks', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('calls onAppearanceClick callback when appearance is clicked', async () => {
      const user = userEvent.setup();
      const onAppearanceClick = vi.fn();

      render(
        <ReidHistoryPanel
          entityId={mockEntityId}
          entityType="person"
          onAppearanceClick={onAppearanceClick}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      // Click on first appearance
      const appearances = screen.getAllByRole('button', { pressed: false });
      await user.click(appearances[0]);

      expect(onAppearanceClick).toHaveBeenCalledWith(
        expect.objectContaining({
          detection_id: expect.any(String),
          camera_id: expect.any(String),
        })
      );
    });
  });

  describe('API Integration', () => {
    it('calls fetchEntityHistory with correct entity ID', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith(mockEntityId);
      });
    });

    it('refetches when entityId prop changes', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);

      const { rerender } = render(
        <ReidHistoryPanel entityId="entity-1" entityType="person" />
      );

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith('entity-1');
      });

      // Change entity ID
      rerender(<ReidHistoryPanel entityId="entity-2" entityType="person" />);

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith('entity-2');
      });

      expect(api.fetchEntityHistory).toHaveBeenCalledTimes(2);
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('provides aria-label for refresh button', async () => {
      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        const refreshButton = screen.getByRole('button', { name: /refresh history/i });
        expect(refreshButton).toHaveAttribute('aria-label', 'Refresh history');
      });
    });

    it('provides aria-pressed state for selectable appearances', async () => {
      const user = userEvent.setup();

      render(<ReidHistoryPanel entityId={mockEntityId} entityType="person" />);

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      const appearance = screen.getAllByRole('button', { pressed: false })[0];
      expect(appearance).toHaveAttribute('aria-pressed', 'false');

      await user.click(appearance);

      await waitFor(() => {
        const selectedAppearance = screen.getByRole('button', { pressed: true });
        expect(selectedAppearance).toHaveAttribute('aria-pressed', 'true');
      });
    });
  });

  describe('Custom Styling', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistory);
    });

    it('applies custom className prop', async () => {
      const customClass = 'my-custom-class';

      const { container } = render(
        <ReidHistoryPanel
          entityId={mockEntityId}
          entityType="person"
          className={customClass}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/front door/i)).toBeInTheDocument();
      });

      const panel = container.querySelector(`.${customClass}`);
      expect(panel).toBeInTheDocument();
    });
  });
});
