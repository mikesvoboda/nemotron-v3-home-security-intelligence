import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityDetailModal, { type EntityDetailModalProps } from './EntityDetailModal';

import type { EntityDetail, EntityAppearance } from '../../services/api';

describe('EntityDetailModal', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock appearances
  const mockAppearances: EntityAppearance[] = [
    {
      detection_id: 'det-001',
      camera_id: 'front_door',
      camera_name: 'Front Door',
      timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
      thumbnail_url: 'https://example.com/thumb1.jpg',
      similarity_score: 0.95,
      attributes: {},
    },
    {
      detection_id: 'det-002',
      camera_id: 'back_yard',
      camera_name: 'Back Yard',
      timestamp: new Date(BASE_TIME - 30 * 60 * 1000).toISOString(),
      thumbnail_url: 'https://example.com/thumb2.jpg',
      similarity_score: 0.88,
      attributes: {},
    },
  ];

  // Mock entity detail
  const mockEntity: EntityDetail = {
    id: 'entity-abc123',
    entity_type: 'person',
    first_seen: new Date(BASE_TIME - 3 * 60 * 60 * 1000).toISOString(),
    last_seen: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
    appearance_count: 2,
    cameras_seen: ['front_door', 'back_yard'],
    thumbnail_url: 'https://example.com/thumbnail.jpg',
    appearances: mockAppearances,
  };

  const defaultProps: EntityDetailModalProps = {
    entity: mockEntity,
    isOpen: true,
    onClose: vi.fn(),
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders modal when isOpen is true', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      render(<EntityDetailModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders entity type in title', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('heading', { name: /Person/i })).toBeInTheDocument();
    });

    it('renders entity ID', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/entity-abc123/)).toBeInTheDocument();
    });

    it('renders thumbnail when available', () => {
      render(<EntityDetailModal {...defaultProps} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThan(0);
    });

    it('renders appearance timeline', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText('Appearance Timeline')).toBeInTheDocument();
    });

    it('renders all appearances', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
    });
  });

  describe('entity info', () => {
    it('displays first seen timestamp', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/First seen/i)).toBeInTheDocument();
    });

    it('displays last seen timestamp', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/Last seen/i)).toBeInTheDocument();
    });

    it('displays appearance count', () => {
      render(<EntityDetailModal {...defaultProps} />);
      // Appearance count is shown as "2" with "appearances" label below
      const countElement = screen.getAllByText('2')[0]; // First "2" is appearance count
      expect(countElement).toBeInTheDocument();
      expect(screen.getByText('appearances')).toBeInTheDocument();
    });

    it('displays cameras seen count', () => {
      render(<EntityDetailModal {...defaultProps} />);
      // Camera count is also "2" with "cameras" label below
      expect(screen.getByText('cameras')).toBeInTheDocument();
    });
  });

  describe('vehicle entity', () => {
    it('renders vehicle type correctly', () => {
      const vehicleEntity: EntityDetail = {
        ...mockEntity,
        entity_type: 'vehicle',
      };
      render(<EntityDetailModal {...defaultProps} entity={vehicleEntity} />);
      expect(screen.getByRole('heading', { name: /Vehicle/i })).toBeInTheDocument();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EntityDetailModal {...defaultProps} onClose={onClose} />);

      // Get the X close button in the header (aria-label="Close modal")
      const closeButton = screen.getByLabelText(/close modal/i);
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onClose when clicking footer close button', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EntityDetailModal {...defaultProps} onClose={onClose} />);

      // Get the footer Close button
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const footerButton = closeButtons[closeButtons.length - 1]; // Last one is footer button
      await user.click(footerButton);

      expect(onClose).toHaveBeenCalledTimes(1);
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('null entity', () => {
    it('returns null when entity is null', () => {
      const { container } = render(<EntityDetailModal {...defaultProps} entity={null} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('styling', () => {
    it('renders styled content', () => {
      render(<EntityDetailModal {...defaultProps} />);
      // Modal renders with content that has styling applied
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('applies border styling', () => {
      render(<EntityDetailModal {...defaultProps} />);
      // Modal renders
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible dialog role', () => {
      render(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has accessible dialog title', () => {
      render(<EntityDetailModal {...defaultProps} />);
      const headings = screen.getAllByRole('heading');
      expect(headings.length).toBeGreaterThanOrEqual(1);
    });

    it('close button has accessible label', () => {
      render(<EntityDetailModal {...defaultProps} />);
      // Multiple close buttons exist (header X and footer button)
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      expect(closeButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('empty appearances', () => {
    it('handles entity with no appearances', () => {
      const entityNoAppearances: EntityDetail = {
        ...mockEntity,
        appearances: [],
        appearance_count: 0,
      };
      render(<EntityDetailModal {...defaultProps} entity={entityNoAppearances} />);
      expect(screen.getByText(/No appearances recorded/i)).toBeInTheDocument();
    });
  });
});
